import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from datetime import datetime

# Define file paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "etf_prices.csv")
OUTPUT_HTML = os.path.join(BASE_DIR, "dashboard", "sma_simulator.html")

def run_simulation():
    print("="*60)
    print("              SMA TREND REGIME VISUAL SIMULATOR")
    print("="*60)
    
    # 1. Load Data
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found. Please run backtest or download script first.")
        return
        
    print(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE, index_col=0, parse_dates=True, header=[0, 1])
    
    # Extract QQQ Close price
    qqq = df['Close']['QQQ'].dropna()
    print(f"Loaded {len(qqq)} historical daily bars for QQQ ({qqq.index[0].date()} to {qqq.index[-1].date()})")
    
    # 2. Calculate Indicators
    print("Calculating 50-day and 200-day Simple Moving Averages...")
    sma_50 = qqq.rolling(window=50, min_periods=50).mean()
    sma_200 = qqq.rolling(window=200, min_periods=200).mean()
    
    # Combine into a single clean DataFrame
    sim_df = pd.DataFrame({
        'Price': qqq,
        'SMA_50': sma_50,
        'SMA_200': sma_200
    }).dropna()
    
    print(f"Simulation window after SMA warm-up: {len(sim_df)} days ({sim_df.index[0].date()} to {sim_df.index[-1].date()})")
    
    # 3. Determine Regimes
    regimes = []
    for idx, row in sim_df.iterrows():
        p, s50, s200 = row['Price'], row['SMA_50'], row['SMA_200']
        if p > s50 and p > s200:
            regimes.append('TQQQ')  # Strong Uptrend
        elif p > s200:
            regimes.append('QLD')   # Mild Uptrend / Warning
        else:
            regimes.append('QQQ')   # Downtrend / Defense
            
    sim_df['Regime'] = regimes
    
    # 4. Detect Trigger Events (Regime Changes)
    print("Detecting trigger events (regime changes)...")
    triggers = []
    current_regime = sim_df['Regime'].iloc[0]
    
    # Track regime stats
    stats = {'TQQQ': 0, 'QLD': 0, 'QQQ': 0}
    
    # Record starting point
    triggers.append({
        'Date': sim_df.index[0].strftime('%Y-%m-%d'),
        'Price': float(sim_df['Price'].iloc[0]),
        'SMA_50': float(sim_df['SMA_50'].iloc[0]),
        'SMA_200': float(sim_df['SMA_200'].iloc[0]),
        'From': 'None',
        'To': current_regime,
        'Reason': 'Simulation started. Initial regime calculated.'
    })
    
    for i in range(1, len(sim_df)):
        date = sim_df.index[i]
        p = sim_df['Price'].iloc[i]
        s50 = sim_df['SMA_50'].iloc[i]
        s200 = sim_df['SMA_200'].iloc[i]
        regime = sim_df['Regime'].iloc[i]
        
        stats[regime] += 1
        
        if regime != current_regime:
            # Determine beginner-friendly reason
            reason = ""
            if regime == 'TQQQ':
                reason = "🟢 <b>Strong Bull Market:</b> Price crossed above both short-term (50-day) and long-term (200-day) averages. Maximize speed in TQQQ!"
            elif regime == 'QLD':
                if current_regime == 'TQQQ':
                    reason = "🟡 <b>Warning Signal:</b> Price dipped below short-term (50-day) average, but remains above long-term. Safely downshift to QLD."
                else:
                    reason = "🟡 <b>Early Recovery:</b> Price climbed back above long-term (200-day) average, but remains below short-term. Move to QLD."
            elif regime == 'QQQ':
                reason = "🔴 <b>Bear Market / Defense:</b> Price fell below long-term (200-day) average. Switch to safe 1x QQQ to avoid massive leverage losses."
                
            triggers.append({
                'Date': date.strftime('%Y-%m-%d'),
                'Price': float(p),
                'SMA_50': float(s50),
                'SMA_200': float(s200),
                'From': current_regime,
                'To': regime,
                'Reason': reason
            })
            current_regime = regime
            
    print(f"Total Trigger Events (Regime Changes): {len(triggers) - 1}")
    
    # 5. Build Contiguous Shading Blocks for Chart
    blocks = []
    block_start = sim_df.index[0]
    block_regime = sim_df['Regime'].iloc[0]
    
    for i in range(1, len(sim_df)):
        date = sim_df.index[i]
        regime = sim_df['Regime'].iloc[i]
        if regime != block_regime:
            blocks.append({
                'Start': block_start.strftime('%Y-%m-%d'),
                'End': date.strftime('%Y-%m-%d'),
                'Regime': block_regime
            })
            block_start = date
            block_regime = regime
    blocks.append({
        'Start': block_start.strftime('%Y-%m-%d'),
        'End': sim_df.index[-1].strftime('%Y-%m-%d'),
        'Regime': block_regime
    })
    
    # 6. Generate Plotly Chart
    print("\nGenerating interactive Plotly chart...")
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
        line=dict(color='#3498db', width=1.5, dash='dash'),
        hovertemplate='50 SMA: $%{y:.2f}<extra></extra>'
    ))
    
    # SMA 200 trace
    fig.add_trace(go.Scatter(
        x=sim_df.index, y=sim_df['SMA_200'],
        mode='lines',
        name='200-day SMA (Long-term)',
        line=dict(color='#e67e22', width=1.5),
        hovertemplate='200 SMA: $%{y:.2f}<extra></extra>'
    ))
    
    # Add vertical shading blocks
    colors = {
        'TQQQ': 'rgba(46, 204, 113, 0.08)',  # Light Green
        'QLD': 'rgba(241, 196, 15, 0.08)',   # Light Yellow
        'QQQ': 'rgba(231, 76, 60, 0.08)'     # Light Red
    }
    
    for b in blocks:
        fig.add_vrect(
            x0=b['Start'], x1=b['End'],
            fillcolor=colors[b['Regime']],
            opacity=1.0,
            layer="below",
            line_width=0
        )
        
    # Styling the Plotly Layout
    fig.update_layout(
        title={
            'text': 'QQQ SMA Trend Regime Simulation Map',
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': dict(size=22, color='#ffffff')
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
        margin=dict(l=40, r=40, t=100, b=40),
        height=600
    )
    
    # Convert Plotly graph to HTML snippet with custom div_id
    plotly_div = fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='sma-chart')
    
    # Generate JSON string for Javascript data array (100% robust, browser-compatible date matching)
    js_data = []
    for idx, row in sim_df.iterrows():
        js_data.append({
            'd': idx.strftime('%Y-%m-%d'),
            'p': float(row['Price']),
            's50': float(row['SMA_50']),
            's200': float(row['SMA_200'])
        })
    js_data_json = json.dumps(js_data)
    
    # 7. Generate Full Self-Contained Dashboard HTML
    print("Assembling final interactive HTML report...")
    
    # Calculate stats percentages
    total_days = len(sim_df)
    percent_tqqq = (stats['TQQQ'] / total_days) * 100
    percent_qld = (stats['QLD'] / total_days) * 100
    percent_qqq = (stats['QQQ'] / total_days) * 100
    
    # Build Triggers HTML Table Rows
    table_rows = []
    # Reverse so most recent triggers are at the top
    for t in reversed(triggers):
        badge_class = ""
        action_text = ""
        if t['To'] == 'TQQQ':
            badge_class = "badge-tqqq"
            action_text = f"{t['From']} ➡️ TQQQ (3x)"
        elif t['To'] == 'QLD':
            badge_class = "badge-qld"
            action_text = f"{t['From']} ➡️ QLD (2x)"
        elif t['To'] == 'QQQ':
            badge_class = "badge-qqq"
            action_text = f"{t['From']} ➡️ QQQ (1x)"
            
        if t['From'] == 'None':
            action_text = f"Initial: {t['To']}"
            
        # Clean reason for JS single-quote safety
        js_reason = t['Reason'].replace("'", "\\'").replace('"', '&quot;')
            
        row_html = f"""
        <tr id="row-{t['Date']}" onclick="zoomToTrigger('{t['Date']}', '{t['To']}', '{js_reason}')" style="cursor: pointer;">
            <td style="font-weight: 600; color: #f8fafc;">
                {t['Date']}
                <span class="zoom-helper">🔍 Click to zoom</span>
            </td>
            <td><span class="badge {badge_class}">{action_text}</span></td>
            <td style="color: #cbd5e1; font-family: monospace;">${t['Price']:.2f}</td>
            <td style="color: #94a3b8; font-family: monospace;">${t['SMA_50']:.2f}</td>
            <td style="color: #94a3b8; font-family: monospace;">${t['SMA_200']:.2f}</td>
            <td style="color: #cbd5e1; font-size: 0.9em;">{t['Reason']}</td>
        </tr>
        """
        table_rows.append(row_html)
        
    table_rows_joined = "\n".join(table_rows)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMA Trend Regime Simulator</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-main: #0b0f19;
            --bg-card: rgba(30, 41, 59, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --green: #2ecc71;
            --yellow: #f1c40f;
            --red: #e74c3c;
            --accent-blue: #38bdf8;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        
        body {{
            background-color: var(--bg-main);
            color: var(--text-main);
            padding: 2rem;
            min-height: 100vh;
            background-image: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(244, 63, 94, 0.05) 0%, transparent 40%);
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}
        
        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .back-link {{
            color: #38bdf8;
            text-decoration: none;
            font-weight: 500;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: color 0.2s;
        }}
        
        .back-link:hover {{
            color: #818cf8;
        }}
        
        /* Grid Layout */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }}
        
        /* Card Styles */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            position: relative;
        }}
        
        .card-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        /* Stats Flexbox */
        .stats-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: rgba(30, 41, 59, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        
        .stat-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .stat-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #ffffff;
        }}
        
        .stat-bar-container {{
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 0.5rem;
        }}
        
        .stat-bar {{
            height: 100%;
            border-radius: 3px;
        }}
        
        /* Interactive Row Clicking */
        tbody tr {{
            transition: all 0.2s ease-in-out;
        }}
        tbody tr:hover {{
            background-color: rgba(56, 189, 248, 0.08) !important;
            transform: translateX(4px);
        }}
        tbody tr:hover .zoom-helper {{
            opacity: 1;
            transform: translateX(0);
        }}
        
        .active-row td {{
            background-color: rgba(56, 189, 248, 0.12) !important;
            border-top: 1px solid rgba(56, 189, 248, 0.3) !important;
            border-bottom: 1px solid rgba(56, 189, 248, 0.3) !important;
            font-weight: 500;
        }}
        
        .zoom-helper {{
            display: inline-block;
            font-size: 0.75rem;
            color: var(--accent-blue);
            background: rgba(56, 189, 248, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
            opacity: 0;
            transform: translateX(-4px);
            transition: all 0.2s ease;
        }}
        
        /* Floating Action Banner */
        .zoom-banner {{
            display: none;
            align-items: center;
            justify-content: space-between;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(8px);
            animation: slideIn 0.3s ease;
        }}
        
        @keyframes slideIn {{
            from {{ transform: translateY(-10px); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}
        
        .btn-reset {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #ffffff;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .btn-reset:hover {{
            background: #ffffff;
            color: #000000;
        }}

        /* Stock Legend Card */
        .legend-card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
        }}
        .legend-item {{
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
        }}
        .legend-icon {{
            font-size: 1.25rem;
            line-height: 1.2;
        }}
        .legend-title {{
            font-weight: 600;
            font-size: 0.95rem;
            color: #f1f5f9;
            margin-bottom: 0.25rem;
        }}
        .legend-desc {{
            font-size: 0.85rem;
            color: var(--text-muted);
            line-height: 1.4;
        }}

        /* Table Styles */
        .table-wrapper {{
            max-height: 600px;
            overflow-y: auto;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        
        th {{
            background-color: rgba(15, 23, 42, 0.8);
            padding: 1rem;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 1px solid var(--border-color);
        }}
        
        td {{
            padding: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            font-size: 0.95rem;
        }}
        
        /* Badges */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .badge-tqqq {{
            background-color: rgba(46, 204, 113, 0.15);
            color: var(--green);
            border: 1px solid rgba(46, 204, 113, 0.3);
        }}
        
        .badge-qld {{
            background-color: rgba(241, 196, 15, 0.15);
            color: var(--yellow);
            border: 1px solid rgba(241, 196, 15, 0.3);
        }}
        
        .badge-qqq {{
            background-color: rgba(231, 76, 60, 0.15);
            color: var(--red);
            border: 1px solid rgba(231, 76, 60, 0.3);
        }}
        
        /* Scrollbar custom styling */
        .table-wrapper::-webkit-scrollbar {{
            width: 8px;
        }}
        .table-wrapper::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.1);
        }}
        .table-wrapper::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}
        .table-wrapper::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>SMA Trend Regime Simulator</h1>
                <p style="color: var(--text-muted); margin-top: 0.25rem;">Interactive trigger map and transaction simulator for QQQ leveraged switching</p>
            </div>
            <a href="index.html" class="back-link">
                ← Back to Multi-Strategy Dashboard
            </a>
        </header>
        
        <!-- Regime Duration Stats -->
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-label">🟢 Time spent in TQQQ (Strong Bull)</div>
                <div class="stat-value" id="stat-tqqq-val">{stats['TQQQ']:,} Days <span style="font-size: 0.55em; color: var(--green); font-weight: 500;">({percent_tqqq:.1f}%)</span></div>
                <div class="stat-bar-container">
                    <div class="stat-bar" id="stat-tqqq-bar" style="width: {percent_tqqq}%; background-color: var(--green);"></div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🟡 Time spent in QLD (Mild Warning)</div>
                <div class="stat-value" id="stat-qld-val">{stats['QLD']:,} Days <span style="font-size: 0.55em; color: var(--yellow); font-weight: 500;">({percent_qld:.1f}%)</span></div>
                <div class="stat-bar-container">
                    <div class="stat-bar" id="stat-qld-bar" style="width: {percent_qld}%; background-color: var(--yellow);"></div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔴 Time spent in QQQ (Bear Defense)</div>
                <div class="stat-value" id="stat-qqq-val">{stats['QQQ']:,} Days <span style="font-size: 0.55em; color: var(--red); font-weight: 500;">({percent_qqq:.1f}%)</span></div>
                <div class="stat-bar-container">
                    <div class="stat-bar" id="stat-qqq-bar" style="width: {percent_qqq}%; background-color: var(--red);"></div>
                </div>
            </div>
        </div>

        <!-- Interactive Date Range Selector -->
        <div class="card" style="margin-bottom: 2rem; padding: 1.25rem;">
            <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1.5rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9;">📅 Filter Date Range</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 4px;" id="data-range-label"></span>
                </div>
                
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 1.1rem;">
                    <!-- Presets -->
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">Preset:</span>
                        <select id="date-preset" style="background: #1e293b; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; cursor: pointer; transition: border-color 0.2s;">
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
                        <input type="date" id="start-date" style="background: #1e293b; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; transition: border-color 0.2s;">
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">To:</span>
                        <input type="date" id="end-date" style="background: #1e293b; border: 1px solid var(--border-color); color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.85rem; outline: none; transition: border-color 0.2s;">
                    </div>
                    
                    <button class="btn-reset" onclick="applyCustomDateFilter()" style="background: var(--accent-blue); border: none; color: #0b0f19; padding: 0.45rem 1.2rem; border-radius: 8px; font-weight: 600; font-size: 0.85rem; transition: opacity 0.2s;" onmouseover="this.style.opacity='0.9';" onmouseout="this.style.opacity='1';">Apply Filter</button>
                    <button class="btn-reset" onclick="resetDateFilter()">Reset</button>
                </div>
            </div>
        </div>

        <!-- Zoom Active Notification Banner -->
        <div class="zoom-banner" id="zoom-banner">
            <div id="zoom-banner-text" style="color: #ffffff; font-size: 0.95rem; line-height: 1.4;"></div>
            <button class="btn-reset" onclick="resetZoom()">Reset Zoom (Show All)</button>
        </div>

        <div class="dashboard-grid">
            <!-- 1. Interactive Chart Card -->
            <div id="sma-chart-card" class="card" style="padding: 1rem;">
                {plotly_div}
                
                <!-- Stock Beginner Education Guide -->
                <div class="legend-card-grid">
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
                    </div>
                </div>
            </div>
            
            <!-- 2. Transaction / Trigger Event Log -->
            <div class="card">
                <div class="card-title" id="chronicle-title-container">
                    <span id="chronicle-title">⚡ Chronicle of Regime Trigger Events ({len(triggers) - 1} Changes)</span>
                    <span style="font-size: 0.7em; font-weight: 400; color: var(--text-muted);">💡 Click any row below to automatically zoom the chart above!</span>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Regime Switch Action</th>
                                <th>QQQ Price</th>
                                <th>50-Day SMA</th>
                                <th>200-Day SMA</th>
                                <th>Switch Reason / Trigger Rule</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_joined}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Zoom Interaction JS script -->
    <script>
        // 100% robust serialized data array directly generated from Python
        const priceData = {js_data_json};

        // Scans visible data arrays to calculate the dynamic y-axis range (with 8% padding)
        function updateYAxisRange(startStr, endStr) {{
            // Clean up start and end strings to YYYY-MM-DD format for string comparison
            let cleanStart = startStr.substring(0, 10);
            let cleanEnd = endStr.substring(0, 10);
            
            let minVal = Infinity;
            let maxVal = -Infinity;
            
            for (let i = 0; i < priceData.length; i++) {{
                let item = priceData[i];
                if (item.d >= cleanStart && item.d <= cleanEnd) {{
                    let p = item.p;
                    let s50 = item.s50;
                    let s200 = item.s200;
                    
                    if (p !== undefined && p !== null && !isNaN(p)) {{
                        if (p < minVal) minVal = p;
                        if (p > maxVal) maxVal = p;
                    }}
                    if (s50 !== undefined && s50 !== null && !isNaN(s50)) {{
                        if (s50 < minVal) minVal = s50;
                        if (s50 > maxVal) maxVal = s50;
                    }}
                    if (s200 !== undefined && s200 !== null && !isNaN(s200)) {{
                        if (s200 < minVal) minVal = s200;
                        if (s200 > maxVal) maxVal = s200;
                    }}
                }}
            }}
            
            if (minVal !== Infinity && maxVal !== -Infinity) {{
                let padding = (maxVal - minVal) * 0.08;
                if (padding === 0) padding = 10;
                return [minVal - padding, maxVal + padding];
            }}
            return null;
        }}

        function zoomToTrigger(dateStr, regime, reasonClean) {{
            // Zoom range: 35 days before, 35 days after trigger date to give visual breathing room.
            // Parse date in a fully browser-compatible and timezone-agnostic manner.
            let parts = dateStr.split('-');
            let year = parseInt(parts[0], 10);
            let month = parseInt(parts[1], 10) - 1;
            let day = parseInt(parts[2], 10);
            
            let triggerDate = new Date(year, month, day);
            let start = new Date(year, month, day - 35);
            let end = new Date(year, month, day + 35);
            
            let formatDate = function(d) {{
                let y = d.getFullYear();
                let m = String(d.getMonth() + 1).padStart(2, '0');
                let dd = String(d.getDate()).padStart(2, '0');
                return y + '-' + m + '-' + dd;
            }};
            
            let startStr = formatDate(start);
            let endStr = formatDate(end);
            
            let yRange = updateYAxisRange(startStr, endStr);
            
            let updateObj = {{
                'xaxis.range': [startStr, endStr]
            }};
            
            if (yRange) {{
                updateObj['yaxis.range'] = yRange;
                updateObj['yaxis.autorange'] = false;
            }}
            
            // Relayout Plotly chart using the custom div_id we assigned
            Plotly.relayout('sma-chart', updateObj);
            
            // Smoothly scroll the chart card into view
            document.getElementById('sma-chart-card').scrollIntoView({{
                behavior: 'smooth',
                block: 'center'
            }});
            
            // Update and show active banner details
            let banner = document.getElementById('zoom-banner');
            let bannerText = document.getElementById('zoom-banner-text');
            let color = regime === 'TQQQ' ? '#2ecc71' : (regime === 'QLD' ? '#f1c40f' : '#e74c3c');
            
            bannerText.innerHTML = `🔍 <b>Inspecting trigger on ${{dateStr}}</b>: ${{reasonClean}}`;
            banner.style.borderLeft = `4px solid ${{color}}`;
            banner.style.display = 'flex';
            
            // Highlight the clicked row in the table
            let rows = document.querySelectorAll('tbody tr');
            rows.forEach(r => {{
                r.classList.remove('active-row');
            }});
            
            let clickedRow = document.getElementById('row-' + dateStr);
            if (clickedRow) {{
                clickedRow.classList.add('active-row');
            }}
        }}
        
        function resetZoom() {{
            // Reset the xaxis and yaxis scales to default auto
            Plotly.relayout('sma-chart', {{
                'xaxis.range': null,
                'yaxis.range': null,
                'yaxis.autorange': true
            }});
            
            // Hide the active banner
            let banner = document.getElementById('zoom-banner');
            banner.style.display = 'none';
            
            // Clear highlights from rows
            let rows = document.querySelectorAll('tbody tr');
            rows.forEach(r => {{
                r.classList.remove('active-row');
            }});
            
            // Sync with date controls reset
            resetDateFilter();
        }}

        // Custom Date Range Filter JS Functions
        function applyCustomDateFilter() {{
            let startStr = document.getElementById('start-date').value;
            let endStr = document.getElementById('end-date').value;
            
            if (!startStr || !endStr) return;
            if (startStr > endStr) {{
                alert("Start date cannot be after end date.");
                return;
            }}
            
            let yRange = updateYAxisRange(startStr, endStr);
            let gd = document.getElementById('sma-chart');
            if (gd) {{
                let updateObj = {{
                    'xaxis.range': [startStr, endStr]
                }};
                if (yRange) {{
                    updateObj['yaxis.range'] = yRange;
                    updateObj['yaxis.autorange'] = false;
                }}
                Plotly.relayout(gd, updateObj);
            }}
            
            recalculateStatsAndChronicle(startStr, endStr);
        }}
        
        function resetDateFilter() {{
            const minDate = priceData[0].d;
            const maxDate = priceData[priceData.length - 1].d;
            
            document.getElementById('start-date').value = minDate;
            document.getElementById('end-date').value = maxDate;
            document.getElementById('date-preset').value = 'all';
            
            let gd = document.getElementById('sma-chart');
            if (gd) {{
                Plotly.relayout(gd, {{
                    'xaxis.range': null,
                    'yaxis.range': null,
                    'yaxis.autorange': true
                }});
            }}
            
            recalculateStatsAndChronicle(minDate, maxDate);
        }}
        
        function handlePresetChange() {{
            const preset = document.getElementById('date-preset').value;
            const maxDateObj = new Date(priceData[priceData.length - 1].d);
            let startStr = priceData[0].d;
            let endStr = priceData[priceData.length - 1].d;
            
            if (preset === 'last5') {{
                let start = new Date(maxDateObj);
                start.setFullYear(start.getFullYear() - 5);
                startStr = start.toISOString().split('T')[0];
            }} else if (preset === 'last10') {{
                let start = new Date(maxDateObj);
                start.setFullYear(start.getFullYear() - 10);
                startStr = start.toISOString().split('T')[0];
            }} else if (preset === 'covid') {{
                startStr = '2020-01-01';
                endStr = '2022-06-30';
            }} else if (preset === 'tech_rally') {{
                startStr = '2023-01-01';
                endStr = priceData[priceData.length - 1].d;
            }} else if (preset === 'bear_defense') {{
                startStr = '2022-01-01';
                endStr = '2022-12-31';
            }}
            
            // Constrain to dataset boundaries
            if (startStr < priceData[0].d) startStr = priceData[0].d;
            
            document.getElementById('start-date').value = startStr;
            document.getElementById('end-date').value = endStr;
            
            applyCustomDateFilter();
        }}
        
        function recalculateStatsAndChronicle(startStr, endStr) {{
            let tqqqDays = 0;
            let qldDays = 0;
            let qqqDays = 0;
            let totalDays = 0;
            
            for (let i = 0; i < priceData.length; i++) {{
                let item = priceData[i];
                if (item.d >= startStr && item.d <= endStr) {{
                    totalDays++;
                    let p = item.p;
                    let s50 = item.s50;
                    let s200 = item.s200;
                    
                    if (p > s50 && p > s200) {{
                        tqqqDays++;
                    }} else if (p > s200) {{
                        qldDays++;
                    }} else {{
                        qqqDays++;
                    }}
                }}
            }}
            
            if (totalDays === 0) totalDays = 1;
            
            let pTqqq = (tqqqDays / totalDays) * 100;
            let pQld = (qldDays / totalDays) * 100;
            let pQqq = (qqqDays / totalDays) * 100;
            
            // Update stats cards values dynamically
            document.getElementById('stat-tqqq-val').innerHTML = `${{tqqqDays.toLocaleString()}} Days <span style="font-size: 0.55em; color: var(--green); font-weight: 500;">(${{pTqqq.toFixed(1)}}%)</span>`;
            document.getElementById('stat-qld-val').innerHTML = `${{qldDays.toLocaleString()}} Days <span style="font-size: 0.55em; color: var(--yellow); font-weight: 500;">(${{pQld.toFixed(1)}}%)</span>`;
            document.getElementById('stat-qqq-val').innerHTML = `${{qqqDays.toLocaleString()}} Days <span style="font-size: 0.55em; color: var(--red); font-weight: 500;">(${{pQqq.toFixed(1)}}%)</span>`;
            
            // Update stats progress bars widths dynamically
            document.getElementById('stat-tqqq-bar').style.width = `${{pTqqq}}%`;
            document.getElementById('stat-qld-bar').style.width = `${{pQld}}%`;
            document.getElementById('stat-qqq-bar').style.width = `${{pQqq}}%`;
            
            // Filter Chronicle Table rows
            let rows = document.querySelectorAll('tbody tr');
            let visibleCount = 0;
            rows.forEach(row => {{
                let id = row.id;
                if (id && id.startsWith('row-')) {{
                    let date = id.substring(4);
                    if (date >= startStr && date <= endStr) {{
                        row.style.display = '';
                        visibleCount++;
                    }} else {{
                        row.style.display = 'none';
                    }}
                }}
            }});
            
            // Update Chronicle title count
            let chronicleTitle = document.getElementById('chronicle-title');
            if (chronicleTitle) {{
                chronicleTitle.innerHTML = `⚡ Chronicle of Regime Trigger Events (${{visibleCount}} Events in Range)`;
            }}
        }}

        // Listen for manual zoom gestures via Plotly UI controls and dynamically adjust Y-axis scale
        document.addEventListener("DOMContentLoaded", function() {{
            let gd = document.getElementById('sma-chart');
            if (gd) {{
                gd.on('plotly_relayout', function(eventData) {{
                    if (eventData['xaxis.range[0]'] && eventData['xaxis.range[1]']) {{
                        let startStr = eventData['xaxis.range[0]'].split(' ')[0].substring(0, 10);
                        let endStr = eventData['xaxis.range[1]'].split(' ')[0].substring(0, 10);
                        
                        // Synchronize input fields
                        document.getElementById('start-date').value = startStr;
                        document.getElementById('end-date').value = endStr;
                        document.getElementById('date-preset').value = 'custom';
                        
                        // Recalculate stats and filter chronicle
                        recalculateStatsAndChronicle(startStr, endStr);
                        
                        let yRange = updateYAxisRange(startStr, endStr);
                        if (yRange) {{
                            Plotly.relayout('sma-chart', {{
                                'yaxis.range': yRange,
                                'yaxis.autorange': false
                            }});
                        }}
                    }} else if (eventData['xaxis.autorange'] === true) {{
                        resetDateFilter();
                    }}
                }});
            }}
            
            // Initialize date selection elements
            const minDate = priceData[0].d;
            const maxDate = priceData[priceData.length - 1].d;
            
            document.getElementById('start-date').min = minDate;
            document.getElementById('start-date').max = maxDate;
            document.getElementById('end-date').min = minDate;
            document.getElementById('end-date').max = maxDate;
            
            document.getElementById('start-date').value = minDate;
            document.getElementById('end-date').value = maxDate;
            
            document.getElementById('data-range-label').textContent = `${{minDate}} to ${{maxDate}}`;
            
            // Listen for preset changes
            document.getElementById('date-preset').addEventListener('change', handlePresetChange);
        }});
    </script>
</body>
</html>
"""
    
    # Save the file
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
