#!/usr/bin/env python3
"""Leveraged ETF Backtesting System.

Runs all strategies and benchmarks against historical data for multiple
ETF universes (QQQ/QLD/TQQQ and SOXX/USD/SOXL).

Outputs per universe:
  - results/summary_{universe}.csv: Performance comparison table
  - results/dashboard_data_{universe}.json: Data for the interactive web dashboard
"""

import os
import sys
import json
from typing import Dict, List, Tuple, Any
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.download_data import load_all_data, UNIVERSES
from indicators.sma import add_sma_columns
from indicators.rsi import add_rsi_column
from indicators.bollinger import add_bollinger_columns
from indicators.macd import add_macd_columns
from indicators.composite import add_composite_column
from engine.backtester import Backtester, generate_summary_table, BacktestResult
from strategies import ALL_STRATEGIES, ALL_BENCHMARKS
from tools.config_loader import get_universe_params
from engine.logger import logger


def prepare_indicator_data(close_prices: pd.DataFrame, vix_data: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators on the close price data.

    Args:
        close_prices: DataFrame with QQQ, QLD, TQQQ close prices.
        vix_data: DataFrame with VIX_Close.

    Returns:
        pd.DataFrame: Original prices + all indicator columns.
    """
    logger.info("Computing technical indicators...")

    df = close_prices.copy()

    # SMA 50 and 200
    df = add_sma_columns(df, price_col="QQQ")
    logger.info("  ✓ SMA (50, 200)")

    # RSI 14
    df = add_rsi_column(df, price_col="QQQ", period=14)
    logger.info("  ✓ RSI (14)")

    # Bollinger Bands (20, 2σ)
    df = add_bollinger_columns(df, price_col="QQQ", window=20, num_std=2.0)
    logger.info("  ✓ Bollinger Bands (20, 2σ)")

    # MACD (12/26/9)
    df = add_macd_columns(df, price_col="QQQ")
    logger.info("  ✓ MACD (12/26/9)")

    # Composite score (needs SMA and RSI already computed)
    vix_aligned = vix_data["VIX_Close"].reindex(df.index).ffill()
    df = add_composite_column(df, vix_aligned)
    logger.info("  ✓ Composite Score")

    # Find first date where all indicators are available
    first_valid = df.dropna().index[0] if not df.dropna().empty else df.index[0]
    logger.info(f"Indicator data: {len(df)} rows. First valid date: {first_valid.date()}")

    return df


def _rename_strategy(name: str, universe_config: Dict[str, Any]) -> str:
    """Replace generic ticker names with real ticker names for display.

    For example, "Buy & Hold QQQ (1x)" becomes "Buy & Hold SOXX (1x)" in the
    SOXX universe.

    Args:
        name: Strategy name string.
        universe_config: Universe config dict from UNIVERSES.

    Returns:
        str: Display-friendly strategy name.
    """
    tickers = universe_config["tickers"]
    # Only rename if NOT the QQQ universe (QQQ universe keeps original names)
    if tickers["1x"] == "QQQ":
        return name
    result = name
    # Replace longest matches first to avoid partial match corruption
    result = result.replace("TQQQ", tickers["3x"])
    result = result.replace("QLD", tickers["2x"])
    result = result.replace("QQQ", tickers["1x"])
    return result


def export_dashboard_data(
    results: List[BacktestResult], 
    summary_df: pd.DataFrame, 
    output_dir: str, 
    universe_key: str
) -> str:
    """Export results as JSON for the interactive dashboard.

    Args:
        results: List of BacktestResult objects.
        summary_df: Summary DataFrame.
        output_dir: Directory to write to.
        universe_key: Universe key ("qqq" or "soxx").

    Returns:
        str: Path to the generated JSON dashboard file.
    """
    config = UNIVERSES[universe_key]
    tickers = config["tickers"]

    dashboard_data = {
        "universe": {
            "key": universe_key,
            "name": config["name"],
            "tickers": tickers,
            "start_date": config["start_date"],
        },
        "summary": [],
        "equity_curves": {},
        "drawdown_curves": {},
        "allocation_history": {},
    }

    # Summary table — rename strategies for display
    for _, row in summary_df.iterrows():
        row_dict = row.to_dict()
        row_dict["Strategy"] = _rename_strategy(row_dict["Strategy"], config)
        dashboard_data["summary"].append(row_dict)

    # Time series data for each strategy
    for result in results:
        name = _rename_strategy(result.strategy_name, config)
        h = result.history

        if h.empty:
            continue

        dates = [str(d.date()) for d in h.index]
        dashboard_data["equity_curves"][name] = {
            "dates": dates,
            "values": [round(v, 2) for v in h["total_value"].values],
            "invested": [round(v, 2) for v in h["total_invested"].values],
        }

        dashboard_data["drawdown_curves"][name] = {
            "dates": dates,
            "values": [round(v, 2) for v in h["drawdown_pct"].values],
        }

        dashboard_data["allocation_history"][name] = {
            "dates": dates,
            "QQQ": [round(v, 4) for v in h["QQQ_alloc"].values] if "QQQ_alloc" in h.columns else [0.0] * len(h),
            "QLD": [round(v, 4) for v in h["QLD_alloc"].values] if "QLD_alloc" in h.columns else [0.0] * len(h),
            "TQQQ": [round(v, 4) for v in h["TQQQ_alloc"].values] if "TQQQ_alloc" in h.columns else [0.0] * len(h),
            "CASH": [round(v, 4) for v in h["CASH_alloc"].values] if "CASH_alloc" in h.columns else [0.0] * len(h),
        }

    output_file = os.path.join(output_dir, f"dashboard_data_{universe_key}.json")
    with open(output_file, "w") as f:
        json.dump(dashboard_data, f)

    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    logger.info(f"✓ Dashboard data saved to {output_file} ({file_size_mb:.1f} MB)")

    return output_file


def run_universe(universe_key: str, force_refresh: bool = False) -> Tuple[List[BacktestResult], pd.DataFrame]:
    """Run the full backtest pipeline for a single universe.

    Args:
        universe_key: Universe key ("qqq" or "soxx").
        force_refresh: If True, re-download data.

    Returns:
        Tuple[List[BacktestResult], pd.DataFrame]: List of results and comparison DataFrame.
    """
    config = UNIVERSES[universe_key]
    tickers = config["tickers"]

    logger.info("=" * 70)
    logger.info(f"BACKTESTING UNIVERSE: {config['name']}")
    logger.info(f"  Tickers: {tickers['1x']} (1x), {tickers['2x']} (2x), {tickers['3x']} (3x)")
    logger.info("=" * 70)

    # 1. Load dynamic configuration parameters for weekly contribution
    universe_params = get_universe_params(universe_key)
    weekly_contribution = universe_params.get("weekly_contribution", 5000.0)

    # 2. Load data
    logger.info(f"[1/5] Loading historical data for {config['name']}...")
    close_prices, vix_data = load_all_data(universe=universe_key, force_refresh=force_refresh)

    # 3. Compute indicators
    logger.info("[2/5] Computing technical indicators...")
    indicator_data = prepare_indicator_data(close_prices, vix_data)

    # 4. Initialize strategies
    logger.info("[3/5] Initializing strategies...")
    strategies = [cls() for cls in ALL_STRATEGIES]
    benchmarks = [cls() for cls in ALL_BENCHMARKS]
    all_runners = strategies + benchmarks

    logger.info(f"  Strategies: {len(strategies)}")
    for s in strategies:
        logger.info(f"    • {s.name}: {s.description}")
    logger.info(f"  Benchmarks: {len(benchmarks)}")
    for b in benchmarks:
        logger.info(f"    • {b.name}: {b.description}")

    # 5. Run backtests
    logger.info("[4/5] Running backtests...")
    backtester = Backtester(
        close_prices, 
        vix_data, 
        indicator_data, 
        weekly_contribution=weekly_contribution
    )
    results = backtester.run_all(all_runners)

    # 6. Generate output
    logger.info("[5/5] Generating results...")

    # Create output directory
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    # Summary table
    summary_df = generate_summary_table(results)
    summary_file = os.path.join(results_dir, f"summary_{universe_key}.csv")
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"✓ Summary saved to {summary_file}")

    # Print summary to console
    logger.info("=" * 70)
    logger.info(f"PERFORMANCE SUMMARY — {config['name']} (sorted by Total Return)")
    logger.info("=" * 70)

    display_cols = [
        "Strategy", "total_value", "profit", "total_return_pct",
        "cagr_pct", "max_drawdown_pct", "sharpe_ratio", "rebalance_count"
    ]
    display_df = summary_df[display_cols].copy()
    display_df["Strategy"] = display_df["Strategy"].apply(lambda x: _rename_strategy(x, config))
    display_df.columns = [
        "Strategy", "Final Value ($)", "Profit ($)", "Return (%)",
        "CAGR (%)", "Max DD (%)", "Sharpe", "Rebalances"
    ]

    for col in ["Final Value ($)", "Profit ($)"]:
        display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")

    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 30)
    print(display_df.to_string(index=False))

    # Export dashboard data
    export_dashboard_data(results, summary_df, results_dir, universe_key)

    return results, summary_df


def main() -> Dict[str, Tuple[List[BacktestResult], pd.DataFrame]]:
    """Main orchestrator — runs backtests across all universes."""
    logger.info("=" * 70)
    logger.info("LEVERAGED ETF BACKTESTING SYSTEM INITIALIZED")
    logger.info("=" * 70)
    logger.info(f"Universes: {', '.join(config['name'] for config in UNIVERSES.values())}")

    all_results = {}
    for universe_key in UNIVERSES:
        results, summary_df = run_universe(universe_key, force_refresh=False)
        all_results[universe_key] = (results, summary_df)

    logger.info("=" * 70)
    logger.info("ALL BACKTESTS COMPLETE")
    logger.info("=" * 70)

    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    logger.info(f"Results saved to: {results_dir}")
    logger.info("Open dashboard/index.html to view interactive results.")

    return all_results


if __name__ == "__main__":
    main()
