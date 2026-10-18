#!/usr/bin/env python3
"""Parameter sweep for the EMA Channel strategy family.

Runs a grid of EMA-channel variants across every universe and reports
time-weighted (DCA-independent) CAGR, Sharpe, max drawdown and Calmar for the
full history and for three sub-periods, so that a variant can be judged on
robustness rather than on a single in-sample number.

Usage:
    python3 tools/sweep_ema_channel.py [--out results.csv] [--universes qqq,soxx,spy]
"""

import os
import sys
import argparse
import itertools
from dataclasses import dataclass, field
from typing import Dict, Optional, List

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from data.download_data import load_all_data, UNIVERSES
from indicators.ema_channel import compute_ema
from indicators.rsi import add_rsi_column
from engine.backtester import Backtester
from engine.constants import RISK_FREE_RATE_ANNUAL, WEEKS_PER_YEAR
from strategies.base import BaseStrategy
from tools.config_loader import get_universe_params

TQQQ = {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
QLD = {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
QQQ = {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
CASH = {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}
QQQ_QLD = {"QQQ": 0.5, "QLD": 0.5, "TQQQ": 0.0, "CASH": 0.0}
QLD_TQQQ = {"QQQ": 0.0, "QLD": 0.5, "TQQQ": 0.5, "CASH": 0.0}

GRAY_ALLOCS = {"QLD": QLD, "QQQ": QQQ, "QQQ+QLD": QQQ_QLD, "QLD+TQQQ": QLD_TQQQ}


def _leverage(alloc: Dict[str, float]) -> float:
    return alloc["QQQ"] * 1 + alloc["QLD"] * 2 + alloc["TQQQ"] * 3


def _cap(alloc: Dict[str, float], cap: Dict[str, float]) -> Dict[str, float]:
    """Return whichever of the two allocations carries less leverage."""
    return cap if _leverage(cap) < _leverage(alloc) else alloc

SUB_PERIODS = [
    ("p1_to2000", None, "2000-12-31"),
    ("p2_2001_2012", "2001-01-01", "2012-12-31"),
    ("p3_2013on", "2013-01-01", None),
]


@dataclass
class Variant:
    length: int = 200
    gray: str = "QLD"            # key into GRAY_ALLOCS
    gray_mode: str = "fixed"     # fixed | asym | hold_prev
    vix_gate: Optional[float] = None
    top_mult: float = 1.0
    bot_mult: float = 1.0
    # Stage-2 risk overlays (each caps leverage at `overlay` allocation when it fires)
    dd_breaker: Optional[float] = None   # 1x price below (1-x) * rolling 252d high
    fast_ema: Optional[int] = None       # 1x close below EMA(fast_ema) of close
    vol_gate: Optional[float] = None     # 20d realised vol (annualised %) above this
    overlay: str = "gray"                # "gray" -> gray allocation, "QQQ" -> 1x

    @property
    def name(self) -> str:
        parts = [f"L{self.length}", f"gray={self.gray}", self.gray_mode]
        if self.vix_gate:
            parts.append(f"vix<{self.vix_gate:g}")
        if self.top_mult != 1.0 or self.bot_mult != 1.0:
            parts.append(f"buf={self.top_mult:g}/{self.bot_mult:g}")
        ov = []
        if self.dd_breaker:
            ov.append(f"dd>{self.dd_breaker:g}")
        if self.fast_ema:
            ov.append(f"ema{self.fast_ema}")
        if self.vol_gate:
            ov.append(f"vol>{self.vol_gate:g}")
        if ov:
            parts.append("[" + ",".join(ov) + f"->{self.overlay}]")
        return " ".join(parts)


class ParamEMAChannel(BaseStrategy):
    """EMA channel strategy driven by a Variant.

    gray_mode:
      fixed     - gray zone always holds the gray allocation.
      asym      - gray entered from green holds the gray allocation; gray entered
                  from red stays in cash (re-lever only on a fresh green).
      hold_prev - gray zone keeps whatever the previous zone held (pure hysteresis).
    vix_gate    - while green, if VIX >= gate step down to the gray allocation.
    top/bot_mult - buffer multipliers applied to the channel lines.
    """

    def __init__(self, v: Variant) -> None:
        self.v = v
        self.prev_zone = "RED"

    @property
    def name(self) -> str:
        return self.v.name

    @property
    def description(self) -> str:
        return ""

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        v = self.v
        price = market_data["QQQ"]
        top = market_data.get(f"EMA_TOP_{v.length}")
        bot = market_data.get(f"EMA_BOT_{v.length}")
        if top is None or bot is None or np.isnan(top) or np.isnan(bot):
            return CASH

        if price > top * v.top_mult:
            zone = "GREEN"
        elif price < bot * v.bot_mult:
            zone = "RED"
        else:
            zone = "GRAY"

        gray_alloc = GRAY_ALLOCS[v.gray]

        if zone == "GREEN":
            vix = market_data.get("VIX")
            if v.vix_gate is not None and vix is not None and vix >= v.vix_gate:
                alloc = gray_alloc
            else:
                alloc = TQQQ
            self.prev_zone = "GREEN"
        elif zone == "RED":
            alloc = CASH
            self.prev_zone = "RED"
        else:
            if v.gray_mode == "fixed":
                alloc = gray_alloc
            elif v.gray_mode == "asym":
                alloc = gray_alloc if self.prev_zone == "GREEN" else CASH
            else:  # hold_prev
                alloc = TQQQ if self.prev_zone == "GREEN" else CASH
            # prev_zone stays as the last non-gray zone

        # Stage-2 overlays: cap leverage when a risk trigger fires
        if v.dd_breaker or v.fast_ema or v.vol_gate:
            cap_alloc = QQQ if v.overlay == "QQQ" else gray_alloc
            fired = False
            if v.dd_breaker:
                hi = market_data.get("ROLL_HIGH_252")
                fired |= hi is not None and not np.isnan(hi) and price < hi * (1 - v.dd_breaker)
            if v.fast_ema:
                fe = market_data.get(f"EMA_CLOSE_{v.fast_ema}")
                fired |= fe is not None and not np.isnan(fe) and price < fe
            if v.vol_gate:
                rv = market_data.get("RVOL_20")
                fired |= rv is not None and not np.isnan(rv) and rv > v.vol_gate
            if fired:
                alloc = _cap(alloc, cap_alloc)
        return alloc


def twr_metrics(h: pd.DataFrame) -> Dict[str, float]:
    """Time-weighted CAGR / Sharpe / max DD / Calmar for a slice of history."""
    tv = h["total_value"]
    c = h["weekly_contribution"]
    prev = tv.shift(1)
    r = ((tv - c - prev) / prev).iloc[1:]
    r = r[prev.iloc[1:] > 0].replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 10:
        return {"cagr": np.nan, "sharpe": np.nan, "maxdd": np.nan, "calmar": np.nan}
    growth = (1 + r).cumprod()
    years = len(r) / WEEKS_PER_YEAR
    cagr = growth.iloc[-1] ** (1 / years) - 1
    maxdd = -(growth / growth.cummax() - 1).min()
    ex = r - RISK_FREE_RATE_ANNUAL / WEEKS_PER_YEAR
    sharpe = ex.mean() / ex.std() * np.sqrt(WEEKS_PER_YEAR) if ex.std() > 0 else 0.0
    calmar = cagr / maxdd if maxdd > 0 else np.nan
    return {"cagr": cagr * 100, "sharpe": sharpe, "maxdd": maxdd * 100, "calmar": calmar}


def prepare(universe: str, lengths: List[int]):
    close, vix = load_all_data(universe=universe)
    df = close.copy()
    df = add_rsi_column(df, price_col="QQQ", period=14)
    high = df["QQQ_High"] if "QQQ_High" in df.columns else df["QQQ"]
    for L in lengths:
        df[f"EMA_TOP_{L}"] = compute_ema(high, L)
        df[f"EMA_BOT_{L}"] = compute_ema(df["QQQ"], L)
    # Overlay inputs
    df["ROLL_HIGH_252"] = df["QQQ"].rolling(252, min_periods=252).max()
    for fe in (50, 100):
        df[f"EMA_CLOSE_{fe}"] = compute_ema(df["QQQ"], fe)
    df["RVOL_20"] = df["QQQ"].pct_change().rolling(20).std() * np.sqrt(252) * 100
    contrib = get_universe_params(universe).get("weekly_contribution", 5000.0)
    return Backtester(close, vix, df, weekly_contribution=contrib)


def build_grid() -> List[Variant]:
    lengths = [100, 150, 200, 250, 300]
    grays = ["QLD", "QQQ", "QQQ+QLD", "QLD+TQQQ"]
    modes = ["fixed", "asym", "hold_prev"]
    vix_gates = [None, 25.0, 30.0]
    buffers = [(1.0, 1.0), (1.01, 0.99), (1.02, 0.98)]
    grid = []
    for L, g, m, vg, (t, b) in itertools.product(lengths, grays, modes, vix_gates, buffers):
        # hold_prev ignores the gray allocation unless a VIX gate uses it
        if m == "hold_prev" and vg is None and g != "QLD":
            continue
        grid.append(Variant(L, g, m, vg, t, b))
    return grid


def evaluate(bt: Backtester, universe: str, v: Variant) -> Dict[str, object]:
    """Run one variant on one universe and return a flat metrics row."""
    res = bt.run(ParamEMAChannel(v))
    h = res.history
    row = {"universe": universe, "variant": v.name, "length": v.length, "gray": v.gray,
           "gray_mode": v.gray_mode, "vix_gate": v.vix_gate or 0,
           "top_mult": v.top_mult, "bot_mult": v.bot_mult,
           "final_value": res.metrics["total_value"],
           "rebalances": res.metrics["rebalance_count"]}
    for k, val in twr_metrics(h).items():
        row[f"full_{k}"] = val
    for pname, start, end in SUB_PERIODS:
        for k, val in twr_metrics(h.loc[start:end]).items():
            row[f"{pname}_{k}"] = val
    return row


# Worker-process state (one Backtester per universe, built lazily per process)
_WORKER_BT: Dict[str, Backtester] = {}
_WORKER_LENGTHS: List[int] = []


def _worker_init(lengths: List[int]) -> None:
    import logging
    logging.getLogger("LeverageLab").setLevel(logging.WARNING)
    global _WORKER_LENGTHS
    _WORKER_LENGTHS = lengths


def _worker_run(job) -> Dict[str, object]:
    universe, v = job
    if universe not in _WORKER_BT:
        _WORKER_BT[universe] = prepare(universe, _WORKER_LENGTHS)
    return evaluate(_WORKER_BT[universe], universe, v)


def build_grid_stage2() -> List[Variant]:
    """Risk overlays on top of the two best stage-1 bases."""
    bases = [dict(length=200, gray="QLD", top_mult=1.01, bot_mult=0.99),
             dict(length=200, gray="QLD+TQQQ", top_mult=1.01, bot_mult=0.99)]
    grid = []
    for b in bases:
        for dd, fe, vg, ov in itertools.product([None, 0.10, 0.15, 0.20], [None, 50, 100],
                                                [None, 30.0, 40.0], ["gray", "QQQ"]):
            if dd is None and fe is None and vg is None and ov == "QQQ":
                continue  # identical to the no-overlay base
            grid.append(Variant(dd_breaker=dd, fast_ema=fe, vol_gate=vg, overlay=ov, **b))
    return grid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage2", action="store_true", help="run risk-overlay grid on top of best stage-1 bases")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "results", "ema_channel_sweep.csv"))
    ap.add_argument("--universes", default=",".join(UNIVERSES.keys()))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()

    universes = args.universes.split(",")
    grid = build_grid_stage2() if args.stage2 else build_grid()
    lengths = sorted({v.length for v in grid})
    jobs = [(u, v) for u in universes for v in grid]
    print(f"{len(grid)} variants x {len(universes)} universes = {len(jobs)} runs on {args.workers} workers", flush=True)

    # Make sure caches exist before forking workers so they don't all download at once
    for u in universes:
        load_all_data(universe=u)

    from concurrent.futures import ProcessPoolExecutor
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init, initargs=(lengths,)) as ex:
        for i, row in enumerate(ex.map(_worker_run, jobs, chunksize=8)):
            rows.append(row)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(jobs)}", flush=True)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} rows to {args.out}")


if __name__ == "__main__":
    # Quiet the per-strategy engine logging during the sweep
    import logging
    logging.getLogger("LeverageLab").setLevel(logging.WARNING)
    main()
