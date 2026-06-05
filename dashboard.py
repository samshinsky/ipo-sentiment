import streamlit as st
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timezone, timedelta
import config
import math
import subprocess
import sys
import anthropic

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

st.set_page_config(
    page_title="Pamalican Asset Management",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

* { box-sizing: border-box; }

html, body, .stApp {
    background: #0b1724 !important;
    font-family: 'DM Sans', sans-serif;
}

header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }
div[data-testid="stStatusWidget"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }

div[data-testid="stTabsContent"] {
    border: none !important;
    box-shadow: none !important;
    padding-top: 0 !important;
    background: transparent !important;
}

div[data-baseweb="tab-panel"] {
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    background: transparent !important;
}

div[data-baseweb="tab-border"] {
    display: none !important;
}

.header {
    background: linear-gradient(135deg, #0d1f2d 0%, #0b1a27 50%, #0d1f2d 100%);
    border-bottom: 2px solid #c97b3a;
    padding: 14px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: -6rem -4rem 0 -4rem;
}

.logo-area {
    display: flex;
    align-items: center;
    gap: 14px;
}

.logo-svg { width: 42px; height: 42px; }
.brand-text { display: flex; flex-direction: column; }

.brand-name {
    font-family: 'Rajdhani', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #4ecdc4;
    letter-spacing: 0.08em;
    line-height: 1;
}

.brand-sub {
    font-size: 10px;
    font-weight: 500;
    color: #7a9bb5;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-top: 2px;
}

.header-right {
    font-family: 'Rajdhani', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: #4ecdc4;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.main-panel { padding: 20px 0; }

.input-section {
    background: #0d1f2d;
    border: 1px solid #1a3347;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

.results-panel {
    background: #0d1f2d;
    border: 1px solid #1a3347;
    border-radius: 10px;
    padding: 24px;
}

.results-grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 32px;
    align-items: center;
}

.company-detail {
    font-size: 12px;
    color: #7a9bb5;
    margin-bottom: 4px;
}

.company-detail span {
    color: #e8f0f7;
    font-weight: 500;
}

.score-big {
    font-family: 'Rajdhani', sans-serif;
    font-size: 64px;
    font-weight: 700;
    line-height: 1;
}

.score-denom {
    font-size: 28px;
    color: #4a7a9b;
    font-weight: 400;
}

.signal-text {
    font-family: 'Rajdhani', sans-serif;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 6px;
}

.metrics-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}

.metric-box {
    background: #0b1724;
    border: 1px solid #1a3347;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}

.metric-icon-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
}

.metric-num {
    font-family: 'Rajdhani', sans-serif;
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
}

.bullish-box { border-color: #1a4a2e; }
.bullish-box .metric-icon-label { color: #4caf7d; }
.bullish-box .metric-num { color: #4caf7d; }

.neutral-box { border-color: #1a2a4a; }
.neutral-box .metric-icon-label { color: #4a7aaf; }
.neutral-box .metric-num { color: #4a7aaf; }

.bearish-box { border-color: #4a1a1a; }
.bearish-box .metric-icon-label { color: #e05c5c; }
.bearish-box .metric-num { color: #e05c5c; }

.ipo-box { border-color: #4a3a1a; }
.ipo-box .metric-icon-label { color: #e0a050; }
.ipo-box .metric-num { color: #e0a050; }

.quotes-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.quote-item {
    background: #0b1724;
    border-left: 3px solid;
    border-radius: 0 6px 6px 0;
    padding: 12px 14px;
    margin-bottom: 8px;
    font-size: 12px;
    color: #b0c4d8;
    line-height: 1.6;
}

.quote-source {
    font-size: 10px;
    color: #4a6a7a;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    gap: 4px;
    border-bottom: 1px solid #1a3347;
    margin: 0 -4rem;
    padding: 0 4rem;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #4a6a7a !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    padding: 10px 20px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}

.stTabs [aria-selected="true"] {
    color: #4ecdc4 !important;
    border-bottom-color: #4ecdc4 !important;
}

.stTextInput input {
    background: #0b1724 !important;
    border: 1px solid #1a3347 !important;
    color: #e8f0f7 !important;
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 13px !important;
}

.stTextInput input:focus {
    border-color: #4ecdc4 !important;
    box-shadow: 0 0 0 2px rgba(78,205,196,0.15) !important;
}

.stSelectbox > div > div {
    background: #0b1724 !important;
    border: 1px solid #1a3347 !important;
    color: #e8f0f7 !important;
    border-radius: 6px !important;
}

label {
    color: #4a7a9b !important;
    font-size: 10px !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
}

div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #4ecdc4, #2a9d94) !important;
    color: #0b1724 !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    width: 100% !important;
    padding: 10px !important;
}

div[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, #5eddd4, #3aada4) !important;
}

.stSpinner > div { border-top-color: #4ecdc4 !important; }
</style>
""", unsafe_allow_html=True)

LOGO_SVG = """<svg viewBox="0 0 42 42" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-svg">
  <polygon points="4,21 16,8 16,16 28,8 28,16 38,8 38,14 24,24 24,16 12,24 12,16" fill="#ffffff" opacity="0.9"/>
  <polygon points="4,27 16,14 16,22 28,14 28,22 38,14 38,20 24,30 24,22 12,30 12,22" fill="#4ecdc4" opacity="0.8"/>
</svg>"""

SOURCE_PRIORITY = [
    'telegram', 'lihkg', 'discuss', 'xiaohongshu', 'dcard', 'ptt',
    'naver_blog', 'naver_finance', 'aastocks', 'babykingdom',
    'mobile01', 'eastmoney', 'bilibili', '36kr', 'minkabu',
    'yahoo_japan', 'google_trends', 'youtube'
]

def source_rank(p):
    s = p.get('source', 'unknown')
    try:
        return SOURCE_PRIORITY.index(s)
    except ValueError:
        return 99

def get_summary(text, sentiment):
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": f"In one short sentence (max 15 words), summarise what this {sentiment} post is saying about the stock/IPO. If not in English, translate first. Post: {text[:300]}"}]
        )
        return msg.content[0].text.strip()
    except:
        return ""

def calculate_retail_score(data):
    if not data:
        return 0
    data = [p for p in data if p.get('relevance_tag') != 'news_article']
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
    if score >= 75: return "EXTREMELY FROTHY", "#ff8c42"
    elif score >= 60: return "BULLISH", "#4caf7d"
    elif score >= 50: return "MILDLY BULLISH", "#4caf7d"
    elif score >= 40: return "NEUTRAL", "#4a7aaf"
    elif score >= 25: return "MILDLY BEARISH", "#e05c5c"
    else: return "COLD / NO INTEREST", "#4a6a7a"

def get_score_color(score):
    if score >= 60: return "#4caf7d"
    elif score >= 40: return "#4a7aaf"
    else: return "#e05c5c"

def make_gauge(score, color):
    fig = go.Figure(go.Indicator(
        mode="gauge",
        value=score,
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#1a3347",
                     'tickfont': {'color': '#4a7a9b', 'size': 10}},
            'bar': {'color': color, 'thickness': 0.25},
            'bgcolor': "#0b1724",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 25], 'color': '#1a1a2e'},
                {'range': [25, 50], 'color': '#1a2030'},
                {'range': [50, 75], 'color': '#0f2a1a'},
                {'range': [75, 100], 'color': '#1a2a10'},
            ],
            'threshold': {
                'line': {'color': color, 'width': 3},
                'thickness': 0.8,
                'value': score
            }
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=180,
        margin=dict(l=20, r=20, t=20, b=0),
        font={'color': '#4a7a9b', 'family': 'DM Sans'}
    )
    return fig

def clear_company(company_en):
    supabase.table("posts").delete().eq("company", company_en).execute()

def fetch_results(company_en):
    result = supabase.table("posts").select("*").eq("company", company_en).execute()
    return result.data

def get_sources_for_region(region):
    if region == "HK":
        return ["eastmoney", "bilibili", "36kr", "stockfeel", "mobile01", "google_trends"]
    elif region == "JP":
        return ["yahoo_japan", "minkabu", "36kr", "google_trends"]
    elif region == "KR":
        return ["eastmoney", "google_trends"]
    elif region == "TW":
        return ["stockfeel", "mobile01", "eastmoney", "google_trends"]
    return ["eastmoney", "google_trends"]

def display_results(scored_data, company_name, ticker_val, company_zh_val, region_val):
    score = calculate_retail_score(scored_data)
    signal, signal_color = get_signal(score)
    score_color = get_score_color(score)

    scored_data = [p for p in scored_data if p.get('relevance_tag') != 'news_article']
    bullish = [p for p in scored_data if p['sentiment_label'] == 'bullish']
    bearish = [p for p in scored_data if p['sentiment_label'] == 'bearish']
    neutral = [p for p in scored_data if p['sentiment_label'] == 'neutral']
    ipo_rel = [p for p in scored_data if p.get('relevance_tag') == 'ipo_related']

    st.markdown(f"""
    <div class="results-panel">
        <div class="results-grid">
            <div>
                <div style="margin-bottom:20px">
                    <div class="company-detail">Ticker: <span>{ticker_val or '—'}</span></div>
                    <div class="company-detail">English Name: <span>{company_name}</span></div>
                    <div class="company-detail">Local Name: <span>{company_zh_val or '—'}</span></div>
                    <div class="company-detail">Region: <span>{region_val}</span></div>
                </div>
                <div style="text-align:center">
                    <div class="score-big" style="color:{score_color}">{score}<span class="score-denom">/100</span></div>
                    <div class="signal-text" style="color:{signal_color}">{signal}</div>
                </div>
            </div>
            <div class="metrics-row">
                <div class="metric-box bullish-box">
                    <div class="metric-icon-label">↗ Bullish Posts</div>
                    <div class="metric-num">{len(bullish)}</div>
                </div>
                <div class="metric-box neutral-box">
                    <div class="metric-icon-label">▐ Neutral Posts</div>
                    <div class="metric-num">{len(neutral)}</div>
                </div>
                <div class="metric-box bearish-box">
                    <div class="metric-icon-label">↘ Bearish Posts</div>
                    <div class="metric-num">{len(bearish)}</div>
                </div>
                <div class="metric-box ipo-box">
                    <div class="metric-icon-label">★ IPO Related</div>
                    <div class="metric-num">{len(ipo_rel)}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_gauge, col_spacer = st.columns([1, 3])
    with col_gauge:
        st.plotly_chart(make_gauge(score, score_color), use_container_width=True)

    col_bull, col_bear = st.columns(2)

    with col_bull:
        st.markdown('<div class="quotes-title" style="color:#4caf7d">Top Bullish Signals</div>', unsafe_allow_html=True)
        ipo_bullish = [p for p in bullish if p.get('relevance_tag') == 'ipo_related']
        pool = sorted(ipo_bullish or bullish, key=lambda x: (source_rank(x), -float(x.get('sentiment_score') or 0)))[:3]
        for p in pool:
            text = (p.get('body') or p.get('title') or '')[:250]
            source = p.get('source', '')
            relevance = p.get('relevance_tag', '')
            summary = get_summary(text, 'bullish')
            st.markdown(f"""<div class="quote-item" style="border-color:#4caf7d">
                {text}
                {f'<div style="color:#4caf7d;font-size:11px;margin-top:6px;font-style:italic">→ {summary}</div>' if summary else ''}
                <div class="quote-source">{source} · {relevance}</div>
            </div>""", unsafe_allow_html=True)

    with col_bear:
        st.markdown('<div class="quotes-title" style="color:#e05c5c">Top Bearish Signals</div>', unsafe_allow_html=True)
        ipo_bearish = [p for p in bearish if p.get('relevance_tag') == 'ipo_related']
        pool = sorted(ipo_bearish or bearish, key=lambda x: (source_rank(x), float(x.get('sentiment_score') or 0)))[:3]
        for p in pool:
            text = (p.get('body') or p.get('title') or '')[:250]
            source = p.get('source', '')
            relevance = p.get('relevance_tag', '')
            summary = get_summary(text, 'bearish')
            st.markdown(f"""<div class="quote-item" style="border-color:#e05c5c">
                {text}
                {f'<div style="color:#e05c5c;font-size:11px;margin-top:6px;font-style:italic">→ {summary}</div>' if summary else ''}
                <div class="quote-source">{source} · {relevance}</div>
            </div>""", unsafe_allow_html=True)

# ── HEADER ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="header">
    <div class="logo-area">
        {LOGO_SVG}
        <div class="brand-text">
            <div class="brand-name">PAMALICAN ASSET MANAGEMENT</div>
            <div class="brand-sub">IPO Retail Sentiment Intelligence</div>
        </div>
    </div>
    <div class="header-right">Stock Sentiment Scanner</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["LIVE SCAN", "BACKTEST"])

with tab1:
    st.markdown('<div class="main-panel">', unsafe_allow_html=True)
    st.markdown('<div class="input-section">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
    with col1:
        company_en = st.text_input("Company Name (English)", placeholder="e.g. LongBio Pharma")
    with col2:
        company_zh = st.text_input("Company Name (Local)", placeholder="e.g. 朗迈生物")
    with col3:
        ticker = st.text_input("Ticker / Code", placeholder="e.g. 1779")
    with col4:
        region = st.selectbox("Region", ["HK", "JP", "KR", "TW"])

    col_window, col_scan = st.columns([3, 1])
    with col_window:
        days_back = st.radio("Time window", [7, 30, 60, 90], horizontal=True, index=1,
                             format_func=lambda x: f"{x} days")
    with col_scan:
        st.markdown("<br>", unsafe_allow_html=True)
        scan_clicked = st.button("SCAN", key="run_scan")

    st.markdown('</div>', unsafe_allow_html=True)

    if scan_clicked:
        if not company_en:
            st.error("Please enter a company name.")
        else:
            company_clean = company_en.strip()
            with st.spinner(f"Collecting posts for {company_clean}..."):
                clear_company(company_clean)
                import asyncio
                from collector_playwright import run_all as playwright_run
                sources = get_sources_for_region(region)
                asyncio.run(playwright_run(company_clean, company_zh, ticker, region, sources))

                if region == "HK":
                    subprocess.run([sys.executable, "collector_lihkg.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_aastocks.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_xiaohongshu.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_discuss.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_babykingdom.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)

                if region == "KR":
                    subprocess.run([sys.executable, "collector_naver.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_cafestock.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)

                if region == "TW":
                    subprocess.run([sys.executable, "collector_ptt.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)
                    subprocess.run([sys.executable, "collector_dcard.py"],
                        input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n", text=True)

                subprocess.run([sys.executable, "collector_youtube.py"],
                    input=f"{company_clean}\n{company_zh or ''}\n{ticker or ''}\n{region}\n", text=True)

            # Enforce time window
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
            supabase.table("posts").delete().eq("company", company_clean).lt("posted_at", cutoff).execute()

            with st.spinner("Scoring sentiment with AI..."):
                from sentiment import run_sentiment
                run_sentiment(company_clean)

            st.session_state['last_company'] = company_clean
            st.session_state['last_ticker'] = ticker
            st.session_state['last_zh'] = company_zh
            st.session_state['last_region'] = region
            st.session_state['last_days'] = days_back
            st.rerun()

    if 'last_company' in st.session_state:
        data = fetch_results(st.session_state['last_company'])
        scored_data = [p for p in data if p.get('sentiment_label')]
        if scored_data:
            display_results(
                scored_data,
                st.session_state['last_company'],
                st.session_state.get('last_ticker', ''),
                st.session_state.get('last_zh', ''),
                st.session_state.get('last_region', '')
            )

    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="main-panel">', unsafe_allow_html=True)
    st.markdown('<div class="input-section">', unsafe_allow_html=True)
    st.markdown("### Historical IPO Sentiment Backtest")
    st.markdown("Enter a past IPO and select a lookback window to see what retail sentiment looked like before listing.")

    bt_col1, bt_col2, bt_col3 = st.columns([3, 2, 2])
    with bt_col1:
        bt_company = st.text_input("Company name", placeholder="e.g. Mixue", key="bt_company")
    with bt_col2:
        bt_ipo_date = st.date_input("IPO listing date", key="bt_date")
    with bt_col3:
        bt_region = st.selectbox("Region", ["HK", "JP", "KR", "TW"], key="bt_region")

    bt_zh = st.text_input("Local name (optional)", placeholder="e.g. 蜜雪冰城", key="bt_zh")
    bt_ticker = st.text_input("Ticker (optional)", key="bt_ticker")
    bt_window = st.radio("Days before IPO", [7, 30, 60, 90], horizontal=True,
                         key="bt_window", format_func=lambda x: f"{x}d")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("RUN BACKTEST", key="run_backtest"):
        if not bt_company:
            st.error("Please enter a company name.")
        else:
            bt_clean = bt_company.strip()
            with st.spinner("Collecting historical data..."):
                clear_company(bt_clean)
                import asyncio
                from collector_playwright import run_all as playwright_run
                sources = get_sources_for_region(bt_region)
                asyncio.run(playwright_run(bt_clean, bt_zh, bt_ticker, bt_region, sources))
                subprocess.run([sys.executable, "collector_youtube.py"],
                    input=f"{bt_clean}\n{bt_zh or ''}\n{bt_ticker or ''}\n{bt_region}\n", text=True)

            # Enforce backtest time window
            ipo_dt = datetime.combine(bt_ipo_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            cutoff = (ipo_dt - timedelta(days=bt_window)).isoformat()
            supabase.table("posts").delete().eq("company", bt_clean).lt("posted_at", cutoff).execute()
            supabase.table("posts").delete().eq("company", bt_clean).gt("posted_at", ipo_dt.isoformat()).execute()

            with st.spinner("Scoring sentiment..."):
                from sentiment import run_sentiment
                run_sentiment(bt_clean)
            bt_data = fetch_results(bt_clean)
            scored = [p for p in bt_data if p.get('sentiment_label')]
            if scored:
                display_results(scored, bt_clean, bt_ticker, bt_zh, bt_region)

    st.markdown('</div>', unsafe_allow_html=True)