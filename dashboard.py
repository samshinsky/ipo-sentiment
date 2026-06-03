import streamlit as st
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timezone, timedelta
import config
import math
import subprocess
import sys

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

st.set_page_config(
    page_title="Pamalican Asset Management",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0a0a0f; }
    .block-container { padding-top: 2rem; }
    .header {
        display: flex;
        align-items: center;
        padding: 0 0 30px 0;
        border-bottom: 1px solid #1e1e2e;
        margin-bottom: 30px;
    }
    .brand {
        font-size: 18px;
        font-weight: 600;
        color: #c9a84c;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .brand-sub {
        font-size: 11px;
        color: #555;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-top: 2px;
    }
    .score-container {
        background: #0f0f1a;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        height: 100%;
    }
    .score-number {
        font-size: 96px;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 8px;
    }
    .score-label {
        font-size: 14px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .signal-badge {
        display: inline-block;
        padding: 8px 24px;
        border-radius: 100px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-top: 16px;
        text-transform: uppercase;
    }
    .metric-card {
        background: #0f0f1a;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: #fff;
    }
    .metric-label {
        font-size: 11px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 4px;
    }
    .quote-card {
        background: #0f0f1a;
        border-left: 3px solid;
        border-radius: 0 8px 8px 0;
        padding: 16px 20px;
        margin-bottom: 12px;
        font-size: 13px;
        color: #ccc;
        line-height: 1.6;
    }
    .quote-meta {
        font-size: 11px;
        color: #555;
        margin-top: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stButton"] button {
        background: #c9a84c !important;
        color: #000 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 12px 32px !important;
        width: 100% !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    div[data-testid="stButton"] button:hover {
        background: #e8c46a !important;
    }
    h1, h2, h3 { color: #fff !important; }
    .stTabs [data-baseweb="tab"] {
        color: #888 !important;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stTabs [aria-selected="true"] {
        color: #c9a84c !important;
    }
    div[data-baseweb="radio"] label {
        color: #888 !important;
    }
    div[data-baseweb="radio"] [data-checked="true"] + div {
        color: #c9a84c !important;
    }
    .stTextInput input {
        background: #0f0f1a !important;
        border: 1px solid #1e1e2e !important;
        color: #fff !important;
        border-radius: 8px !important;
    }
    .stSelectbox > div > div {
        background: #0f0f1a !important;
        border: 1px solid #1e1e2e !important;
        color: #fff !important;
        border-radius: 8px !important;
    }
    label { color: #888 !important; font-size: 12px !important; }
    hr { border-color: #1e1e2e !important; }
    .stSpinner > div { border-top-color: #c9a84c !important; }
</style>
""", unsafe_allow_html=True)

def calculate_retail_score(data):
    if not data:
        return 0
    total_posts = len(data)
    volume_score = min(30, math.log1p(total_posts) * 5)
    weighted_sentiment = 0
    total_weight = 0
    for p in data:
        source_weight = float(p.get('source_weight') or 1.0)
        sentiment_score = float(p.get('sentiment_score') or 0)
        conviction = float(p.get('conviction') or 0.5)
        relevance = p.get('relevance_tag', 'general_mention')
        relevance_multiplier = 2.0 if relevance == 'ipo_related' else 1.0
        effective_weight = source_weight * conviction * relevance_multiplier
        weighted_sentiment += sentiment_score * effective_weight
        total_weight += effective_weight
    if total_weight > 0:
        avg_sentiment = weighted_sentiment / total_weight
        sentiment_component = (avg_sentiment + 1) / 2 * 70
    else:
        sentiment_component = 35
    return round(min(100, max(0, volume_score + sentiment_component)))

def get_signal(score):
    if score >= 75:
        return "EXTREMELY FROTHY", "#ff6b35"
    elif score >= 60:
        return "STRONGLY BULLISH", "#2ecc71"
    elif score >= 50:
        return "MILDLY BULLISH", "#27ae60"
    elif score >= 40:
        return "NEUTRAL", "#f39c12"
    elif score >= 25:
        return "MILDLY BEARISH", "#e74c3c"
    else:
        return "COLD / NO INTEREST", "#95a5a6"

def get_score_color(score):
    if score >= 75:
        return "#ff6b35"
    elif score >= 60:
        return "#2ecc71"
    elif score >= 50:
        return "#27ae60"
    elif score >= 40:
        return "#f39c12"
    elif score >= 25:
        return "#e74c3c"
    else:
        return "#95a5a6"

def clear_company(company_en):
    supabase.table("posts").delete().eq("company", company_en).execute()

def fetch_results(company_en):
    result = supabase.table("posts").select("*").eq("company", company_en).execute()
    return result.data

def display_results(scored_data, company_name):
    score = calculate_retail_score(scored_data)
    signal, signal_color = get_signal(score)
    score_color = get_score_color(score)

    bullish = [p for p in scored_data if p['sentiment_label'] == 'bullish']
    bearish = [p for p in scored_data if p['sentiment_label'] == 'bearish']
    neutral = [p for p in scored_data if p['sentiment_label'] == 'neutral']
    ipo_rel = [p for p in scored_data if p.get('relevance_tag') == 'ipo_related']
    total = len(scored_data)

    st.markdown("<br>", unsafe_allow_html=True)
    col_score, col_breakdown = st.columns([1, 2])

    with col_score:
        st.markdown(f"""
        <div class="score-container">
            <div class="score-number" style="color: {score_color}">{score}</div>
            <div class="score-label">Retail Sentiment Score</div>
            <div class="signal-badge" style="background: {signal_color}22; color: {signal_color}; border: 1px solid {signal_color}44">
                {signal}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_breakdown:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#2ecc71">{len(bullish)}</div>
                <div class="metric-label">Bullish ({round(len(bullish)/total*100)}%)</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#e74c3c">{len(bearish)}</div>
                <div class="metric-label">Bearish ({round(len(bearish)/total*100)}%)</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#888">{len(neutral)}</div>
                <div class="metric-label">Neutral ({round(len(neutral)/total*100)}%)</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value" style="color:#c9a84c">{len(ipo_rel)}</div>
                <div class="metric-label">IPO-related</div>
            </div>""", unsafe_allow_html=True)

        # Source breakdown chart — sorted correctly
        sources = {}
        for p in scored_data:
            s = p.get('source', 'unknown')
            sources[s] = sources.get(s, 0) + 1
        
        sorted_sources = sorted(sources.items(), key=lambda x: x[1])
        
        fig = go.Figure(go.Bar(
            x=[v for _, v in sorted_sources],
            y=[k for k, _ in sorted_sources],
            orientation='h',
            marker_color='#c9a84c',
            marker_opacity=0.8
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#888',
            font_size=12,
            height=max(150, len(sources) * 40),
            margin=dict(l=0, r=20, t=10, b=0),
            xaxis=dict(gridcolor='#1e1e2e', showgrid=True),
            yaxis=dict(gridcolor='#1e1e2e', showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_bull_q, col_bear_q = st.columns(2)
    with col_bull_q:
        st.markdown("**Top Bullish Signals**")
        top_bullish = sorted(bullish, key=lambda x: float(x.get('sentiment_score') or 0), reverse=True)[:3]
        for p in top_bullish:
            text = (p.get('body') or p.get('title') or '')[:250]
            source = p.get('source', '')
            st.markdown(f"""<div class="quote-card" style="border-color: #2ecc71">
                {text}
                <div class="quote-meta">{source}</div>
            </div>""", unsafe_allow_html=True)

    with col_bear_q:
        st.markdown("**Top Bearish Signals**")
        top_bearish = sorted(bearish, key=lambda x: float(x.get('sentiment_score') or 0))[:3]
        for p in top_bearish:
            text = (p.get('body') or p.get('title') or '')[:250]
            source = p.get('source', '')
            st.markdown(f"""<div class="quote-card" style="border-color: #e74c3c">
                {text}
                <div class="quote-meta">{source}</div>
            </div>""", unsafe_allow_html=True)

# ── HEADER ───────────────────────────────────────────────────────────
st.markdown("""
<div class="header">
    <div>
        <div class="brand">Pamalican Asset Management</div>
        <div class="brand-sub">IPO Retail Sentiment Intelligence</div>
    </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["LIVE SCAN", "BACKTEST"])

# ══════════════════════════════════════════════════════════════════════
# TAB 1: LIVE SCAN
# ══════════════════════════════════════════════════════════════════════
with tab1:
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    with col1:
        company_en = st.text_input("Company name (English)", placeholder="e.g. Mixue")
    with col2:
        company_zh = st.text_input("Local name", placeholder="e.g. 蜜雪冰城")
    with col3:
        ticker = st.text_input("Ticker", placeholder="e.g. 2097")
    with col4:
        region = st.selectbox("Region", ["HK", "JP", "KR", "TW"])

    days_back = st.radio("Time window", [7, 30, 60, 90], horizontal=True, index=1,
                         format_func=lambda x: f"{x}d")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("RUN SCAN", key="run_scan"):
        if not company_en:
            st.error("Please enter a company name.")
        else:
            company_clean = company_en.strip()

            with st.spinner(f"Collecting posts for {company_clean}..."):
                clear_company(company_clean)

                import asyncio
                from collector_playwright import run_all as playwright_run
                sources = ["eastmoney", "bilibili", "36kr", "yahoo_japan",
                           "minkabu", "stockfeel", "mobile01", "google_trends"]
                asyncio.run(playwright_run(company_clean, company_zh, ticker, region, sources))

                if region == "HK":
                    subprocess.run([sys.executable, "collector_lihkg.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                if region == "KR":
                    subprocess.run([sys.executable, "collector_naver.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                if region == "TW":
                    subprocess.run([sys.executable, "collector_ptt.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)

                subprocess.run([sys.executable, "collector_youtube.py"],
                    input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n{region}\n", text=True)

            with st.spinner("Scoring sentiment with AI..."):
                from sentiment import run_sentiment
                run_sentiment(company_clean)

            st.rerun()

    # Results
    if company_en:
        data = fetch_results(company_en.strip())
        scored_data = [p for p in data if p.get('sentiment_label')]
        if scored_data:
            display_results(scored_data, company_en.strip())

# ══════════════════════════════════════════════════════════════════════
# TAB 2: BACKTEST
# ══════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Historical IPO Sentiment Backtest")
    st.markdown("Enter a past IPO and select a lookback window to see what retail sentiment looked like before listing.")

    bt_col1, bt_col2, bt_col3 = st.columns([3, 2, 2])
    with bt_col1:
        bt_company = st.text_input("Company name", placeholder="e.g. BubbleMart", key="bt_company")
    with bt_col2:
        bt_ipo_date = st.date_input("IPO listing date", key="bt_date")
    with bt_col3:
        bt_region = st.selectbox("Region", ["HK", "JP", "KR", "TW"], key="bt_region")

    bt_zh = st.text_input("Local name (optional)", placeholder="e.g. 泡泡瑪特", key="bt_zh")
    bt_ticker = st.text_input("Ticker (optional)", key="bt_ticker")
    bt_window = st.radio("Days before IPO", [7, 30, 60, 90], horizontal=True,
                         key="bt_window", format_func=lambda x: f"{x}d")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("RUN BACKTEST", key="run_backtest"):
        if not bt_company:
            st.error("Please enter a company name.")
        else:
            bt_clean = bt_company.strip()
            st.info(f"Backtesting {bt_clean} — {bt_window} days before {bt_ipo_date}")

            with st.spinner("Collecting historical data..."):
                clear_company(bt_clean)
                import asyncio
                from collector_playwright import run_all as playwright_run
                asyncio.run(playwright_run(bt_clean, bt_zh, bt_ticker, bt_region, None))
                subprocess.run([sys.executable, "collector_youtube.py"],
                    input=f"{bt_clean}\n{bt_zh or ''}\n{bt_ticker or ''}\n{bt_region}\n", text=True)

            with st.spinner("Scoring sentiment..."):
                from sentiment import run_sentiment
                run_sentiment(bt_clean)

            bt_data = fetch_results(bt_clean)
            scored = [p for p in bt_data if p.get('sentiment_label')]

            if scored:
                score = calculate_retail_score(scored)
                signal, signal_color = get_signal(score)
                score_color = get_score_color(score)

                st.markdown(f"""
                <div class="score-container" style="margin-top: 24px; text-align:center">
                    <div style="color:#888; font-size:12px; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:8px">
                        {bt_window}d pre-IPO sentiment — {bt_clean}
                    </div>
                    <div class="score-number" style="color: {score_color}">{score}</div>
                    <div class="score-label">Retail Sentiment Score</div>
                    <div class="signal-badge" style="background: {signal_color}22; color: {signal_color}; border: 1px solid {signal_color}44">
                        {signal}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                display_results(scored, bt_clean)