"""
CLI validation tool to compare synthetic backfill model returns against actual ETF performance.

For each universe and role with real fund data (e.g. TQQQ, QLD, QQQ, SOXL, USD, SOXX,
UPRO, SSO, SPY), this script runs the backfill return formula over the fund's real life
and compares model CAGR vs actual CAGR, reporting the gap in percentage points per year (pp/yr).

Usage:
    python data/validate_backfill.py [--spread SPREAD] [--universe UNIVERSE]
"""

import sys
import os
import argparse
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.download_data import (
    UNIVERSES,
    DEFAULT_FINANCING_SPREAD,
    _download_single_ticker,
    load_risk_free_rate,
)


def run_validation(override_spread=None, target_universe="all"):
    """Run model vs actual CAGR validation across universes and roles."""
    universes_to_run = (
        [target_universe] if target_universe in UNIVERSES else list(UNIVERSES.keys())
    )

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results = []

    for u_key in universes_to_run:
        u_cfg = UNIVERSES[u_key]
        idx_ticker = u_cfg["index"]
        idx_name = idx_ticker.replace("%5E", "^")
        start_date = u_cfg["start_date"]
        div_yield = u_cfg.get("dividend_yield", 0.0)
        spread = override_spread if override_spread is not None else u_cfg.get("financing_spread", DEFAULT_FINANCING_SPREAD)

        print(f"\nEvaluating universe: {u_cfg['name']} (index: {idx_name}, spread: {spread:.4f})...")
        idx_data = _download_single_ticker(idx_ticker, start_date, end_date)
        if idx_data is None or len(idx_data) == 0:
            print(f"Error: Could not download index data for {idx_name}")
            continue

        idx_data = idx_data[~idx_data.index.duplicated(keep="first")]
        idx_data.index = pd.to_datetime(idx_data.index).normalize()

        rf_series = load_risk_free_rate(idx_data.index)

        for role_key, ticker in u_cfg["tickers"].items():
            lev_params = u_cfg["leverage_params"][role_key]
            leverage = lev_params["leverage"]
            er = lev_params.get("expense_ratio", lev_params.get("drag", 0.0))

            t_data = _download_single_ticker(ticker, start_date, end_date)
            if t_data is None or len(t_data) == 0:
                print(f"Warning: Could not download data for {ticker}")
                continue

            t_data = t_data[~t_data.index.duplicated(keep="first")]
            t_data.index = pd.to_datetime(t_data.index).normalize()

            common_dates = t_data.index.intersection(idx_data.index).sort_values()
            if len(common_dates) < 20:
                print(f"Warning: Insufficient overlapping data for {ticker}")
                continue

            act_close = t_data.loc[common_dates, "Close"]
            idx_close = idx_data.loc[common_dates, "Close"]
            rf_aligned = rf_series.reindex(common_dates).ffill().bfill().fillna(0.0)

            # Fund actual lifespan
            start_dt = common_dates[0]
            end_dt = common_dates[-1]
            years = (end_dt - start_dt).days / 365.25

            if years <= 0:
                continue

            act_cagr = (act_close.iloc[-1] / act_close.iloc[0]) ** (1.0 / years) - 1.0

            # Daily index return
            idx_ret = idx_close.pct_change()
            idx_ret.iloc[0] = 0.0

            # Model daily return formula:
            # synth_return = L * (index_return + div/252) - (L - 1) * (rf + spread)/252 - er/252
            daily_div = leverage * (div_yield / 252.0)
            daily_er = er / 252.0
            if leverage == 1.0:
                daily_financing = 0.0
            else:
                daily_financing = (leverage - 1.0) * (rf_aligned + spread) / 252.0

            synth_ret = (leverage * idx_ret) + daily_div - daily_financing - daily_er
            synth_ret.iloc[0] = 0.0

            # Forward compound model price starting from fund inception price
            model_price = (1.0 + synth_ret).cumprod() * act_close.iloc[0]
            model_cagr = (model_price.iloc[-1] / model_price.iloc[0]) ** (1.0 / years) - 1.0

            gap_pp = (model_cagr - act_cagr) * 100.0

            results.append({
                "universe": u_key,
                "role": role_key,
                "ticker": ticker,
                "inception": start_dt.strftime("%Y-%m-%d"),
                "years": years,
                "act_cagr": act_cagr * 100.0,
                "model_cagr": model_cagr * 100.0,
                "gap_pp": gap_pp,
                "spread": spread,
            })

    # Display results table
    print("\n" + "=" * 90)
    print(f"{'Universe':<10} {'Role':<6} {'Ticker':<8} {'Inception':<12} {'Actual CAGR':<13} {'Model CAGR':<13} {'Gap (pp/yr)':<13} {'Spread':<8}")
    print("-" * 90)
    for r in results:
        print(
            f"{r['universe']:<10} {r['role']:<6} {r['ticker']:<8} {r['inception']:<12} "
            f"{r['act_cagr']:>10.2f}%   {r['model_cagr']:>10.2f}%   {r['gap_pp']:>10.2f} pp   {r['spread']:>7.4f}"
        )
    print("=" * 90 + "\n")
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate backfill model CAGR against actual ETF history.")
    parser.add_argument(
        "--spread",
        type=float,
        default=None,
        help="Financing spread to test (overrides universe default). E.g. 0.0050",
    )
    parser.add_argument(
        "--universe",
        type=str,
        default="all",
        choices=["all", "qqq", "soxx", "spy"],
        help="Universe to validate (default: all)",
    )
    args = parser.parse_args()

    run_validation(override_spread=args.spread, target_universe=args.universe)


if __name__ == "__main__":
    main()
