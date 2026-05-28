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
    # Load template from file instead of hardcoded massive string
    TEMPLATE_PATH = os.path.join(BASE_DIR, "tools", "templates", "simulator_template.html")
    if not os.path.exists(TEMPLATE_PATH):
        # Compatibility fallback if run from a different CWD
        TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "simulator_template.html")
    
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_template = f.read()
    
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
