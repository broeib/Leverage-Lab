# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Retail and systematic algorithmic investors, quant traders, and financial engineers evaluating leveraged ETF rebalancing strategies, DCA distributions, and SMA-based market regime filters across leveraged universes (QQQ/QLD/TQQQ and SOXX/USD/SOXL).

## Product Purpose

Leverage Lab backtests and visualizes long-term leveraged ETF rebalancing strategies with realistic dollar-cost averaging ($5,000/week DCA), regime filtering, drawdown analysis, and strategy comparison, helping investors understand risk-adjusted returns and volatility drag.

## Positioning

Quantitative, evidence-based backtesting specifically tailored for multi-tier leveraged ETFs (1x, 2x, 3x) with dynamic DCA cash-flow simulation, real historical prices, and visual regime switching rather than simplified lump-sum approximations.

## Operating Context

Web dashboard running locally or hosted as a static interactive report (`dashboard/index.html` and `dashboard/sma_simulator.html`) driven by Chart.js, HTML5 canvas, and client-side JavaScript processing backtest CSV/JSON run data.

## Capabilities and Constraints

- Client-side static architecture without heavy frontend build steps.
- Multi-universe switching: NASDAQ-100 (QQQ/QLD/TQQQ) and Semiconductors (SOXX/USD/SOXL).
- Interactive strategy performance comparison, awards, drawdown curves, equity progression, and metric tables.
- Linked interactive SMA trend regime visual simulator.
- Must remain fast, responsive, and lightweight without dependency on heavy frameworks.

## Brand Commitments

- Name: Leverage Lab
- Voice: Analytical, precise, objective, institutional-grade.
- Design Archetype: Modern FinTech / Clean Studio (Linear & Stripe inspired).

## Product Principles

1. **Clarity Over Decoration**: Financial data, curves, and statistics should communicate immediately without visual gimmicks, glows, or distracting animations.
2. **Tabular Precision**: Numbers, percentages, ratios, and dates require clear monospace alignment and high contrast.
3. **Restrained Hierarchy**: Subtle elevations, crisp 1px borders, and purposeful contrast replace card-in-card nesting and heavy shadows.
