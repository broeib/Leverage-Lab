# 📊 Leverage Lab: Leveraged ETF DCA & Rebalancing Backtester

> **Live Interactive Site:** [leverage-etf-simulator.netlify.app/dashboard/](https://leverage-etf-simulator.netlify.app/dashboard/)

Welcome to **Leverage Lab**, a professional-grade quantitative backtesting system and interactive visual dashboard designed to model and simulate **leveraged Dollar-Cost Averaging (DCA)** and **dynamic asset allocation strategies** across multiple leveraged ETF universes. 

The system tests **18 rule-based strategies** alongside **4 static benchmarks** over up to **40 years of market history**, to study whether systematic rebalancing can tame the extreme drawdowns of daily-reset leveraged ETFs. Read the [modelling assumptions](#-modelling-assumptions--limitations) before drawing conclusions: most of the leveraged history is synthetic.

---

## 🔬 Core Features & Architecture

### 1. Multi-Universe Configuration
The data layer maps real-world physical tickers into generic *roles* (`1x`, `2x`, `3x` assets), allowing core strategies to run on any universe without modifications:
* **📈 NASDAQ-100 Universe (`qqq`)**:
  * `QQQ` (1x, $0.20\%$ annual drag)
  * `QLD` (2x, $0.75\%$ annual drag)
  * `TQQQ` (3x, $1.50\%$ annual drag)
  * Underlying Index: `%5ENDX` (`^NDX`), backfilled to **October 1985** (40+ years).
* **🔬 Semiconductor Universe (`soxx`)**:
  * `SOXX` (1x, $0.40\%$ annual drag)
  * `USD` (2x, $0.95\%$ annual drag)
  * `SOXL` (3x, $1.10\%$ annual drag)
  * Underlying Index: `%5ESOX` (`^SOX`), backfilled to **May 1994** (32+ years).
* **🏛️ S&P 500 Universe (`spy`)**:
  * `SPY` (1x, $0.10\%$ annual drag)
  * `SSO` (2x, $0.75\%$ annual drag)
  * `UPRO` (3x, $1.50\%$ annual drag)
  * Underlying Index: `%5EGSPC` (`^GSPC`), backfilled to **October 1985** (40+ years).

### 2. Synthetic Pre-Inception History (Backfill)
To simulate the decades before each fund existed (e.g. `TQQQ` before 2010), `data/download_data.py` compounds a synthetic daily return backward from each fund's first real close:
$$P_{t-1} = \frac{P_t}{1 + r_{\text{synth}, t}}$$

$$r_{\text{synth}, t} = L\left(R_{\text{index}, t} + \frac{d}{252}\right) - (L-1)\,\frac{r_{f,t} + s}{252} - \frac{ER}{252}$$

* $L$: leverage (1, 2 or 3); $R_{\text{index}}$: daily price return of `^NDX`, `^SOX` or `^GSPC`.
* $d$: approximate index dividend yield (the indexes are price-only, the real ETFs are total-return).
* $r_{f,t}$: the 13-week T-bill rate (`^IRX`) on that day; the fund borrows $(L-1)$ times its assets.
* $s$: financing spread over T-bills, **0.6%** (0.9% for semiconductors). Calibrated by running each leveraged fund against its own 1x ETF over the fund's live history: TQQQ 0.58%, QLD 0.63%, UPRO 0.61%, SSO 0.67%, SOXL 0.89%.
* $ER$: the fund's expense ratio.

`python data/validate_backfill.py` compares the model with every real fund over its live period. The model is an approximation: it ignores swap-pricing changes, intraday rebalancing costs and tracking error. USD (2x semiconductors) tracks a different index and fits poorly.

### 3. The "Enhanced Quant SMA" Strategy
Leveraged ETFs undergo extreme volatility decay (beta slippage) and catastrophic drawdowns (e.g., -99.9% in market crashes) when bought and held. The `EnhancedSMATrendStrategy` addresses this with:
* **Signal Decoupling**: Technical indicators (SMAs, RSI, MACD) are calculated on the unleveraged 1x index (`QQQ`/`SOXX`) to filter out noise, while trading is executed on leveraged assets.
* **Asymmetric Buffer Bands (Hysteresis Loop)**: Avoids whipsaw signal triggers with a $+3\%$ / $-1.5\%$ band around the 200-day SMA (bull/bear) and a $+2\%$ / $-1\%$ band around the 50-day SMA (strong/mild).
* **Multi-Signal confirmation**: Prevents buying at overbought tops or high-volatility zones by verifying `RSI < 70`, `MACD Histogram >= 0`, and `VIX < 25`.
* **Yield-Bearing Bear Safe Haven**: Sweeps defense capital (CASH) during bear regimes into cash earning the historical **13-week T-bill rate** (a proxy for funds like `SGOV`).

---

## 📁 Repository Structure

```
├── README.md
├── index.html                    # Root redirect to dashboard/ (static hosting)
├── run_backtest.py               # Runs every strategy on every universe, writes results/
├── requirements.txt              # Runtime dependencies (requirements-dev.txt adds pytest)
├── config/strategies.json        # Strategy thresholds, costs, execution lag, DCA amount
├── data/
│   ├── download_data.py          # Yahoo download, OHLC adjustment, backfill, T-bill and VIX caches
│   └── validate_backfill.py      # Compares the backfill model with real funds
├── engine/                       # Backtester loop, Portfolio, metrics, constants
├── indicators/                   # SMA, RSI, MACD, Bollinger, composite score, EMA channel
├── strategies/                   # 18 strategies + 4 benchmarks (see strategies/__init__.py)
├── tools/
│   ├── sweep_ema_channel.py      # EMA-channel parameter sweep with a held-out period
│   ├── simulate_sma.py           # Builds dashboard/sma_simulator.html
│   └── config_loader.py
├── tests/                        # pytest suite (offline)
├── results/                      # Generated: summary_<universe>.csv, dashboard_data_<universe>.json
└── dashboard/                    # Static Chart.js dashboard + SMA simulator page
```

Cached market data (`data/etf_prices_*.csv`, `data/vix_data.csv`, `data/rates_irx.csv`) is gitignored and rebuilt by `python data/download_data.py all`. A warning is printed when a cache is more than 7 days old.

---

## ⚠️ Modelling Assumptions & Limitations

* **Synthetic history.** Before each ETF's inception the price is modelled (see above). For TQQQ/UPRO/SOXL that is 1985-2010, most of the window. The dashboard shows the inception dates.
* **Execution.** Signals use the last close of each week; trades fill at the **next trading day's close** (`backtest.execution_lag_days` in the config).
* **Costs.** **5 bps** of turnover per rebalance (`universes.<u>.slippage`). No taxes.
* **Cash and risk-free rate.** Cash earns, and Sharpe/Sortino are measured against, the historical 13-week T-bill rate week by week.
* **VIX.** `^VIX` starts in 1990; earlier dates are left empty (not filled), so VIX-gated rules treat them as "unknown".
* **In-sample selection.** EMA Channel v2 was chosen from a parameter sweep. `tools/sweep_ema_channel.py` now ranks variants on data before 2019 and reports 2019+ as a holdout, but its thresholds were originally found on the full history.
* **Semiconductor universe.** USD and SOXL track different indexes than `^SOX`, so their backfill is approximate.

---

## 📈 Backtest Results

Regenerate with `python run_backtest.py`; full tables are in `results/summary_<universe>.csv` and on the dashboard.

### NASDAQ-100 (`QQQ`/`QLD`/`TQQQ`)

*1985-10-07 to 2026-10-12, 2,141 weeks of $5,000 DCA ($10,705,000 invested). Top 6 by final value.*

| Strategy | Final Value ($) | CAGR (TWR, %) | Max Drawdown (%) | Sharpe |
| :--- | ---: | ---: | ---: | ---: |
| EMA Channel: 3x / 2x / Cash | $8,350,091,090 | 19.62% | 80.25% | 0.554 |
| EMA Channel: 3x / 1x / Cash | $7,950,779,621 | 19.36% | 80.58% | 0.550 |
| EMA Channel v2: Risk-Managed | $7,577,431,888 | 20.95% | 75.19% | 0.578 |
| Composer SMA: 100% TQQQ / CASH | $6,838,402,216 | 18.60% | 90.95% | 0.539 |
| 4-Tier Graduated Leverage (1% Buffer) | $4,418,338,216 | 19.72% | 90.24% | 0.553 |
| SMA Trend Regime | $3,943,621,319 | 20.12% | 96.66% | 0.559 |

### S&P 500 (`SPY`/`SSO`/`UPRO`)

*1985-10-07 to 2026-10-12, 2,141 weeks of $5,000 DCA ($10,705,000 invested). Top 6 by final value.*

| Strategy | Final Value ($) | CAGR (TWR, %) | Max Drawdown (%) | Sharpe |
| :--- | ---: | ---: | ---: | ---: |
| EMA Channel v2: Risk-Managed | $1,372,247,580 | 17.64% | 59.61% | 0.558 |
| Composer SMA: 100% UPRO / CASH | $832,496,064 | 14.40% | 79.97% | 0.483 |
| Bollinger Mean Reversion | $801,039,269 | 16.91% | 80.87% | 0.537 |
| Buy & Hold UPRO (3x) | $786,845,841 | 16.53% | 97.70% | 0.510 |
| SMA Trend Regime | $652,366,506 | 15.21% | 72.54% | 0.493 |
| Tactical Cash & Buy-the-Dip | $643,120,264 | 15.69% | 96.15% | 0.484 |

### Semiconductors (`SOXX`/`USD`/`SOXL`)

*1994-05-09 to 2026-10-12, 1,693 weeks of $5,000 DCA ($8,465,000 invested). Top 6 by final value.*

| Strategy | Final Value ($) | CAGR (TWR, %) | Max Drawdown (%) | Sharpe |
| :--- | ---: | ---: | ---: | ---: |
| Enhanced Quant SMA | $1,489,097,826 | 21.43% | 94.82% | 0.587 |
| RSI Momentum | $952,298,857 | 17.26% | 99.59% | 0.531 |
| Buy & Hold USD (2x) | $898,594,582 | 15.21% | 99.70% | 0.528 |
| Bollinger Mean Reversion | $861,833,243 | 13.16% | 99.87% | 0.498 |
| VIX Volatility Regime | $749,682,467 | 14.83% | 99.39% | 0.508 |
| Equal Weight (33/33/33) | $689,841,049 | 14.07% | 99.75% | 0.511 |

--- | :--- | :--- | :--- | :--- | :--- |
| **Enhanced Quant SMA** | **$1,393,777,413** | **16,552.06%** | **17.30%** | **95.45%** | **0.489** |
| **RSI Momentum** | $1,292,100,002 | 15,337.28% | 17.02% | 98.67% | 0.497 |
| **Buy & Hold USD (2x)** | $1,036,885,798 | 12,288.12% | 16.22% | 99.37% | 0.509 |
| **Buy & Hold SOXL (3x)** | $918,467,894 | 10,873.33% | 15.78% | 99.94% | 0.627 |
| **Equal Weight (33/33/33)** | $860,441,403 | 10,180.06% | 15.55% | 99.44% | 0.498 |
| **Buy & Hold SOXX (1x)** | $276,913,901 | 3,208.41% | 11.53% | 89.25% | 0.373 |

---

## 💻 How to Run Locally

### 1. Installation
Clone the repository and install all required python dependencies:
```bash
git clone https://github.com/YOUR_USERNAME/Leverage-Lab.git
cd Leverage-Lab
pip install -r requirements.txt        # or requirements-dev.txt to also run the tests
python -m pytest -q                    # offline test suite
```

### 2. Run the Quantitative Backtester
To download ETF data, compute the historical backfills, run the simulations, and compile the results:
```bash
# Backtests all three universes and exports results/dashboard_data_*.json
# (add --refresh to re-download market data)
python3 run_backtest.py
```

### 3. Open the Interactive Dashboard
Launch a local development server at the project root to serve the premium web dashboard:
```bash
python3 -m http.server 8000
```
Open your browser and navigate to: [http://localhost:8000](http://localhost:8000)

---

## 🌐 Live Web Hosting
This repository is configured to be hosted instantly on free static providers like **Netlify** or **GitHub Pages**. Because it serves a root redirect `index.html`, visitors are routed seamlessly to `dashboard/index.html` on mount, maintaining relative fetch paths to the compiled JSONs under `results/`.
