#!/usr/bin/env python3
"""
QQQ Leveraged ETF Backtesting System
=====================================

Runs all 7 strategies + 4 benchmarks against historical data for QQQ, QLD, and TQQQ.
Outputs:
  - results/summary.csv: Performance comparison table
  - results/dashboard_data.json: Data for the interactive web dashboard
"""

import os
import sys
import json
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.download_data import load_all_data
from indicators.sma import add_sma_columns
from indicators.rsi import add_rsi_column
from indicators.bollinger import add_bollinger_columns
from indicators.macd import add_macd_columns
from indicators.composite import add_composite_column
from engine.backtester import Backtester, generate_summary_table
from strategies import ALL_STRATEGIES, ALL_BENCHMARKS


def prepare_indicator_data(close_prices: pd.DataFrame, vix_data: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators on the close price data.

    Args:
        close_prices: DataFrame with QQQ, QLD, TQQQ close prices.
        vix_data: DataFrame with VIX_Close.

    Returns:
        pd.DataFrame: Original prices + all indicator columns.
    """
    print("\nComputing technical indicators...")

    df = close_prices.copy()

    # SMA 50 and 200
    df = add_sma_columns(df, price_col="QQQ")
    print("  ✓ SMA (50, 200)")

    # RSI 14
    df = add_rsi_column(df, price_col="QQQ", period=14)
    print("  ✓ RSI (14)")

    # Bollinger Bands (20, 2σ)
    df = add_bollinger_columns(df, price_col="QQQ", window=20, num_std=2.0)
    print("  ✓ Bollinger Bands (20, 2σ)")

    # MACD (12/26/9)
    df = add_macd_columns(df, price_col="QQQ")
    print("  ✓ MACD (12/26/9)")

    # Composite score (needs SMA and RSI already computed)
    vix_aligned = vix_data["VIX_Close"].reindex(df.index).ffill()
    df = add_composite_column(df, vix_aligned)
    print("  ✓ Composite Score")

    # Forward-fill any NaN in VIX for alignment
    print(f"\n  Indicator data: {len(df)} rows, {len(df.columns)} columns")
    print(f"  First valid date (all indicators ready): ", end="")

    # Find first date where all indicators are available
    first_valid = df.dropna().index[0] if not df.dropna().empty else df.index[0]
    print(f"{first_valid.date()}")

    return df


def export_dashboard_data(results, summary_df, output_dir):
    """Export results as JSON for the interactive dashboard.

    Args:
        results: List of BacktestResult objects.
        summary_df: Summary DataFrame.
        output_dir: Directory to write to.
    """
    dashboard_data = {
        "summary": [],
        "equity_curves": {},
        "drawdown_curves": {},
        "allocation_history": {},
    }

    # Summary table
    for _, row in summary_df.iterrows():
        dashboard_data["summary"].append(row.to_dict())

    # Time series data for each strategy
    for result in results:
        name = result.strategy_name
        h = result.history

        if h.empty:
            continue

        # Equity curve (downsample to weekly for performance)
        dates = [str(d.date()) for d in h.index]
        dashboard_data["equity_curves"][name] = {
            "dates": dates,
            "values": [round(v, 2) for v in h["total_value"].values],
            "invested": [round(v, 2) for v in h["total_invested"].values],
        }

        # Drawdown curve
        dashboard_data["drawdown_curves"][name] = {
            "dates": dates,
            "values": [round(v, 2) for v in h["drawdown_pct"].values],
        }

        # Allocation history
        dashboard_data["allocation_history"][name] = {
            "dates": dates,
            "QQQ": [round(v, 4) for v in h["QQQ_alloc"].values] if "QQQ_alloc" in h.columns else [0.0] * len(h),
            "QLD": [round(v, 4) for v in h["QLD_alloc"].values] if "QLD_alloc" in h.columns else [0.0] * len(h),
            "TQQQ": [round(v, 4) for v in h["TQQQ_alloc"].values] if "TQQQ_alloc" in h.columns else [0.0] * len(h),
            "CASH": [round(v, 4) for v in h["CASH_alloc"].values] if "CASH_alloc" in h.columns else [0.0] * len(h),
        }

    output_file = os.path.join(output_dir, "dashboard_data.json")
    with open(output_file, "w") as f:
        json.dump(dashboard_data, f)

    print(f"\n✓ Dashboard data saved to {output_file}")
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  File size: {file_size_mb:.1f} MB")


def main():
    """Main entry point — runs all strategies and generates output."""
    print("=" * 70)
    print("QQQ LEVERAGED ETF BACKTESTING SYSTEM")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading historical data...")
    close_prices, vix_data = load_all_data(force_refresh=False)

    # 2. Compute indicators
    print("\n[2/5] Computing technical indicators...")
    indicator_data = prepare_indicator_data(close_prices, vix_data)

    # 3. Initialize strategies
    print("\n[3/5] Initializing strategies...")
    strategies = [cls() for cls in ALL_STRATEGIES]
    benchmarks = [cls() for cls in ALL_BENCHMARKS]
    all_runners = strategies + benchmarks

    print(f"  Strategies: {len(strategies)}")
    for s in strategies:
        print(f"    • {s.name}: {s.description}")
    print(f"  Benchmarks: {len(benchmarks)}")
    for b in benchmarks:
        print(f"    • {b.name}: {b.description}")

    # 4. Run backtests
    print("\n[4/5] Running backtests...")
    backtester = Backtester(close_prices, vix_data, indicator_data)
    results = backtester.run_all(all_runners)

    # 5. Generate output
    print("\n[5/5] Generating results...")

    # Create output directory
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    # Summary table
    summary_df = generate_summary_table(results)
    summary_file = os.path.join(results_dir, "summary.csv")
    summary_df.to_csv(summary_file, index=False)
    print(f"\n✓ Summary saved to {summary_file}")

    # Print summary to console
    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY (sorted by Total Return)")
    print("=" * 70)

    # Format for display
    display_cols = [
        "Strategy", "total_value", "profit", "total_return_pct",
        "cagr_pct", "max_drawdown_pct", "sharpe_ratio", "rebalance_count"
    ]
    display_df = summary_df[display_cols].copy()
    display_df.columns = [
        "Strategy", "Final Value ($)", "Profit ($)", "Return (%)",
        "CAGR (%)", "Max DD (%)", "Sharpe", "Rebalances"
    ]

    # Format numbers
    for col in ["Final Value ($)", "Profit ($)"]:
        display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")

    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 30)
    print(display_df.to_string(index=False))

    # Export dashboard data
    export_dashboard_data(results, summary_df, results_dir)

    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE")
    print("=" * 70)
    print(f"\nResults directory: {results_dir}")
    print(f"Open dashboard/index.html to view interactive results")

    return results, summary_df


if __name__ == "__main__":
    results, summary = main()
