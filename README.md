# 📊 Leverage Lab: Leveraged ETF DCA & Rebalancing Backtester

> **Live Interactive Site:** [leverage-etf-simulator.netlify.app/dashboard/](https://leverage-etf-simulator.netlify.app/dashboard/)

Welcome to **Leverage Lab**, a professional-grade quantitative backtesting system and interactive visual dashboard designed to model and simulate **leveraged Dollar-Cost Averaging (DCA)** and **dynamic asset allocation strategies** across multiple leveraged ETF universes. 

The system tests **9 advanced quantitative strategies** alongside **4 static benchmarks** over up to **40 years of market history**, demonstrating how smart rebalancing can tame the extreme drawdowns of daily-reset leveraged ETFs while capturing massive compounding returns.

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

### 2. Mathematical Backward-Compounding Engine (40-Year History)
To simulate performance prior to the modern ETF inceptions (e.g. `TQQQ` in 2010), the system implements a **synthetic backward-compounding price generator** in `data/download_data.py`. For any pre-inception day $t$:
$$P_{t-1} = \frac{P_t}{1.0 + r_{\text{synth}, t}}$$

Where the daily synthetic return $r_{\text{synth}, t}$ incorporates index movement and drag cost:
$$r_{\text{synth}, t} = (R_{\text{Index}, t} \times \text{Leverage}) - \frac{\text{Annual Drag}}{252}$$

This mathematical engine guarantees accurate tracking of leverage decay, borrowing costs, and compounding parameters prior to modern ETF listings.

### 3. The "Enhanced Quant SMA" Strategy
Leveraged ETFs undergo extreme volatility decay (beta slippage) and catastrophic drawdowns (e.g., -99.9% in market crashes) when bought and held. The `EnhancedSMATrendStrategy` addresses this with:
* **Signal Decoupling**: Technical indicators (SMAs, RSI, MACD) are calculated on the unleveraged 1x index (`QQQ`/`SOXX`) to filter out noise, while trading is executed on leveraged assets.
* **Asymmetric Buffer Bands (Hysteresis Loop)**: Avoids whipsaw signal triggers by requiring a $+2\%$ buffer to leverage up, and a $-1\%$ trigger to de-leverage.
* **Multi-Signal confirmation**: Prevents buying at overbought tops or high-volatility zones by verifying `RSI < 70`, `MACD Histogram >= 0`, and `VIX < 25`.
* **Yield-Bearing Bear Safe Haven**: Sweeps defense capital (CASH) during bear regimes into a **4.5% annual yield** compounding weekly (simulating Treasury proxies like `SGOV`).

---

## 📁 Repository Structure

```
├── README.md                  # Project overview & documentation
├── index.html                 # Root redirect file (for hosting support)
├── run_backtest.py            # Backtest loop and JSON/CSV generation
├── requirements.txt           # Python dependency file
├── data/
│   ├── download_data.py       # Data caching, index download, and backfill
│   ├── etf_prices_qqq.csv     # Cached historical prices (NASDAQ-100)
│   ├── etf_prices_soxx.csv    # Cached historical prices (Semiconductors)
│   └── vix_data.csv           # Aligned VIX dataset (from 1985)
├── engine/
│   ├── backtester.py          # Backtester loop executor
│   └── portfolio.py           # Rebalancer and portfolio value tracker
├── indicators/
│   ├── sma.py / rsi.py        # Technical indicator formulas
│   └── bollinger.py / macd.py 
├── strategies/
│   ├── base.py                # Base strategy schema
│   ├── enhanced_sma.py        # Asymmetric buffer band strategy
│   └── composite.py           # Blended multi-signal indicators
├── results/
│   ├── dashboard_data_qqq.json   # Dynamic JSON data (NASDAQ-100)
│   └── dashboard_data_soxx.json  # Dynamic JSON data (Semiconductors)
└── dashboard/
    ├── index.html             # Premium interactive UI dashboard
    └── sma_simulator.html     # Standalone visual transaction simulator
```

---

## 📈 Backtest Results Comparison (1994 - 2026)

*Simulated over 1,674 weeks with **$5,000 weekly DCA contributions** ($8,370,000 total principal).*

### Semiconductors Universe (`SOXX`/`USD`/`SOXL`)
| Strategy | Final Value ($) | Return (%) | CAGR (%) | Max Drawdown (%) | Sharpe Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
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
pip install -r requirements.txt
```

### 2. Run the Quantitative Backtester
To download ETF data, compute the historical backfills, run the simulations, and compile the results:
```bash
# This will backtest both universes and export results/dashboard_data_*.json
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
