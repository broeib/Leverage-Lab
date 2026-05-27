import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import sys

# Define file paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from indicators.rsi import compute_rsi
from indicators.macd import compute_macd

DATA_FILE = os.path.join(BASE_DIR, "data", "etf_prices.csv")
VIX_FILE = os.path.join(BASE_DIR, "data", "vix_data.csv")
OUTPUT_HTML = os.path.join(BASE_DIR, "dashboard", "sma_simulator.html")

def run_simulation():
    print("="*60)
    print("        ENHANCED SMA TREND REGIME VISUAL SIMULATOR")
    print("="*60)
    
    # 1. Load ETF Prices
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found. Please run backtest or download script first.")
        return
        
    print(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE, index_col=0, parse_dates=True, header=[0, 1])
    qqq = df['Close']['QQQ'].dropna()
    print(f"Loaded {len(qqq)} historical daily bars for QQQ ({qqq.index[0].date()} to {qqq.index[-1].date()})")
    
    # 2. Calculate Technical Indicators
    print("Calculating Simple Moving Averages, RSI, and MACD...")
    sma_50 = qqq.rolling(window=50, min_periods=50).mean()
    sma_200 = qqq.rolling(window=200, min_periods=200).mean()
    rsi = compute_rsi(qqq, period=14)
    macd, macd_signal, macd_hist = compute_macd(qqq)
    
    # 3. Load VIX Volatility Index Data
    if os.path.exists(VIX_FILE):
        print(f"Loading VIX data from {VIX_FILE}...")
        vix_df = pd.read_csv(VIX_FILE, index_col=0, parse_dates=True)
        vix = vix_df["VIX_Close"].reindex(qqq.index).ffill().fillna(19.0)
    else:
        print("Warning: VIX data file not found, defaulting to VIX = 19.0")
        vix = pd.Series(19.0, index=qqq.index)
        
    # Combine into a single clean DataFrame and drop NaN warm-up rows
    sim_df = pd.DataFrame({
        'Price': qqq,
        'SMA_50': sma_50,
        'SMA_200': sma_200,
        'RSI': rsi,
        'MACD': macd,
        'MACD_Signal': macd_signal,
        'MACD_Hist': macd_hist,
        'VIX': vix
    }).dropna()
    
    print(f"Simulation window after indicator warm-up: {len(sim_df)} days ({sim_df.index[0].date()} to {sim_df.index[-1].date()})")
    
    # 4. Simulate Regimes and Allocations
    print("Simulating Standard and Enhanced Quant SMA strategies...")
    
    std_regimes = []
    enh_regimes = []
    enh_allocations = []
    enh_reasons = []
    
    # State tracking for Enhanced hysteresis loop
    prev_regime = "BEAR"  # "BULL_STRONG", "BULL_MILD", "BEAR"
    
    for idx, row in sim_df.iterrows():
        p = row['Price']
        s50 = row['SMA_50']
        s200 = row['SMA_200']
        rsi_val = row['RSI']
        m_hist = row['MACD_Hist']
        v_val = row['VIX']
        
        # A. Standard SMA Trend Regime
        if p > s50 and p > s200:
            std_reg = 'TQQQ'
        elif p > s200:
            std_reg = 'QLD'
        else:
            std_reg = 'QQQ'
        std_regimes.append(std_reg)
        
        # B. Enhanced Quant SMA Regime
        # Technical confirmations
        is_momentum_bullish = m_hist >= 0
        is_not_overbought = rsi_val < 70.0
        is_volatility_safe = v_val < 25.0
        
        # Buffers
        sma_200_upper = s200 * 1.03
        sma_200_lower = s200 * 0.985
        sma_50_upper = s50 * 1.02
        sma_50_lower = s50 * 0.99
        
        # Determine Major Regime (BULL vs BEAR) using SMA_200 buffers
        if prev_regime == "BEAR":
            if p > sma_200_upper:
                current_major = "BULL"
            else:
                current_major = "BEAR"
        else:
            if p < sma_200_lower:
                current_major = "BEAR"
            else:
                current_major = "BULL"
                
        # Determine Regime using SMA_50 buffers (if in BULL)
        if current_major == "BULL":
            if prev_regime == "BULL_STRONG":
                if p < sma_50_lower:
                    current_regime = "BULL_MILD"
                else:
                    current_regime = "BULL_STRONG"
            elif prev_regime == "BULL_MILD":
                if p > sma_50_upper:
                    current_regime = "BULL_STRONG"
                else:
                    current_regime = "BULL_MILD"
            else:  # Coming from BEAR
                if p > sma_50_upper:
                    current_regime = "BULL_STRONG"
                else:
                    current_regime = "BULL_MILD"
        else:
            current_regime = "BEAR"
            
        prev_regime = current_regime
        enh_regimes.append(current_regime)
        
        # Apply technical confirmations to choose active allocation
        if current_regime == "BULL_STRONG":
            if is_momentum_bullish and is_not_overbought and is_volatility_safe:
                alloc = "TQQQ"
                reason = "🟢 <b>Strong Bull confirmed:</b> Price is in strong trend with healthy momentum (MACD Histogram >= 0), stable volatility (VIX < 25), and normal RSI (< 70). Max speed in TQQQ (3x)."
            else:
                alloc = "QLD/QQQ"
                disconf = []
                if not is_momentum_bullish: disconf.append("bearish MACD histogram")
                if not is_not_overbought: disconf.append("RSI overbought (>70)")
                if not is_volatility_safe: disconf.append("VIX high stress (>=25)")
                reason = f"🟣 <b>Strong Bull disconfirmed ({', '.join(disconf)}):</b> Trend is strong but key confirmations failed. De-leveraged to 50% QLD / 50% QQQ to avoid beta slippage."
        elif current_regime == "BULL_MILD":
            if is_volatility_safe:
                alloc = "QLD"
                reason = "🟡 <b>Mild Bull confirmed:</b> Price is in mild uptrend and volatility is stable (VIX < 25). Target 100% QLD (2x) leverage."
            else:
                alloc = "QQQ"
                reason = "🔵 <b>Mild Bull high-risk (VIX high):</b> Trend is up, but market volatility is dangerous (VIX >= 25). Safely downshifted to 100% defensive QQQ."
        else:  # BEAR
            alloc = "CASH"
            reason = "🔴 <b>Bear Market / Cash sweep:</b> Price fell below SMA_200 buffer band. Tactical exit to high-yield CASH (SGOV proxy at 4.5% yield) to protect nest egg."
            
        enh_allocations.append(alloc)
        enh_reasons.append(reason)
        
    sim_df['Std_Regime'] = std_regimes
    sim_df['Enh_Regime'] = enh_regimes
    sim_df['Enh_Alloc'] = enh_allocations
    sim_df['Enh_Reason'] = enh_reasons
    
    # 5. Detect Trigger Events
    print("Compiling trigger event timelines...")
    
    # Standard Triggers
    std_triggers = []
    current_std = sim_df['Std_Regime'].iloc[0]
    std_triggers.append({
        'Date': sim_df.index[0].strftime('%Y-%m-%d'),
        'Price': float(sim_df['Price'].iloc[0]),
        'SMA_50': float(sim_df['SMA_50'].iloc[0]),
        'SMA_200': float(sim_df['SMA_200'].iloc[0]),
        'From': 'None',
        'To': current_std,
        'Reason': 'Simulation started. Initial regime calculated.'
    })
    
    for i in range(1, len(sim_df)):
        date = sim_df.index[i]
        p = sim_df['Price'].iloc[i]
        s50 = sim_df['SMA_50'].iloc[i]
        s200 = sim_df['SMA_200'].iloc[i]
        regime = sim_df['Std_Regime'].iloc[i]
        
        if regime != current_std:
            reason = ""
            if regime == 'TQQQ':
                reason = "🟢 <b>Strong Bull Market:</b> Price crossed above both short-term (50-day) and long-term (200-day) averages. Maximize speed in TQQQ!"
            elif regime == 'QLD':
                if current_std == 'TQQQ':
                    reason = "🟡 <b>Warning Signal:</b> Price dipped below short-term (50-day) average, but remains above long-term. Safely downshift to QLD."
                else:
                    reason = "🟡 <b>Early Recovery:</b> Price climbed back above long-term (200-day) average, but remains below short-term. Move to QLD."
            elif regime == 'QQQ':
                reason = "🔴 <b>Bear Market / Defense:</b> Price fell below long-term (200-day) average. Switch to safe 1x QQQ to avoid massive leverage losses."
                
            std_triggers.append({
                'Date': date.strftime('%Y-%m-%d'),
                'Price': float(p),
                'SMA_50': float(s50),
                'SMA_200': float(s200),
                'From': current_std,
                'To': regime,
                'Reason': reason
            })
            current_std = regime
            
    # Enhanced Triggers
    enh_triggers = []
    current_enh = sim_df['Enh_Alloc'].iloc[0]
    enh_triggers.append({
        'Date': sim_df.index[0].strftime('%Y-%m-%d'),
        'Price': float(sim_df['Price'].iloc[0]),
        'SMA_50': float(sim_df['SMA_50'].iloc[0]),
        'SMA_200': float(sim_df['SMA_200'].iloc[0]),
        'From': 'None',
        'To': current_enh,
        'Reason': 'Simulation started. Initial Enhanced Quant allocation calculated.'
    })
    
    for i in range(1, len(sim_df)):
        date = sim_df.index[i]
        p = sim_df['Price'].iloc[i]
        s50 = sim_df['SMA_50'].iloc[i]
        s200 = sim_df['SMA_200'].iloc[i]
        alloc = sim_df['Enh_Alloc'].iloc[i]
        reason = sim_df['Enh_Reason'].iloc[i]
        
        if alloc != current_enh:
            enh_triggers.append({
                'Date': date.strftime('%Y-%m-%d'),
                'Price': float(p),
                'SMA_50': float(s50),
                'SMA_200': float(s200),
                'From': current_enh,
                'To': alloc,
                'Reason': reason
            })
            current_enh = alloc
            
    print(f"Total Standard Triggers: {len(std_triggers) - 1}")
    print(f"Total Enhanced Triggers: {len(enh_triggers) - 1}")
    
    # 6. Generate Plotly Figure
    print("Generating base Plotly interactive chart...")
    fig = go.Figure()
    
    # QQQ Price trace
    fig.add_trace(go.Scatter(
        x=sim_df.index, y=sim_df['Price'],
        mode='lines',
        name='QQQ Price',
        line=dict(color='#ffffff', width=2),
        hovertemplate='Date: %{x}<br>Price: $%{y:.2f}<extra></extra>'
    ))
    
    # SMA 50 trace
    fig.add_trace(go.Scatter(
        x=sim_df.index, y=sim_df['SMA_50'],
        mode='lines',
        name='50-day SMA (Short-term)',
        line=dict(color='#38bdf8', width=1.5, dash='dash'),
        hovertemplate='50 SMA: $%{y:.2f}<extra></extra>'
    ))
    
    # SMA 200 trace
    fig.add_trace(go.Scatter(
        x=sim_df.index, y=sim_df['SMA_200'],
        mode='lines',
        name='200-day SMA (Long-term)',
        line=dict(color='#fb923c', width=1.5),
        hovertemplate='200 SMA: $%{y:.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        title={
            'text': 'QQQ SMA Trend Regime Simulation Map',
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': dict(size=20, color='#ffffff')
        },
        paper_bgcolor='#0b0f19',
        plot_bgcolor='#0b0f19',
        xaxis=dict(
            gridcolor='#1e293b',
            zeroline=False,
            tickfont=dict(color='#a0aec0'),
            rangeslider=dict(visible=False),
            type="date"
        ),
        yaxis=dict(
            gridcolor='#1e293b',
            zeroline=False,
            tickfont=dict(color='#a0aec0'),
            tickprefix='$'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#ffffff')
        ),
        margin=dict(l=40, r=40, t=80, b=40),
        height=550
    )
    
    plotly_div = fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='sma-chart')
    
    # 7. Serialize Data to JSON Strings
    js_data = []
    for idx, row in sim_df.iterrows():
        js_data.append({
            'd': idx.strftime('%Y-%m-%d'),
            'p': float(row['Price']),
            's50': float(row['SMA_50']),
            's200': float(row['SMA_200']),
            'rsi': float(row['RSI']),
            'macd_h': float(row['MACD_Hist']),
            'vix': float(row['VIX']),
            'std_reg': row['Std_Regime'],
            'enh_reg': row['Enh_Regime'],
            'enh_all': row['Enh_Alloc'],
            'enh_reason': row['Enh_Reason']
        })
    js_data_json = json.dumps(js_data)
    std_triggers_json = json.dumps(std_triggers)
    enh_triggers_json = json.dumps(enh_triggers)
    
    # 8. Define HTML Template
    print("Assembling final interactive HTML report...")
    
    # Write the full dashboard HTML using simple string replace to bypass f-string brace escaping.
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMA Trend Regime Simulator</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #060814;
            --bg-card: rgba(15, 23, 42, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --green: #10b981;
            --yellow: #f59e0b;
            --red: #f43f5e;
            --purple: #a855f7;
            --blue: #38bdf8;
            --accent-blue: #38bdf8;
            --gradient-active: linear-gradient(135deg, #38bdf8, #818cf8);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        
        body {
            background-color: var(--bg-main);
            color: var(--text-main);
            padding: 2rem;
            min-height: 100vh;
            background-image: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.06) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(244, 63, 94, 0.06) 0%, transparent 40%);
            background-attachment: fixed;
        }
        
        .container {
            max-width: 1500px;
            margin: 0 auto;
        }
        
        header {
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1.5rem;
        }
        
        h1 {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }
        
        .back-link {
            color: #38bdf8;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: color 0.2s;
        }
        
        .back-link:hover {
            color: #818cf8;
        }
        
        /* Segmented Controller */
        .strategy-toggle-wrapper {
            display: flex;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 4px;
            gap: 4px;
            backdrop-filter: blur(12px);
        }
        
        .btn-segment {
            padding: 8px 20px;
            border: none;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            color: var(--text-muted);
            background: transparent;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .btn-segment:hover:not(.active) {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.03);
        }
        
        .btn-segment.active {
            background: var(--gradient-active);
            color: #030712;
            box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
        }
        
        /* Dashboard Layout Split */
        .dashboard-layout {
            display: grid;
            grid-template-columns: 2.7fr 1.3fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        @media (max-width: 1024px) {
            .dashboard-layout {
                grid-template-columns: 1fr;
            }
        }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            position: relative;
        }
        
        .card-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1.25rem;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            padding-bottom: 0.75rem;
            letter-spacing: -0.01em;
        }
        
        /* Dynamic Stats Cards */
        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .stat-card {
            background: rgba(15, 23, 42, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.1rem;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            box-shadow: inset 0 2px 4px rgba(255,255,255,0.01);
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.01em;
        }
        
        .stat-bar-container {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 0.25rem;
        }
        
        .stat-bar {
            height: 100%;
            border-radius: 3px;
            transition: width 0.4s ease-out;
        }
        
        /* HUD Inspector Panel styles */
        .hud-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        
        .hud-item.status-ok {
            border-left: 3px solid var(--green);
            background: rgba(16, 185, 129, 0.02);
        }
        
        .hud-item.status-fail {
            border-left: 3px solid var(--red);
            background: rgba(244, 63, 94, 0.02);
        }
        
        .hud-item.status-neutral {
            border-left: 3px solid var(--yellow);
            background: rgba(245, 158, 11, 0.02);
        }
        
        .hud-item.status-info {
            border-left: 3px solid var(--blue);
            background: rgba(56, 189, 248, 0.02);
        }
        
        .hud-item.status-purple {
            border-left: 3px solid var(--purple);
            background: rgba(168, 85, 247, 0.02);
        }
        
        /* Interactive Row Clicking */
        tbody tr {
            transition: all 0.2s ease-in-out;
        }
        tbody tr:hover {
            background-color: rgba(56, 189, 248, 0.06) !important;
        }
        tbody tr:hover .zoom-helper {
            opacity: 1;
            transform: translateX(0);
        }
        
        .active-row td {
            background-color: rgba(56, 189, 248, 0.1) !important;
            border-top: 1px solid rgba(56, 189, 248, 0.25) !important;
            border-bottom: 1px solid rgba(56, 189, 248, 0.25) !important;
            font-weight: 500;
        }
        
        .zoom-helper {
            display: inline-block;
            font-size: 0.7rem;
            color: var(--accent-blue);
            background: rgba(56, 189, 248, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
            opacity: 0;
            transform: translateX(-4px);
            transition: all 0.2s ease;
        }
        
        /* Floating Action Banner */
        .zoom-banner {
            display: none;
            align-items: center;
            justify-content: space-between;
            background: rgba(10, 15, 30, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(12px);
            animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        
        @keyframes slideIn {
            from { transform: translateY(-10px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .btn-reset {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #ffffff;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-reset:hover {
            background: #ffffff;
            color: #030712;
        }

        /* Stock Legend Card */
        .legend-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-top: 1.5rem;
            padding-top: 1.25rem;
            border-top: 1px solid var(--border-color);
        }
        .legend-item {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
        }
        .legend-icon {
            font-size: 1.2rem;
            line-height: 1.2;
        }
        .legend-title {
            font-weight: 700;
            font-size: 0.9rem;
            color: #f1f5f9;
            margin-bottom: 0.25rem;
        }
        .legend-desc {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
        }

        /* Table Styles */
        .table-wrapper {
            max-height: 500px;
            overflow-y: auto;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }
        
        th {
            background-color: rgba(10, 15, 30, 0.9);
            padding: 0.9rem;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 1px solid var(--border-color);
        }
        
        td {
            padding: 0.9rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            font-size: 0.9rem;
        }
        
        /* Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        
        .badge-tqqq {
            background-color: rgba(16, 185, 129, 0.12);
            color: var(--green);
            border: 1px solid rgba(16, 185, 129, 0.25);
        }
        
        .badge-qld {
            background-color: rgba(245, 158, 11, 0.12);
            color: var(--yellow);
            border: 1px solid rgba(245, 158, 11, 0.25);
        }
        
        .badge-qqq {
            background-color: rgba(56, 189, 248, 0.12);
            color: var(--blue);
            border: 1px solid rgba(56, 189, 248, 0.25);
        }
        
        .badge-qld-qqq {
            background-color: rgba(168, 85, 247, 0.12);
            color: var(--purple);
            border: 1px solid rgba(168, 85, 247, 0.25);
        }
        
        .badge-cash {
            background-color: rgba(244, 63, 94, 0.12);
            color: var(--red);
            border: 1px solid rgba(244, 63, 94, 0.25);
        }
        
        /* Style comparison panel */
        .comparison-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .comp-card {
            background: rgba(15, 23, 42, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .comp-card-title {
            font-size: 0.95rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--accent-blue);
            border-bottom: 1px solid rgba(255,255,255,0.04);
            padding-bottom: 0.5rem;
        }
        
        .comp-rule-block {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }
        
        .comp-rule-label {
            font-size: 0.78rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        
        .comp-rule-val {
            font-size: 0.88rem;
            color: #ffffff;
            line-height: 1.4;
        }
        
        /* Scrollbar custom styling */
        .table-wrapper::-webkit-scrollbar {
            width: 6px;
        }
        .table-wrapper::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.15);
        }
        .table-wrapper::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 3px;
        }
        .table-wrapper::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.15);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>SMA Trend Regime Simulator</h1>
                <p style="color: var(--text-muted); margin-top: 0.25rem;">Interactive trigger map and transaction simulator for QQQ leveraged switching</p>
            </div>
            
            <div style="display: flex; align-items: center; gap: 1.25rem; flex-wrap: wrap;">
                <!-- Premium Strategy Toggle Segment Control -->
                <div class="strategy-toggle-wrapper">
                    <button id="btn-std" class="btn-segment active" onclick="setStrategy('standard')">Standard SMA</button>
                    <button id="btn-enh" class="btn-segment" onclick="setStrategy('enhanced')">Enhanced Quant SMA</button>
                </div>
                
                <a href="index.html" class="back-link">
                    ← Back to Dashboard
                </a>
            </div>
        </header>
        
        <!-- Regime Duration Stats (Updated dynamically by JS) -->
        <div class="stats-container" id="stats-container-dynamic">
            <!-- Filled dynamically -->
        </div>

        <!-- Interactive Date Range Selector -->
        <div class="card" style="margin-bottom: 2rem; padding: 1.25rem;">
            <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1.5rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="font-size: 1.1rem; font-weight: 700; color: #f1f5f9;">📅 Filter Date Range</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 4px;" id="data-range-label"></span>
                </div>
                
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 1.1rem;">
                    <!-- Presets -->
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">Preset:</span>
                        <select id="date-preset" style="background: #111827; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; cursor: pointer; transition: border-color 0.2s;">
                            <option value="all">Full History (2010 - 2026)</option>
                            <option value="last10">Last 10 Years</option>
                            <option value="last5">Last 5 Years</option>
                            <option value="covid">Covid Cycle (2020 - 2022)</option>
                            <option value="tech_rally">Recent Tech Rally (2023 - 2026)</option>
                            <option value="bear_defense">2022 Bear Market</option>
                            <option value="custom" disabled>Custom Range (Chart Zoom)</option>
                        </select>
                    </div>
                    
                    <!-- Date Pickers -->
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">From:</span>
                        <input type="date" id="start-date" style="background: #111827; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; transition: border-color 0.2s;">
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">To:</span>
                        <input type="date" id="end-date" style="background: #111827; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; transition: border-color 0.2s;">
                    </div>
                    
                    <button class="btn-reset" onclick="applyCustomDateFilter()" style="background: var(--accent-blue); border: none; color: #0b0f19; padding: 0.45rem 1.2rem; border-radius: 8px; font-weight: 700; font-size: 0.85rem; transition: opacity 0.2s;" onmouseover="this.style.opacity='0.9';" onmouseout="this.style.opacity='1';">Apply Filter</button>
                    <button class="btn-reset" onclick="resetDateFilter()">Reset</button>
                </div>
            </div>
        </div>

        <!-- Zoom Active Notification Banner -->
        <div class="zoom-banner" id="zoom-banner">
            <div id="zoom-banner-text" style="color: #ffffff; font-size: 0.95rem; line-height: 1.4;"></div>
            <button class="btn-reset" onclick="resetZoom()">Reset Zoom (Show All)</button>
        </div>

        <!-- Two-Column Interactive Layout -->
        <div class="dashboard-layout">
            <!-- Left Column: Interactive Plotly Chart -->
            <div class="chart-column">
                <div id="sma-chart-card" class="card" style="padding: 1rem;">
                    __PLOTLY_DIV__
                    
                    <!-- Dynamic Educational Explanations (updates on strategy toggle) -->
                    <div class="legend-card-grid" id="legend-grid-dynamic">
                        <!-- Filled dynamically -->
                    </div>
                </div>
            </div>
            
            <!-- Right Column: Interactive technical HUD (Heads Up Display) -->
            <div class="hud-column">
                <div class="card" style="height: 100%; display: flex; flex-direction: column;">
                    <div class="card-title">🔍 Regime Inspector HUD</div>
                    <div id="hud-content" style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 1rem;">
                        <div style="text-align: center; color: var(--text-muted); font-size: 0.9rem; padding: 1.5rem; line-height: 1.5;">
                            ⚡ <b>Hover over any point</b> on the chart above to inspect live technical indicators, confirmation parameters, buffer bands, and active rules!
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Side-by-Side Strategy Comparison Panel -->
        <h2 style="font-size: 1.4rem; font-weight: 800; color: #f1f5f9; margin-bottom: 1rem; letter-spacing: -0.01em;">📊 Strategy Mechanics Comparison</h2>
        <div class="comparison-grid">
            <div class="comp-card">
                <div class="comp-card-title">⚙️ Signal Decoupling</div>
                <div class="comp-rule-block">
                    <span class="comp-rule-label">Standard SMA Trend</span>
                    <span class="comp-rule-val">Calculates SMAs and triggers trades directly on whatever leveraged ETF is traded. Volatile decay and leverage resets distort the trend lines.</span>
                </div>
                <div class="comp-rule-block" style="margin-top: 0.5rem;">
                    <span class="comp-rule-label">Enhanced Quant SMA</span>
                    <span class="comp-rule-val" style="color: var(--accent-blue); font-weight: 500;">Decoupled. Computes technical indicators ONLY on clean, unleveraged 1x QQQ index, and maps the signals to leveraged assets (TQQQ/QLD/CASH).</span>
                </div>
            </div>
            <div class="comp-card">
                <div class="comp-card-title">🛡️ Buffer Bands (Hysteresis)</div>
                <div class="comp-rule-block">
                    <span class="comp-rule-label">Standard SMA Trend</span>
                    <span class="comp-rule-val">Binary. Triggers allocations immediately when price crosses an SMA line. Leads to massive "whipsaw" friction losses around flat moving averages.</span>
                </div>
                <div class="comp-rule-block" style="margin-top: 0.5rem;">
                    <span class="comp-rule-label">Enhanced Quant SMA</span>
                    <span class="comp-rule-val" style="color: var(--accent-blue); font-weight: 500;">Asymmetric Buffers. Requires price to exceed SMA by +3% (on 200 SMA) or +2% (on 50 SMA) to escalate leverage, and fall below by -1.5% or -1% to exit.</span>
                </div>
            </div>
            <div class="comp-card">
                <div class="comp-card-title"> bestätig. Confirmations</div>
                <div class="comp-rule-block">
                    <span class="comp-rule-label">Standard SMA Trend</span>
                    <span class="comp-rule-val">None. Leverages fully into TQQQ or QLD solely based on SMA crossover, even in extremely overbought tops or high-stress crash environments.</span>
                </div>
                <div class="comp-rule-block" style="margin-top: 0.5rem;">
                    <span class="comp-rule-label">Enhanced Quant SMA</span>
                    <span class="comp-rule-val" style="color: var(--accent-blue); font-weight: 500;">Multi-Signal Filter. Escalation is allowed ONLY if confirmed by: RSI < 70 (not overbought), MACD Histogram >= 0 (bullish momentum), and VIX < 25 (calm environment).</span>
                </div>
            </div>
            <div class="comp-card">
                <div class="comp-card-title">💰 Yield safe haven</div>
                <div class="comp-rule-block">
                    <span class="comp-rule-label">Standard SMA Trend</span>
                    <span class="comp-rule-val">Unleveraged QQQ. During bear markets, retreats to 1x QQQ, remaining fully exposed to major stock market declines (e.g. -50% GFC drawdown).</span>
                </div>
                <div class="comp-rule-block" style="margin-top: 0.5rem;">
                    <span class="comp-rule-label">Enhanced Quant SMA</span>
                    <span class="comp-rule-val" style="color: var(--accent-blue); font-weight: 500;">Yield CASH Sweep. Exits completely to CASH during bear regimes, compounding weekly at 4.5% yield (modeled on SGOV short-term Treasuries).</span>
                </div>
            </div>
        </div>
        
        <!-- Transaction / Trigger Event Log -->
        <div class="card" style="margin-top: 2rem;">
            <div class="card-title" id="chronicle-title-container">
                <span id="chronicle-title">⚡ Chronicle of Regime Trigger Events</span>
                <span style="font-size: 0.75rem; font-weight: 500; color: var(--text-muted);">💡 Click any row below to instantly zoom the chart above!</span>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Allocation Change</th>
                            <th>QQQ Price</th>
                            <th>50-Day SMA</th>
                            <th>200-Day SMA</th>
                            <th>Trigger Rule / Technical Confirmations</th>
                        </tr>
                    </thead>
                    <tbody id="triggers-table-body">
                        <!-- Filled dynamically -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- Zoom Interaction & Dynamic Simulator Logic JS script -->
    <script>
        // 100% robust serialized data arrays directly generated from Python
        const priceData = __JS_DATA__;
        const stdTriggers = __STD_TRIGGERS__;
        const enhTriggers = __ENH_TRIGGERS__;
        
        let currentStrategy = 'standard'; // 'standard' or 'enhanced'

        // Color maps
        const badgemap = {
            'TQQQ': 'badge-tqqq',
            'QLD': 'badge-qld',
            'QQQ': 'badge-qqq',
            'QLD/QQQ': 'badge-qld-qqq',
            'CASH': 'badge-cash'
        };

        function getBadgeClass(val) {
            return badgemap[val] || 'badge-qqq';
        }

        // Strategy Setter
        function setStrategy(strategy) {
            currentStrategy = strategy;
            
            // 1. Update Segmented Control CSS classes
            if (strategy === 'standard') {
                document.getElementById('btn-std').classList.add('active');
                document.getElementById('btn-enh').classList.remove('active');
            } else {
                document.getElementById('btn-std').classList.remove('active');
                document.getElementById('btn-enh').classList.add('active');
            }
            
            // 2. Render strategy-specific legend
            renderLegend();
            
            // 3. Update the Plotly chart background shading shapes & redrawing
            let gd = document.getElementById('sma-chart');
            if (gd && gd.layout && gd.layout.xaxis) {
                let range = gd.layout.xaxis.range;
                let startStr = range ? range[0].split(' ')[0].substring(0, 10) : priceData[0].d;
                let endStr = range ? range[1].split(' ')[0].substring(0, 10) : priceData[priceData.length - 1].d;
                
                updatePlotlyShapes(startStr, endStr);
                recalculateStatsAndChronicle(startStr, endStr);
            } else {
                let startStr = priceData[0].d;
                let endStr = priceData[priceData.length - 1].d;
                updatePlotlyShapes(startStr, endStr);
                recalculateStatsAndChronicle(startStr, endStr);
            }

            // Clear active row highlight & HUD
            resetHUD();
        }

        // Render Dynamic Guide Legend Box
        function renderLegend() {
            let html = '';
            if (currentStrategy === 'standard') {
                html = `
                <div class="legend-item">
                    <div class="legend-icon">📊</div>
                    <div>
                        <div class="legend-title">What are these lines?</div>
                        <div class="legend-desc">The <b>50-day average</b> (dashed blue) tracks the short-term price momentum, while the <b>200-day average</b> (orange) is the line in the sand separating bull and bear markets.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🟢</div>
                    <div>
                        <div class="legend-title">TQQQ (3x Speed)</div>
                        <div class="legend-desc">When prices are above both averages, the market is in a strong uptrend. We buy TQQQ to try to capture 3x the daily returns of QQQ.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🟡</div>
                    <div>
                        <div class="legend-title">QLD (2x Speed)</div>
                        <div class="legend-desc">When price falls below the short-term average but holds the 200-day average, we de-risk into QLD to safely weather temporary pullbacks.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🔴</div>
                    <div>
                        <div class="legend-title">QQQ (1x Safe)</div>
                        <div class="legend-desc">If prices plunge below the 200-day average, we exit all leverage and hold regular QQQ to protect our nest egg from devastating corrections.</div>
                    </div>
                </div>`;
            } else {
                html = `
                <div class="legend-item">
                    <div class="legend-icon">🛡️</div>
                    <div>
                        <div class="legend-title">Asymmetric Buffers</div>
                        <div class="legend-desc">Hysteresis loop prevents whipsaw losses. Price must exceed SMA_200 by <b>+3%</b> to start BULL, and drop below <b>-1.5%</b> to start BEAR. Same on SMA_50 (+2%/-1%).</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🟢</div>
                    <div>
                        <div class="legend-title">TQQQ (3x Confirmed)</div>
                        <div class="legend-desc">Regime is Strong Bull, AND technical signals (RSI < 70, MACD histogram positive, VIX < 25) are fully bullish. Max leverage speed!</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🟣</div>
                    <div>
                        <div class="legend-title">QLD/QQQ (50/50 Hedge)</div>
                        <div class="legend-desc">Strong Bull but technical indicators did not confirm (RSI overbought, bearish MACD, or high VIX stress). De-leveraged to hedge risk.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🟡</div>
                    <div>
                        <div class="legend-title">QLD (2x Confirmed)</div>
                        <div class="legend-desc">Regime is Mild Bull, AND volatility is calm (VIX < 25). Target 2x leverage to weather mild pullbacks safely.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🔵</div>
                    <div>
                        <div class="legend-title">QQQ (1x Defensive)</div>
                        <div class="legend-desc">Regime is Mild Bull, but volatility is dangerous (VIX >= 25). De-leveraged to unleveraged 1x QQQ to avoid leverage decay.</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-icon">🔴</div>
                    <div>
                        <div class="legend-title">CASH (Treasury Yield)</div>
                        <div class="legend-desc">Price breaks below SMA_200 buffer band. Tactical exit to high-yield risk-free Cash (compounding at 4.5% yield to build capital).</div>
                    </div>
                </div>`;
            }
            document.getElementById('legend-grid-dynamic').innerHTML = html;
        }

        // Reset Technical HUD to default hover instruction
        function resetHUD() {
            document.getElementById('hud-content').innerHTML = `
            <div style="text-align: center; color: var(--text-muted); font-size: 0.9rem; padding: 1.5rem; line-height: 1.5;">
                ⚡ <b>Hover over any point</b> on the chart above to inspect live technical indicators, confirmation parameters, buffer bands, and active rules!
            </div>`;
        }

        // Update Technical HUD with detailed metrics on hover
        function updateHUD(item) {
            let p = item.p;
            let s50 = item.s50;
            let s200 = item.s200;
            
            let diff50 = ((p - s50) / s50) * 100;
            let diff200 = ((p - s200) / s200) * 100;
            
            let diff50Str = (diff50 >= 0 ? '+' : '') + diff50.toFixed(1) + '%';
            let diff200Str = (diff200 >= 0 ? '+' : '') + diff200.toFixed(1) + '%';
            
            let hudHtml = '';
            
            if (currentStrategy === 'standard') {
                let isAbove200 = p > s200;
                let isAbove50 = p > s50;
                let alloc = isAbove50 && isAbove200 ? 'TQQQ' : (isAbove200 ? 'QLD' : 'QQQ');
                let allocSubText = alloc === 'TQQQ' ? '3x Leveraged Speed' : (alloc === 'QLD' ? '2x Leveraged Speed' : '1x Defensive Safe');
                let reasonText = alloc === 'TQQQ' 
                    ? "🟢 Price is above both averages. Trend is strongly bullish, maximizing leverage speed in 3x TQQQ."
                    : (alloc === 'QLD' ? "🟡 Price is below 50-day average but above 200-day average. Mild trend, holding 2x QLD." : "🔴 Price is below 200-day average. Bear trend, holding defensive 1x QQQ.");
                
                hudHtml = `
                <div style="display: flex; flex-direction: column; gap: 0.8rem;">
                    <!-- Date & Price -->
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                        <span style="font-weight: 800; font-size: 1.2rem; color: #ffffff;">${item.d}</span>
                        <span style="font-family: monospace; font-size: 1.2rem; font-weight: 800; color: var(--accent-blue);">$${p.toFixed(2)}</span>
                    </div>
                    
                    <!-- SMAs comparison -->
                    <div style="display: flex; flex-direction: column; gap: 0.4rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                            <span style="color: var(--text-muted); font-weight: 500;">50-Day SMA:</span>
                            <span style="font-family: monospace; color: #ffffff; font-weight: 600;">$${s50.toFixed(2)} (<span style="color: ${diff50 >= 0 ? 'var(--green)' : 'var(--red)'}">${diff50Str}</span>)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                            <span style="color: var(--text-muted); font-weight: 500;">200-Day SMA:</span>
                            <span style="font-family: monospace; color: #ffffff; font-weight: 600;">$${s200.toFixed(2)} (<span style="color: ${diff200 >= 0 ? 'var(--green)' : 'var(--red)'}">${diff200Str}</span>)</span>
                        </div>
                    </div>
                    
                    <div style="border-bottom: 1px solid var(--border-color); margin: 0.2rem 0;"></div>
                    
                    <!-- Strategy Parameters -->
                    <div style="font-size: 0.85rem; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 0.05em;">
                        Standard SMA Crossover Rules:
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        <div class="hud-item ${isAbove200 ? 'status-ok' : 'status-fail'}">
                            <span style="font-weight: 500;">📈 Above 200 SMA (Bull Regime)</span>
                            <span style="font-weight: 700;">${isAbove200 ? '✅ YES' : '❌ NO'}</span>
                        </div>
                        <div class="hud-item ${isAbove50 ? 'status-ok' : 'status-neutral'}">
                            <span style="font-weight: 500;">⚡ Above 50 SMA (Strong Bull)</span>
                            <span style="font-weight: 700; color: ${isAbove50 ? 'var(--green)' : 'var(--yellow)'}">${isAbove50 ? '🟢 YES' : '🟡 NO'}</span>
                        </div>
                    </div>
                    
                    <div style="border-bottom: 1px solid var(--border-color); margin: 0.2rem 0;"></div>
                    
                    <!-- Result -->
                    <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                        <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Active Allocation:</span>
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.25rem;">
                            <span class="badge ${getBadgeClass(alloc)}">${alloc}</span>
                            <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted);">${allocSubText}</span>
                        </div>
                    </div>
                    
                    <!-- Reason -->
                    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-color); border-radius: 10px; padding: 0.75rem; font-size: 0.8rem; line-height: 1.4; color: #cbd5e1;">
                        ${reasonText}
                    </div>
                </div>`;
            } else {
                let regimeStr = item.enh_reg;
                let regimeLabel = regimeStr === 'BULL_STRONG' ? '🟢 BULL STRONG' : (regimeStr === 'BULL_MILD' ? '🟡 BULL MILD' : '🔴 BEAR MARKET');
                let regimeClass = regimeStr === 'BULL_STRONG' ? 'status-ok' : (regimeStr === 'BULL_MILD' ? 'status-neutral' : 'status-fail');
                
                let isRsiSafe = item.rsi < 70;
                let isMacdSafe = item.macd_h >= 0;
                let isVixSafe = item.vix < 25;
                
                let alloc = item.enh_all;
                let allocSubText = alloc === 'TQQQ' ? '3x Confirmed Leverage' 
                    : (alloc === 'QLD/QQQ' ? '50/50 Whipsaw Buffer'
                    : (alloc === 'QLD' ? '2x Confirmed Leverage'
                    : (alloc === 'QQQ' ? '1x High-Stress Defensive' : 'SGOV Safe CASH Sweep')));
                
                hudHtml = `
                <div style="display: flex; flex-direction: column; gap: 0.8rem;">
                    <!-- Date & Price -->
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                        <span style="font-weight: 800; font-size: 1.2rem; color: #ffffff;">${item.d}</span>
                        <span style="font-family: monospace; font-size: 1.2rem; font-weight: 800; color: var(--accent-blue);">$${p.toFixed(2)}</span>
                    </div>
                    
                    <!-- SMAs comparison -->
                    <div style="display: flex; flex-direction: column; gap: 0.4rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                            <span style="color: var(--text-muted); font-weight: 500;">50-Day SMA:</span>
                            <span style="font-family: monospace; color: #ffffff; font-weight: 600;">$${s50.toFixed(2)} (<span style="color: ${diff50 >= 0 ? 'var(--green)' : 'var(--red)'}">${diff50Str}</span>)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                            <span style="color: var(--text-muted); font-weight: 500;">200-Day SMA:</span>
                            <span style="font-family: monospace; color: #ffffff; font-weight: 600;">$${s200.toFixed(2)} (<span style="color: ${diff200 >= 0 ? 'var(--green)' : 'var(--red)'}">${diff200Str}</span>)</span>
                        </div>
                    </div>
                    
                    <div style="border-bottom: 1px solid var(--border-color); margin: 0.2rem 0;"></div>
                    
                    <!-- Strategy Parameters -->
                    <div style="font-size: 0.85rem; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 0.05em;">
                        Enhanced Quant SMA checklist:
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 0.45rem;">
                        <div class="hud-item ${regimeClass}">
                            <span style="font-weight: 500;">🛡️ Active Hysteresis Regime</span>
                            <span style="font-weight: 700;">${regimeLabel}</span>
                        </div>
                        <div class="hud-item ${isRsiSafe ? 'status-ok' : 'status-fail'}">
                            <span style="font-weight: 500;">📉 RSI (14) = ${item.rsi.toFixed(1)} (&lt; 70)</span>
                            <span style="font-weight: 700;">${isRsiSafe ? '✅ SAFE' : '⚠️ OVERBOUGHT'}</span>
                        </div>
                        <div class="hud-item ${isMacdSafe ? 'status-ok' : 'status-fail'}">
                            <span style="font-weight: 500;">📊 MACD Histogram = ${item.macd_h.toFixed(2)} (&gt;= 0)</span>
                            <span style="font-weight: 700;">${isMacdSafe ? '✅ BULLISH' : '❌ BEARISH'}</span>
                        </div>
                        <div class="hud-item ${isVixSafe ? 'status-ok' : 'status-fail'}">
                            <span style="font-weight: 500;">⚠️ VIX Index = ${item.vix.toFixed(1)} (&lt; 25)</span>
                            <span style="font-weight: 700;">${isVixSafe ? '✅ SAFE' : '🔥 HIGH STRESS'}</span>
                        </div>
                    </div>
                    
                    <div style="border-bottom: 1px solid var(--border-color); margin: 0.2rem 0;"></div>
                    
                    <!-- Result -->
                    <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                        <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Active Allocation:</span>
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.25rem;">
                            <span class="badge ${getBadgeClass(alloc)}">${alloc}</span>
                            <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted);">${allocSubText}</span>
                        </div>
                    </div>
                    
                    <!-- Reason -->
                    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-color); border-radius: 10px; padding: 0.75rem; font-size: 0.8rem; line-height: 1.4; color: #cbd5e1;">
                        ${item.enh_reason}
                    </div>
                </div>`;
            }
            
            document.getElementById('hud-content').innerHTML = hudHtml;
        }
        
        function getStdReason(item) {
            let p = item.p;
            let s50 = item.s50;
            let s200 = item.s200;
            if (p > s50 && p > s200) {
                return "🟢 <b>Strong Bull Market:</b> Price crossed above both short-term (50-day) and long-term (200-day) averages. Maximize speed in TQQQ!";
            } else if (p > s200) {
                return "🟡 <b>Warning Signal:</b> Price dipped below short-term (50-day) average, but remains above long-term. Safely downshift to QLD.";
            } else {
                return "🔴 <b>Bear Market / Defense:</b> Price fell below long-term (200-day) average. Switch to safe 1x QQQ to avoid massive leverage losses.";
            }
        }

        // Plotly Shapes generator dynamically (saves massive HTML size and is extremely fast)
        function updatePlotlyShapes(startStr, endStr) {
            let shapes = [];
            let filteredData = priceData.filter(item => item.d >= startStr && item.d <= endStr);
            if (filteredData.length === 0) return;
            
            let blockStart = filteredData[0].d;
            let blockType = currentStrategy === 'standard' ? filteredData[0].std_reg : filteredData[0].enh_all;
            
            for (let i = 1; i < filteredData.length; i++) {
                let item = filteredData[i];
                let currentType = currentStrategy === 'standard' ? item.std_reg : item.enh_all;
                
                if (currentType !== blockType) {
                    shapes.push(makeShape(blockStart, item.d, blockType));
                    blockStart = item.d;
                    blockType = currentType;
                }
            }
            shapes.push(makeShape(blockStart, filteredData[filteredData.length - 1].d, blockType));
            
            Plotly.relayout('sma-chart', { shapes: shapes });
        }
        
        function makeShape(x0, x1, type) {
            const colors = {
                'TQQQ': 'rgba(16, 185, 129, 0.06)',    // Green
                'QLD': 'rgba(245, 158, 11, 0.06)',     // Yellow
                'QQQ': currentStrategy === 'standard' ? 'rgba(244, 63, 94, 0.06)' : 'rgba(56, 189, 248, 0.06)', // Red in Std, Sky Blue in Enh
                'QLD/QQQ': 'rgba(168, 85, 247, 0.06)', // Purple
                'CASH': 'rgba(244, 63, 94, 0.06)'     // Red (Cash Sweep)
            };
            return {
                type: 'rect',
                xref: 'x',
                yref: 'paper',
                x0: x0,
                x1: x1,
                y0: 0,
                y1: 1,
                fillcolor: colors[type] || 'transparent',
                opacity: 1.0,
                line: { width: 0 },
                layer: 'below'
            };
        }

        // Dynamic stats calculator & Dynamic triggers table renderer
        function recalculateStatsAndChronicle(startStr, endStr) {
            let filteredData = priceData.filter(item => item.d >= startStr && item.d <= endStr);
            let total = filteredData.length;
            if (total === 0) total = 1;
            
            // 1. Calculate Stats
            let counts = {};
            filteredData.forEach(item => {
                let key = currentStrategy === 'standard' ? item.std_reg : item.enh_all;
                counts[key] = (counts[key] || 0) + 1;
            });
            
            let statsHtml = '';
            if (currentStrategy === 'standard') {
                const states = [
                    { key: 'TQQQ', label: '🟢 Time in TQQQ (Strong Bull)', color: 'var(--green)' },
                    { key: 'QLD', label: '🟡 Time in QLD (Mild Warning)', color: 'var(--yellow)' },
                    { key: 'QQQ', label: '🔴 Time in QQQ (Bear Defense)', color: 'var(--red)' }
                ];
                states.forEach(s => {
                    let count = counts[s.key] || 0;
                    let pct = (count / total) * 100;
                    statsHtml += `
                    <div class="stat-card">
                        <div class="stat-label">${s.label}</div>
                        <div class="stat-value">${count.toLocaleString()} Days <span style="font-size: 0.55em; color: ${s.color}; font-weight: 700;">(${pct.toFixed(1)}%)</span></div>
                        <div class="stat-bar-container">
                            <div class="stat-bar" style="width: ${pct}%; background-color: ${s.color};"></div>
                        </div>
                    </div>`;
                });
            } else {
                const states = [
                    { key: 'TQQQ', label: '🟢 Time in TQQQ (Strong Confirmed)', color: 'var(--green)' },
                    { key: 'QLD/QQQ', label: '🟣 Time in QLD/QQQ (Strong Buffer)', color: 'var(--purple)' },
                    { key: 'QLD', label: '🟡 Time in QLD (Mild Confirmed)', color: 'var(--yellow)' },
                    { key: 'QQQ', label: '🔵 Time in QQQ (Mild Defensive)', color: 'var(--blue)' },
                    { key: 'CASH', label: '🔴 Time in CASH (Yield Sweep)', color: 'var(--red)' }
                ];
                states.forEach(s => {
                    let count = counts[s.key] || 0;
                    let pct = (count / total) * 100;
                    statsHtml += `
                    <div class="stat-card">
                        <div class="stat-label">${s.label}</div>
                        <div class="stat-value">${count.toLocaleString()} Days <span style="font-size: 0.55em; color: ${s.color}; font-weight: 700;">(${pct.toFixed(1)}%)</span></div>
                        <div class="stat-bar-container">
                            <div class="stat-bar" style="width: ${pct}%; background-color: ${s.color};"></div>
                        </div>
                    </div>`;
                });
            }
            document.getElementById('stats-container-dynamic').innerHTML = statsHtml;
            
            // 2. Render Triggers Table
            let triggers = currentStrategy === 'standard' ? stdTriggers : enhTriggers;
            let tableHtml = '';
            let visibleCount = 0;
            
            for (let i = triggers.length - 1; i >= 0; i--) {
                let t = triggers[i];
                if (t.Date >= startStr && t.Date <= endStr) {
                    visibleCount++;
                    let badgeClass = getBadgeClass(t.To);
                    let actionText = t.From === 'None' ? `Initial: ${t.To}` : `${t.From} ➡️ ${t.To}`;
                    let jsReason = t.Reason.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    
                    tableHtml += `
                    <tr id="row-${t.Date}" onclick="zoomToTrigger('${t.Date}', '${t.To}', '${jsReason}')" style="cursor: pointer;">
                        <td style="font-weight: 600; color: #f8fafc;">
                            ${t.Date}
                            <span class="zoom-helper">🔍 Zoom</span>
                        </td>
                        <td><span class="badge ${badgeClass}">${actionText}</span></td>
                        <td style="color: #cbd5e1; font-family: monospace;">$${t.Price.toFixed(2)}</td>
                        <td style="color: #94a3b8; font-family: monospace;">$${t.SMA_50.toFixed(2)}</td>
                        <td style="color: #94a3b8; font-family: monospace;">$${t.SMA_200.toFixed(2)}</td>
                        <td style="color: #cbd5e1; font-size: 0.9em;">${t.Reason}</td>
                    </tr>`;
                }
            }
            
            document.getElementById('triggers-table-body').innerHTML = tableHtml;
            document.getElementById('chronicle-title').innerHTML = `⚡ Chronicle of Regime Trigger Events (${visibleCount} Changes in Range)`;
        }

        // Dynamic y-axis scaling based on visible range (with 8% padding)
        function updateYAxisRange(startStr, endStr) {
            let cleanStart = startStr.substring(0, 10);
            let cleanEnd = endStr.substring(0, 10);
            
            let minVal = Infinity;
            let maxVal = -Infinity;
            
            for (let i = 0; i < priceData.length; i++) {
                let item = priceData[i];
                if (item.d >= cleanStart && item.d <= cleanEnd) {
                    let p = item.p;
                    let s50 = item.s50;
                    let s200 = item.s200;
                    
                    if (p !== undefined && p !== null && !isNaN(p)) {
                        if (p < minVal) minVal = p;
                        if (p > maxVal) maxVal = p;
                    }
                    if (s50 !== undefined && s50 !== null && !isNaN(s50)) {
                        if (s50 < minVal) minVal = s50;
                        if (s50 > maxVal) maxVal = s50;
                    }
                    if (s200 !== undefined && s200 !== null && !isNaN(s200)) {
                        if (s200 < minVal) minVal = s200;
                        if (s200 > maxVal) maxVal = s200;
                    }
                }
            }
            
            if (minVal !== Infinity && maxVal !== -Infinity) {
                let padding = (maxVal - minVal) * 0.08;
                if (padding === 0) padding = 10;
                return [minVal - padding, maxVal + padding];
            }
            return null;
        }

        function zoomToTrigger(dateStr, regime, reasonClean) {
            // Zoom range: 35 days before, 35 days after trigger date
            let parts = dateStr.split('-');
            let year = parseInt(parts[0], 10);
            let month = parseInt(parts[1], 10) - 1;
            let day = parseInt(parts[2], 10);
            
            let triggerDate = new Date(year, month, day);
            let start = new Date(year, month, day - 35);
            let end = new Date(year, month, day + 35);
            
            let formatDate = function(d) {
                let y = d.getFullYear();
                let m = String(d.getMonth() + 1).padStart(2, '0');
                let dd = String(d.getDate()).padStart(2, '0');
                return y + '-' + m + '-' + dd;
            };
            
            let startStr = formatDate(start);
            let endStr = formatDate(end);
            
            let yRange = updateYAxisRange(startStr, endStr);
            
            let updateObj = {
                'xaxis.range': [startStr, endStr]
            };
            
            if (yRange) {
                updateObj['yaxis.range'] = yRange;
                updateObj['yaxis.autorange'] = false;
            }
            
            Plotly.relayout('sma-chart', updateObj);
            
            document.getElementById('sma-chart-card').scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
            
            // Update and show active banner details
            let banner = document.getElementById('zoom-banner');
            let bannerText = document.getElementById('zoom-banner-text');
            
            const colors = {
                'TQQQ': 'var(--green)',
                'QLD': 'var(--yellow)',
                'QQQ': 'var(--blue)',
                'QLD/QQQ': 'var(--purple)',
                'CASH': 'var(--red)'
            };
            let color = colors[regime] || 'var(--accent-blue)';
            
            bannerText.innerHTML = `🔍 <b>Inspecting trigger on ${dateStr}</b>: ${reasonClean}`;
            banner.style.borderLeft = `4px solid ${color}`;
            banner.style.display = 'flex';
            
            // Highlight the clicked row
            let rows = document.querySelectorAll('tbody tr');
            rows.forEach(r => {
                r.classList.remove('active-row');
            });
            
            let clickedRow = document.getElementById('row-' + dateStr);
            if (clickedRow) {
                clickedRow.classList.add('active-row');
            }

            // Sync indicators HUD
            let matchedItem = priceData.find(d => d.d === dateStr);
            if (matchedItem) {
                updateHUD(matchedItem);
            }
        }
        
        function resetZoom() {
            Plotly.relayout('sma-chart', {
                'xaxis.range': null,
                'yaxis.range': null,
                'yaxis.autorange': true
            });
            
            let banner = document.getElementById('zoom-banner');
            banner.style.display = 'none';
            
            let rows = document.querySelectorAll('tbody tr');
            rows.forEach(r => {
                r.classList.remove('active-row');
            });
            
            resetDateFilter();
            resetHUD();
        }

        // Custom Date Range Filter Functions
        function applyCustomDateFilter() {
            let startStr = document.getElementById('start-date').value;
            let endStr = document.getElementById('end-date').value;
            
            if (!startStr || !endStr) return;
            if (startStr > endStr) {
                alert("Start date cannot be after end date.");
                return;
            }
            
            let yRange = updateYAxisRange(startStr, endStr);
            let gd = document.getElementById('sma-chart');
            if (gd) {
                let updateObj = {
                    'xaxis.range': [startStr, endStr]
                };
                if (yRange) {
                    updateObj['yaxis.range'] = yRange;
                    updateObj['yaxis.autorange'] = false;
                }
                Plotly.relayout(gd, updateObj);
            }
            
            updatePlotlyShapes(startStr, endStr);
            recalculateStatsAndChronicle(startStr, endStr);
        }
        
        function resetDateFilter() {
            const minDate = priceData[0].d;
            const maxDate = priceData[priceData.length - 1].d;
            
            document.getElementById('start-date').value = minDate;
            document.getElementById('end-date').value = maxDate;
            document.getElementById('date-preset').value = 'all';
            
            let gd = document.getElementById('sma-chart');
            if (gd) {
                Plotly.relayout(gd, {
                    'xaxis.range': null,
                    'yaxis.range': null,
                    'yaxis.autorange': true
                });
            }
            
            updatePlotlyShapes(minDate, maxDate);
            recalculateStatsAndChronicle(minDate, maxDate);
        }
        
        function handlePresetChange() {
            const preset = document.getElementById('date-preset').value;
            const maxDateObj = new Date(priceData[priceData.length - 1].d);
            let startStr = priceData[0].d;
            let endStr = priceData[priceData.length - 1].d;
            
            if (preset === 'last5') {
                let start = new Date(maxDateObj);
                start.setFullYear(start.getFullYear() - 5);
                startStr = start.toISOString().split('T')[0];
            } else if (preset === 'last10') {
                let start = new Date(maxDateObj);
                start.setFullYear(start.getFullYear() - 10);
                startStr = start.toISOString().split('T')[0];
            } else if (preset === 'covid') {
                startStr = '2020-01-01';
                endStr = '2022-06-30';
            } else if (preset === 'tech_rally') {
                startStr = '2023-01-01';
                endStr = priceData[priceData.length - 1].d;
            } else if (preset === 'bear_defense') {
                startStr = '2022-01-01';
                endStr = '2022-12-31';
            }
            
            if (startStr < priceData[0].d) startStr = priceData[0].d;
            
            document.getElementById('start-date').value = startStr;
            document.getElementById('end-date').value = endStr;
            
            applyCustomDateFilter();
        }

        // Initialize document & event handlers
        document.addEventListener("DOMContentLoaded", function() {
            let gd = document.getElementById('sma-chart');
            if (gd) {
                // Plotly hover handler
                gd.on('plotly_hover', function(data) {
                    let point = data.points[0];
                    let dateStr = point.x;
                    let matchedItem = priceData.find(d => d.d === dateStr);
                    if (matchedItem) {
                        updateHUD(matchedItem);
                    }
                });
                
                // Plotly click handler (freezes HUD on selection)
                gd.on('plotly_click', function(data) {
                    let point = data.points[0];
                    let dateStr = point.x;
                    let matchedItem = priceData.find(d => d.d === dateStr);
                    if (matchedItem) {
                        updateHUD(matchedItem);
                        
                        // Highlight corresponding row if it exists
                        let clickedRow = document.getElementById('row-' + dateStr);
                        if (clickedRow) {
                            let rows = document.querySelectorAll('tbody tr');
                            rows.forEach(r => r.classList.remove('active-row'));
                            clickedRow.classList.add('active-row');
                            clickedRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }
                });

                // Plotly range selection sync
                gd.on('plotly_relayout', function(eventData) {
                    if (eventData['xaxis.range[0]'] && eventData['xaxis.range[1]']) {
                        let startStr = eventData['xaxis.range[0]'].split(' ')[0].substring(0, 10);
                        let endStr = eventData['xaxis.range[1]'].split(' ')[0].substring(0, 10);
                        
                        document.getElementById('start-date').value = startStr;
                        document.getElementById('end-date').value = endStr;
                        document.getElementById('date-preset').value = 'custom';
                        
                        updatePlotlyShapes(startStr, endStr);
                        recalculateStatsAndChronicle(startStr, endStr);
                    } else if (eventData['xaxis.autorange'] === true) {
                        resetDateFilter();
                    }
                });
            }
            
            // Set up start and end dates
            const minDate = priceData[0].d;
            const maxDate = priceData[priceData.length - 1].d;
            
            document.getElementById('start-date').min = minDate;
            document.getElementById('start-date').max = maxDate;
            document.getElementById('end-date').min = minDate;
            document.getElementById('end-date').max = maxDate;
            
            document.getElementById('start-date').value = minDate;
            document.getElementById('end-date').value = maxDate;
            
            document.getElementById('data-range-label').textContent = minDate + " to " + maxDate;
            document.getElementById('date-preset').addEventListener('change', handlePresetChange);
            
            // Load Standard strategy by default
            setStrategy('standard');
        });
    </script>
</body>
</html>
"""
    
    # Fill placeholders in the HTML
    html_content = html_template.replace("__PLOTLY_DIV__", plotly_div) \
                                .replace("__JS_DATA__", js_data_json) \
                                .replace("__STD_TRIGGERS__", std_triggers_json) \
                                .replace("__ENH_TRIGGERS__", enh_triggers_json)
                                
    # 9. Save the compiled file
    print(f"Saving compiled HTML report to {OUTPUT_HTML}...")
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print("\n" + "="*60)
    print("SUCCESS: Simulator HTML generated successfully!")
    print(f"File Path: {OUTPUT_HTML}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_simulation()
