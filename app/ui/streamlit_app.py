import streamlit as st
import streamlit.components.v1 as _components
import sys
import os
import re
import base64
import datetime as _dt
import platform

# パスを通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService
from app.services.storage_service import StorageService
from app.engines.finance_engine import FinanceEngine, FinanceResult
from app.engines.exit_strategy_engine import ExitStrategyEngine, ExitStrategyResult
from app.engines.repair_cost_engine import RepairCostEngine, RepairCostResult
from app.engines.developer_land_engine import DeveloperLandEngine, DevLandResult

# UI/UX 強化機能（F1-F4）
from app.ui.dashboard_page import render_dashboard_page
from app.ui.chat_input_page import render_chat_input_page
from app.services.similarity_service import SimilarityService
from app.services.second_opinion_service import SecondOpinionService

def _logo_b64(size: int = 64) -> str:
    p = os.path.join(os.path.dirname(__file__), "..", "static", "mam_logo", f"mam_{size}x{size}.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

def _page_icon_img():
    try:
        from PIL import Image as _PIL
        p = os.path.join(os.path.dirname(__file__), "..", "static", "mam_logo", "mam_32x32.png")
        if os.path.exists(p):
            return _PIL.open(p)
    except Exception:
        pass
    return "🤖"

st.set_page_config(
    page_title="My Agent Match",
    page_icon=_page_icon_img(),
    layout="wide",
    initial_sidebar_state="expanded"
)

def _plotly_font() -> str:
    """OS別にPlotlyで使用する日本語フォントを返す"""
    if platform.system() == "Windows":
        return "Yu Gothic UI, Meiryo, sans-serif"
    elif platform.system() == "Darwin":
        return "Hiragino Sans, -apple-system, sans-serif"
    else:  # Linux (Streamlit Cloud)
        return "Noto Sans JP, Liberation Sans, sans-serif"

# ═══════════════════════════════════════
# 簡易パスワード認証
# ═══════════════════════════════════════
def _check_auth() -> bool:
    """簡易パスワード認証。st.secrets または 環境変数 APP_PASSWORD で設定。"""
    # パスワード未設定なら認証スキップ（開発時）
    try:
        expected = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        expected = os.environ.get("APP_PASSWORD", "")

    if not expected:
        return True  # パスワード未設定なら全員通過

    if st.session_state.get("authenticated"):
        return True

    # ログイン画面
    _logo64 = _logo_b64(64)
    _logo_html = f'<img src="data:image/png;base64,{_logo64}" width="64" height="64" style="margin-bottom:10px;border-radius:12px;" />' if _logo64 else '<div style="font-size:2.8rem;margin-bottom:10px;line-height:1;">🤖</div>'
    st.markdown(f"""
    <div style="max-width:400px;margin:60px auto 24px;padding:36px 40px;
         background:linear-gradient(180deg,#141416 0%,#0E0E10 100%);
         border-radius:16px;
         box-shadow:inset 0 1px 0 rgba(255,255,255,0.08),0 8px 48px rgba(0,0,0,0.8),0 1px 0 rgba(0,0,0,0.9);
         border:1px solid rgba(255,255,255,0.08);">
      <div style="text-align:center;margin-bottom:28px;">
        {_logo_html}
        <div style="font-size:1.6rem;font-weight:900;letter-spacing:-0.02em;
             font-family:'Noto Sans JP','Inter','Helvetica Neue',sans-serif;
             background:linear-gradient(135deg,#FFFFFF 0%,#E8E8EC 45%,#A8A8B0 100%);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
          My Agent Match
        </div>
        <div style="font-size:0.72rem;color:#606068;margin-top:4px;letter-spacing:0.12em;
             text-transform:uppercase;font-weight:600;">
          NEURAL ESTATE &middot; AI
        </div>
        <div style="width:40px;height:1px;
             background:linear-gradient(90deg,transparent,rgba(192,192,200,0.5),transparent);
             margin:14px auto 0;"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        pw = st.text_input("パスワード", type="password", placeholder="パスワードを入力")
        submitted = st.form_submit_button("ログイン", use_container_width=True)
        if submitted:
            if pw == expected:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
    return False

if not _check_auth():
    st.stop()

st.markdown("""<script>
document.documentElement.lang='ja';
document.documentElement.setAttribute('translate','no');
document.documentElement.className += ' notranslate';
</script>
<style>
html { translate: no; }

/* ═══════════════════════════════════════════════════
   NEURAL ESTATE — My Agent Match v5.0
   Monochrome Luxury · Black × White × Chrome Silver
   Palette:
     BG Deep:       #0A0A0C
     BG Surface:    #111113
     BG Raised:     #1A1A1D
     Chrome Light:  #E8E8EC
     Chrome Mid:    #A8A8B0
     Chrome Dark:   #686870
     Platinum:      #C0C0C8
     White:         #FFFFFF
     Off-White:     #F4F4F6
     Text Primary:  #FFFFFF
     Text Secondary:#9A9AA0
     Success:       #A8D8B9  (platinum-green)
     Warning:       #D4B886  (smoked gold)
     Error:         #E89999  (dusty rose)
   ═══════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── CSS Custom Properties ── */
:root {
  --bg-deep:        #0A0A0C;
  --bg-surface:     #111113;
  --bg-raised:      #1A1A1D;
  --chrome-light:   #E8E8EC;
  --chrome-mid:     #A8A8B0;
  --chrome-dark:    #686870;
  --platinum:       #C0C0C8;
  --white:          #FFFFFF;
  --off-white:      #F4F4F6;
  --text-primary:   #FFFFFF;
  --text-secondary: #9A9AA0;
  --text-muted:     #606068;
  --border-subtle:  rgba(255,255,255,0.07);
  --border-chrome:  rgba(232,232,236,0.18);
  --chrome-grad:    linear-gradient(135deg, #E8E8EC 0%, #A8A8B0 50%, #E8E8EC 100%);
  --chrome-sheen:   linear-gradient(180deg, rgba(255,255,255,0.14) 0%, rgba(0,0,0,0.32) 100%);
  --success:        #A8D8B9;
  --warning:        #D4B886;
  --error:          #E89999;
  --info:           #A8C4D8;
}

/* ── Keyframe Animations ── */
@keyframes chrome-shimmer {
  0%   { background-position: -200% center; }
  100% { background-position: 200% center; }
}
@keyframes float-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0 rgba(192,192,200,0.4); }
  70%  { box-shadow: 0 0 0 12px rgba(192,192,200,0); }
  100% { box-shadow: 0 0 0 0 rgba(192,192,200,0); }
}
@keyframes fade-hint {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ── Global ── */
.stApp {
    background: linear-gradient(160deg, #0A0A0C 0%, #111113 50%, #0E0E10 100%) !important;
    font-family: 'Noto Sans JP', 'Inter', 'Helvetica Neue', sans-serif !important;
}
* { box-sizing: border-box; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #050505 0%, #0C0C0E 55%, #101012 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    box-shadow: 4px 0 40px rgba(0,0,0,0.8), inset -1px 0 0 rgba(255,255,255,0.04) !important;
}
[data-testid="stSidebar"] > div { background: transparent !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div { color: var(--text-muted) !important; }
[data-testid="stSidebar"] h1 {
    background: var(--chrome-grad) !important;
    -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-size: 1.35rem !important; font-weight: 900 !important; letter-spacing: -0.02em !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--text-muted) !important; font-size: 0.8rem !important; }
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p { color: var(--text-secondary) !important; font-size: 0.9rem !important; }
[data-testid="stSidebar"] hr {
    border: none !important;
    border-top: 1px solid rgba(255,255,255,0.07) !important;
    background: linear-gradient(90deg, transparent, rgba(192,192,200,0.25), transparent) !important;
    height: 1px !important;
}
[data-testid="stSidebar"] .stInfo,
[data-testid="stSidebar"] .element-container .stAlert {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] .stInfo p,
[data-testid="stSidebar"] .stAlert p { color: var(--text-muted) !important; }
[data-testid="stSidebar"] .stRadio [role="radio"] { accent-color: var(--chrome-mid); }

/* ── Main content background ── */
.main .block-container {
    padding: 1.5rem 2.5rem 2rem !important;
    max-width: 1440px !important;
}
[data-testid="stAppViewContainer"] > .main {
    background: transparent !important;
}

/* ── Text colors in main ── */
.stApp p, .stApp span, .stApp li { color: var(--text-secondary); }
.stApp h1, .stApp h2, .stApp h3 { color: var(--text-primary); }
[data-testid="stMarkdownContainer"] p { color: var(--text-secondary) !important; }

/* ── PDF Drop Zone ── */
.pdf-hero {
    position: relative; overflow: hidden;
    background: linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(192,192,200,0.03) 100%);
    border: 1.5px dashed rgba(192,192,200,0.35);
    border-radius: 16px; padding: 44px 36px;
    text-align: center; cursor: pointer;
    transition: all 0.3s ease;
    animation: float-in 0.5s ease both;
}
.pdf-hero::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 30% 50%, rgba(232,232,236,0.04) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 50%, rgba(168,168,176,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.pdf-hero::after {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(232,232,236,0.4), transparent);
    pointer-events: none;
}
.pdf-hero:hover {
    border-color: rgba(232,232,236,0.55);
    background: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(192,192,200,0.05) 100%);
    box-shadow: 0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.12);
    transform: translateY(-1px);
}
.pdf-hero-icon {
    font-size: 3.2rem; line-height: 1; margin-bottom: 16px;
    filter: drop-shadow(0 2px 12px rgba(0,0,0,0.8));
}
.pdf-hero-title {
    font-size: 1.35rem; font-weight: 900; color: var(--white);
    margin-bottom: 8px; letter-spacing: -0.02em;
}
.pdf-hero-sub {
    font-size: 0.85rem; color: var(--text-muted); margin-bottom: 20px; line-height: 1.7;
}
.pdf-hero-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.06); border: 1px solid rgba(192,192,200,0.25);
    color: var(--chrome-light); font-size: 0.72rem; font-weight: 700;
    padding: 4px 14px; border-radius: 20px; letter-spacing: 0.1em;
}

/* ── Glass Cards ── */
.glass-card {
    background: rgba(26,26,29,0.8);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 14px; padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.5);
    transition: border-color 0.3s, box-shadow 0.3s;
    animation: float-in 0.4s ease both;
}
.glass-card:hover {
    border-color: rgba(192,192,200,0.18);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10), 0 8px 32px rgba(0,0,0,0.6);
}

/* ── KPI Metric Cards ── */
.kpi-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px; margin: 12px 0;
}
.kpi-card {
    background: var(--bg-raised);
    border-radius: 12px; padding: 18px 20px;
    border: 1px solid var(--border-subtle);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 2px 12px rgba(0,0,0,0.4);
    position: relative; overflow: hidden;
    transition: transform 0.2s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    animation: float-in 0.4s ease both;
}
.kpi-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 1px; border-radius: 12px 12px 0 0;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(192,192,200,0.2);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10), 0 10px 28px rgba(0,0,0,0.55);
}
/* Chrome silver accent lines — remapped from neon palette */
.kpi-card.c-blue::before  { background: linear-gradient(90deg, #C0C0C8, #E8E8EC, #C0C0C8); }
.kpi-card.c-green::before { background: linear-gradient(90deg, #A8D8B9, #C0C0C8); }
.kpi-card.c-amber::before { background: linear-gradient(90deg, #D4B886, #C0C0C8); }
.kpi-card.c-red::before   { background: linear-gradient(90deg, #E89999, #C0C0C8); }
.kpi-card.c-purple::before{ background: linear-gradient(90deg, #B8A8C8, #E8E8EC); }
.kpi-card.c-teal::before  { background: linear-gradient(90deg, #A8C4D8, #C0C0C8); }
.kpi-label { font-size: 0.67rem; color: var(--chrome-dark); font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }
.kpi-value { font-size: 1.55rem; font-weight: 900; color: var(--white); line-height: 1.15; font-feature-settings: "tnum" 1; }
.kpi-unit  { font-size: 0.82rem; color: var(--chrome-dark); font-weight: 500; }
.kpi-note  { font-size: 0.72rem; color: var(--text-muted); margin-top: 4px; }

/* ── Rank Badge ── */
.rank-badge-container { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 8px; }
.rank-badge {
    width: 96px; height: 96px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-direction: column;
    font-size: 2.6rem; font-weight: 900; color: white; line-height: 1;
    position: relative; border: 1px solid rgba(255,255,255,0.12);
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.2), 0 4px 24px rgba(0,0,0,0.7);
}
.rank-badge-label { font-size: 0.72rem; font-weight: 700; color: var(--chrome-dark); text-transform: uppercase; letter-spacing: 0.1em; }
/* Rank S: platinum-white — ultra-premium */
.rank-badge.r-S {
    background: linear-gradient(145deg, #F4F4F6 0%, #C0C0C8 40%, #8A8A90 100%);
    color: #0A0A0C;
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.6), 0 0 0 2px rgba(192,192,200,0.4), 0 8px 32px rgba(0,0,0,0.8);
    animation: pulse-ring 2.5s ease infinite;
}
/* Rank A: dark chrome */
.rank-badge.r-A {
    background: linear-gradient(145deg, #D4B886 0%, #A88860 50%, #7A6040 100%);
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.25), 0 0 0 1px rgba(212,184,134,0.3), 0 6px 24px rgba(0,0,0,0.7);
}
/* Rank B: gunmetal silver */
.rank-badge.r-B {
    background: linear-gradient(145deg, #A8A8B0 0%, #686870 50%, #404048 100%);
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.2), 0 6px 24px rgba(0,0,0,0.6);
}
/* Rank C: dark slate */
.rank-badge.r-C {
    background: linear-gradient(145deg, #3A3A3F, #1E1E22);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 4px 16px rgba(0,0,0,0.5);
}
/* Rank D: near-black */
.rank-badge.r-D {
    background: linear-gradient(145deg, #222224, #0A0A0C);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 10px rgba(0,0,0,0.5);
}

/* ── Decision Banner ── */
.decision-banner {
    border-radius: 12px; padding: 22px 28px; margin: 18px 0;
    position: relative; overflow: hidden; border: 1px solid;
    background: var(--bg-raised);
}
.decision-banner::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
}
.decision-banner::after {
    content: ''; position: absolute; top: -40%; right: -5%;
    width: 160px; height: 160px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.04), transparent);
}
.decision-banner.db-go {
    border-color: rgba(168,216,185,0.25);
    box-shadow: inset 0 1px 0 rgba(168,216,185,0.1), 0 4px 20px rgba(0,0,0,0.5);
}
.decision-banner.db-cond {
    border-color: rgba(212,184,134,0.25);
    box-shadow: inset 0 1px 0 rgba(212,184,134,0.1), 0 4px 20px rgba(0,0,0,0.5);
}
.decision-banner.db-nogo {
    border-color: rgba(232,153,153,0.25);
    box-shadow: inset 0 1px 0 rgba(232,153,153,0.1), 0 4px 20px rgba(0,0,0,0.5);
}
.db-title { font-size: 1.25rem; font-weight: 800; margin: 0 0 6px; }
.db-action { font-size: 0.92rem; color: var(--text-secondary); margin: 0; }
.db-go   .db-title { color: var(--success); }
.db-cond .db-title { color: var(--warning); }
.db-nogo .db-title { color: var(--error); }

/* ── Risk Cards ── */
.risk-card {
    border-radius: 10px; padding: 12px 16px; margin: 6px 0;
    display: flex; align-items: flex-start; gap: 12px;
    border: 1px solid; border-left-width: 3px;
    background: var(--bg-surface);
    transition: transform 0.15s ease, border-color 0.2s;
}
.risk-card:hover { transform: translateX(3px); }
.risk-card.rc-critical {
    border-color: rgba(232,153,153,0.2); border-left-color: var(--error);
}
.risk-card.rc-high {
    border-color: rgba(212,184,134,0.25); border-left-color: #C8A870;
}
.risk-card.rc-medium {
    border-color: rgba(212,184,134,0.15); border-left-color: var(--warning);
}
.risk-card.rc-low {
    border-color: rgba(168,216,185,0.18); border-left-color: var(--success);
}
.rc-icon { font-size: 1.1em; flex-shrink: 0; padding-top: 1px; }
.rc-title { font-weight: 700; font-size: 0.88rem; color: var(--off-white); margin-bottom: 2px; }
.rc-desc  { font-size: 0.8rem; color: var(--text-muted); line-height: 1.5; }

/* ── Buyer Rating ── */
.buyer-rating-card {
    background: var(--bg-raised);
    border-radius: 10px; padding: 14px 18px;
    border: 1px solid var(--border-subtle);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    margin: 8px 0; display: flex; align-items: center; gap: 14px;
    transition: border-color 0.2s ease;
}
.buyer-rating-card:hover { border-color: rgba(192,192,200,0.2); }
.buyer-name      { font-weight: 700; font-size: 0.88rem; color: var(--off-white); }
.buyer-type-badge{ font-size: 0.7rem; color: var(--text-muted); }
.buyer-stars     { font-size: 1.0rem; letter-spacing: 1px; margin: 3px 0; }
.buyer-threshold { font-size: 0.75rem; font-weight: 700; color: var(--chrome-light); }
.buyer-comment   { font-size: 0.75rem; color: var(--text-muted); }
.star-fill  { color: var(--warning); }
.star-empty { color: rgba(255,255,255,0.1); }

/* ── Section Header ── */
.sec-header {
    display: flex; align-items: center; gap: 10px;
    margin: 28px 0 16px; padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    position: relative;
}
.sec-header::after {
    content: ''; position: absolute; bottom: -1px; left: 0; width: 48px; height: 1px;
    background: linear-gradient(90deg, var(--chrome-mid), transparent);
}
.sec-header-icon  { font-size: 1.3em; }
.sec-header-title {
    font-size: 1.05rem; font-weight: 800; color: var(--white); margin: 0;
    letter-spacing: -0.01em;
}
.sec-header-badge {
    background: rgba(255,255,255,0.07); color: var(--chrome-light);
    font-size: 0.68rem; font-weight: 700;
    padding: 2px 10px; border-radius: 20px; letter-spacing: 0.08em; text-transform: uppercase;
    border: 1px solid rgba(255,255,255,0.1);
}

/* ── Score Ring ── */
.score-ring-outer { display: flex; flex-direction: column; align-items: center; position: relative; width: 110px; }
.score-ring-outer svg { overflow: visible; }
.score-ring-bg {}
.score-num { font-size: 1.7rem; font-weight: 900; color: var(--white); line-height: 1; font-feature-settings: "tnum" 1; }
.score-lbl { font-size: 0.62rem; color: var(--chrome-dark); font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }

/* ── Form Inputs ── */
.stTextInput input, .stNumberInput input {
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: #0C0C0E !important;
    color: var(--white) !important;
    font-size: 16px !important;
    padding: 8px 12px !important;
    transition: border-color 0.25s, box-shadow 0.25s !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.4) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: rgba(192,192,200,0.5) !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.4), 0 0 0 3px rgba(192,192,200,0.10) !important;
    outline: none !important;
}
.stTextInput input::placeholder, .stNumberInput input::placeholder { color: rgba(255,255,255,0.18) !important; }
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: #0C0C0E !important;
    color: var(--white) !important;
    font-size: 16px !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.4) !important;
}
.stTextArea textarea {
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: #0C0C0E !important;
    color: var(--white) !important;
    font-size: 16px !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.4) !important;
}
label { font-size: 0.8rem !important; font-weight: 600 !important; color: var(--chrome-dark) !important; letter-spacing: 0.02em !important; }
.stSelectbox [data-baseweb="select"] span { color: var(--white) !important; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important; font-weight: 700 !important;
    font-size: 0.9rem !important; letter-spacing: 0.03em !important;
    transition: all 0.25s ease !important;
    min-height: 44px !important; touch-action: manipulation !important;
    position: relative !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #D8D8DC 0%, #A0A0A8 45%, #787880 100%) !important;
    color: #0A0A0C !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.5), 0 4px 16px rgba(0,0,0,0.6), 0 1px 0 rgba(0,0,0,0.8) !important;
    text-shadow: 0 1px 0 rgba(255,255,255,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(180deg, #E8E8EC 0%, #B8B8C0 45%, #909098 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 6px 22px rgba(0,0,0,0.65), 0 1px 0 rgba(0,0,0,0.9) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid rgba(192,192,200,0.25) !important;
    color: var(--chrome-mid) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: rgba(232,232,236,0.45) !important;
    color: var(--chrome-light) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 0 18px rgba(192,192,200,0.10) !important;
    transform: translateY(-1px) !important;
}

/* ── File Uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1.5px dashed rgba(192,192,200,0.28) !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(232,232,236,0.45) !important;
    background: rgba(255,255,255,0.04) !important;
}
[data-testid="stFileUploader"] label { color: var(--text-muted) !important; }
[data-testid="stFileUploadDropzone"] {
    background: transparent !important;
    border: none !important;
}
[data-testid="stFileUploadDropzone"] span { color: var(--text-secondary) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-surface);
    border-radius: 10px; padding: 4px; gap: 3px;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important; font-weight: 700 !important; font-size: 0.82rem !important;
    color: var(--text-muted) !important; border: none !important; padding: 8px 16px !important;
    background: transparent !important; transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,255,255,0.07) !important;
    color: var(--off-white) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.12), 0 1px 4px rgba(0,0,0,0.4) !important;
}

/* ── Expanders ── */
details summary {
    border-radius: 8px !important; font-weight: 700 !important;
    font-size: 0.9rem !important; color: var(--off-white) !important;
    background: rgba(255,255,255,0.04) !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid="stExpander"] {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05) !important;
}

/* ── Dataframe ── */
.stDataFrame iframe { border-radius: 10px !important; }
.stDataFrame { background: var(--bg-raised) !important; border-radius: 10px !important; }

/* ── Metric ── */
[data-testid="metric-container"] {
    background: var(--bg-raised) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important; padding: 16px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06) !important;
}
[data-testid="metric-container"] label { font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.08em; color: var(--chrome-dark) !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800 !important; color: var(--white) !important; }

/* ── Alerts ── */
.stSuccess { background: rgba(168,216,185,0.06) !important; border-left: 3px solid var(--success) !important; border-radius: 8px !important; }
.stInfo    { background: rgba(168,196,216,0.06) !important; border-left: 3px solid var(--info) !important; border-radius: 8px !important; }
.stWarning { background: rgba(212,184,134,0.06) !important; border-left: 3px solid var(--warning) !important; border-radius: 8px !important; }
.stError   { background: rgba(232,153,153,0.06) !important; border-left: 3px solid var(--error) !important; border-radius: 8px !important; }
.stSuccess p, .stInfo p, .stWarning p, .stError p { color: var(--text-secondary) !important; }

/* ── Page Title / Hero ── */
.page-hero {
    background: linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(26,26,29,0.95) 100%);
    border: 1px solid var(--border-subtle);
    border-radius: 14px; padding: 28px 36px; margin-bottom: 28px;
    position: relative; overflow: hidden;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 32px rgba(0,0,0,0.6);
}
.page-hero::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(192,192,200,0.35), transparent);
}
.page-hero::after {
    content: ''; position: absolute; top: -40%; right: -5%;
    width: 260px; height: 260px; border-radius: 50%;
    background: radial-gradient(circle, rgba(192,192,200,0.05), transparent 65%);
    pointer-events: none;
}
.hero-title    { color: var(--white); font-size: 1.5rem; font-weight: 900; margin: 0 0 6px; z-index: 1; position: relative; letter-spacing: -0.02em; }
.hero-subtitle { color: var(--text-muted); font-size: 0.85rem; margin: 0; z-index: 1; position: relative; }
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.06); border: 1px solid rgba(192,192,200,0.22);
    color: var(--chrome-light); font-size: 0.72rem; font-weight: 700; padding: 3px 10px;
    border-radius: 20px; letter-spacing: 0.1em; text-transform: uppercase;
    margin-bottom: 10px; z-index: 1; position: relative;
}

/* ── Pro card ── */
.pro-card {
    background: var(--bg-raised);
    border-radius: 12px; padding: 22px 24px;
    border: 1px solid var(--border-subtle);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 20px rgba(0,0,0,0.45);
    margin-bottom: 16px; transition: border-color 0.25s ease, box-shadow 0.25s;
}
.pro-card:hover {
    border-color: rgba(192,192,200,0.18);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10), 0 8px 30px rgba(0,0,0,0.58);
}
.pro-card-title { font-size: 0.95rem; font-weight: 800; color: var(--white); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; letter-spacing: -0.01em; }

/* ── Progress ── */
.stProgress > div > div { border-radius: 6px !important; background: linear-gradient(90deg, #787880, #C0C0C8, #E8E8EC) !important; }
.stProgress > div { background: rgba(255,255,255,0.06) !important; border-radius: 6px !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: rgba(10,10,12,0.6); }
::-webkit-scrollbar-thumb { background: rgba(192,192,200,0.15); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(192,192,200,0.3); }

/* ── Divider ── */
hr {
    border: none !important;
    border-top: 1px solid rgba(255,255,255,0.07) !important;
    background: linear-gradient(90deg, transparent, rgba(192,192,200,0.2), transparent) !important;
    height: 1px !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: linear-gradient(180deg, #D8D8DC, #A0A0A8) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.4), 0 2px 6px rgba(0,0,0,0.6) !important;
}

/* ── Checkbox / Radio ── */
[data-testid="stCheckbox"] input { accent-color: var(--chrome-mid); }
[data-testid="stRadio"] input { accent-color: var(--chrome-mid); }

/* ── Number Input arrows ── */
.stNumberInput button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: var(--chrome-mid) !important;
    border-radius: 6px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08) !important;
}
.stNumberInput button:hover {
    background: rgba(255,255,255,0.09) !important;
    border-color: rgba(192,192,200,0.25) !important;
    color: var(--chrome-light) !important;
}

/* ── iOS/Mobile ── */
input[type="text"], input[type="number"], input[type="password"],
input[type="email"], select, textarea {
    font-size: 16px !important; -webkit-text-size-adjust: 100% !important;
}
* { -webkit-tap-highlight-color: rgba(0,0,0,0) !important; }
.main, [data-testid="stSidebar"], .block-container {
    -webkit-overflow-scrolling: touch !important;
}
html { scroll-behavior: smooth !important; }
.kpi-value, [data-testid="stMetricValue"], .score-num, .kpi-unit {
    font-feature-settings: "tnum" 1, "lnum" 1 !important;
    font-variant-numeric: tabular-nums !important;
}
::selection { background: rgba(192,192,200,0.2) !important; color: inherit !important; }

/* ── Focus Accessibility ── */
.stButton > button:focus-visible {
    outline: 2px solid rgba(192,192,200,0.6) !important; outline-offset: 2px !important;
    box-shadow: 0 0 0 4px rgba(192,192,200,0.12) !important;
}

/* ── Responsive: Tablet ── */
@media screen and (max-width: 1024px) {
    .main .block-container { padding: 1.25rem 1.5rem 2rem !important; }
    .kpi-row { grid-template-columns: repeat(3, 1fr) !important; gap: 10px !important; }
}

/* ── Responsive: Mobile ── */
@media screen and (max-width: 768px) {
    .main .block-container { padding: 0.75rem 0.875rem 3rem !important; max-width: 100% !important; }
    .kpi-row { grid-template-columns: repeat(2, 1fr) !important; gap: 8px !important; }
    .kpi-card { padding: 14px 16px !important; border-radius: 10px !important; }
    .kpi-value { font-size: 1.3rem !important; }
    .kpi-label { font-size: 0.65rem !important; }
    .page-hero { padding: 18px 20px !important; border-radius: 10px !important; margin-bottom: 18px !important; }
    .hero-title { font-size: 1.2rem !important; }
    .rank-badge { width: 80px !important; height: 80px !important; font-size: 2.1rem !important; }
    .decision-banner { padding: 14px 16px !important; border-radius: 10px !important; }
    .stTabs [data-baseweb="tab"] { padding: 7px 10px !important; font-size: 0.76rem !important; }
    [data-testid="stSidebar"][aria-expanded="true"] { width: min(280px, 88vw) !important; max-width: 88vw !important; }
    .score-ring-outer { width: 90px !important; }
    .score-ring-outer svg { width: 90px !important; height: 90px !important; }
    .score-num { font-size: 1.5rem !important; }
    .pdf-hero { padding: 28px 20px !important; }
    .pdf-hero-title { font-size: 1.1rem !important; }
}

/* ── Responsive: Small Mobile ── */
@media screen and (max-width: 480px) {
    .main .block-container { padding: 0.5rem 0.625rem 3rem !important; }
    .kpi-row { grid-template-columns: 1fr 1fr !important; gap: 7px !important; }
    .kpi-card { padding: 12px 13px !important; }
    .kpi-value { font-size: 1.15rem !important; }
    .stButton > button { min-height: 48px !important; }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.15rem !important; }
    h3 { font-size: 1rem !important; }
}

/* ── Print ── */
@media print {
    .stApp { background: white !important; }
    [data-testid="stSidebar"], .stButton, [data-testid="stToolbar"] { display: none !important; }
    .kpi-card, .pro-card { background: #f8f8f8 !important; border: 1px solid #ccc !important; break-inside: avoid !important; }
    .kpi-value, .score-num { color: #000 !important; }
    .kpi-label, .sec-header-title { color: #333 !important; }
}
</style>
""", unsafe_allow_html=True)

_RANK_COLORS = {"S": "#E8E8EC", "A": "#D4B886", "B": "#A8A8B0", "C": "#484850", "D": "#2A2A2E"}
_RISK_BADGES = {"critical": "🔴 致命的", "high": "🟠 高", "medium": "🟡 中", "low": "🟢 低"}


def get_rank_color(rank: str) -> str:
    return _RANK_COLORS.get(rank, "#000000")


def _rank_badge_html(rank: str, score: float) -> str:
    """ランクバッジのHTML生成"""
    labels = {"S": "最優良", "A": "優良", "B": "標準", "C": "要検討", "D": "見送り"}
    label = labels.get(rank, rank)
    return (
        f'<div class="rank-badge-container">'
        f'<div class="rank-badge r-{rank}">{rank}</div>'
        f'<div class="rank-badge-label">{label} / {score:.0f}点</div>'
        f'</div>'
    )


def _kpi_card_html(label: str, value: str, unit: str = "", color: str = "c-blue", note: str = "") -> str:
    """KPIカードのHTML生成"""
    note_html = f'<div class="kpi-note">{note}</div>' if note else ""
    return (
        f'<div class="kpi-card {color}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>'
        f'{note_html}'
        f'</div>'
    )


def _decision_banner_html(go_no_go: str, action: str) -> str:
    """GO/NO-GOバナーのHTML生成"""
    if "🟢" in go_no_go or "GO" in go_no_go.upper():
        cls, icon = "db-go", "🟢"
    elif "🟡" in go_no_go or "条件" in go_no_go:
        cls, icon = "db-cond", "🟡"
    elif "🔵" in go_no_go:
        cls, icon = "db-cond", "🔵"
    else:
        cls, icon = "db-nogo", "🔴"
    return (
        f'<div class="decision-banner {cls}">'
        f'<p class="db-title">{go_no_go}</p>'
        f'<p class="db-action">📍 今すぐやること: {action}</p>'
        f'</div>'
    )


def _risk_card_html(level: str, title: str, desc: str) -> str:
    """リスクカードのHTML生成"""
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    icon = icons.get(level, "⚪")
    return (
        f'<div class="risk-card rc-{level}">'
        f'<div class="rc-icon">{icon}</div>'
        f'<div><div class="rc-title">{title}</div>'
        f'<div class="rc-desc">{desc}</div></div>'
        f'</div>'
    )


def _buyer_rating_html(buyer_name: str, rating: int, comment: str, threshold: str = "") -> str:
    """バイヤー評価カードのHTML生成"""
    stars = '<span class="star-fill">★</span>' * rating + '<span class="star-empty">★</span>' * (5 - rating)
    threshold_html = f'<div class="buyer-threshold">{threshold}</div>' if threshold else ""
    return (
        f'<div class="buyer-rating-card">'
        f'<div style="flex:1">'
        f'<div class="buyer-name">{buyer_name}</div>'
        f'<div class="buyer-stars">{stars}</div>'
        f'<div class="buyer-comment">{comment}</div>'
        f'{threshold_html}'
        f'</div>'
        f'</div>'
    )


def _section_header_html(icon: str, title: str, badge: str = "") -> str:
    """セクションヘッダーのHTML生成"""
    badge_html = f'<span class="sec-header-badge">{badge}</span>' if badge else ""
    return (
        f'<div class="sec-header">'
        f'<span class="sec-header-icon">{icon}</span>'
        f'<span class="sec-header-title">{title}</span>'
        f'{badge_html}'
        f'</div>'
    )


def _page_title_html(icon: str, title: str, subtitle: str = "") -> str:
    """ページタイトルHTML（モノクロームラグジュアリーテーマ）"""
    sub = f'<div style="font-size:0.85rem;color:#9A9AA0;margin-top:4px;line-height:1.7;">{subtitle}</div>' if subtitle else ""
    return (
        f'<div style="margin-bottom:20px;animation:float-in 0.4s ease both;">'
        f'<h1 lang="ja" style="font-family:\'Noto Sans JP\',\'Inter\',\'Helvetica Neue\',sans-serif;'
        f'font-size:clamp(1.3rem,3vw,1.75rem);font-weight:900;'
        f'background:linear-gradient(135deg,#FFFFFF 0%,#E8E8EC 40%,#A8A8B0 100%);'
        f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        f'background-clip:text;margin:0 0 2px;letter-spacing:-0.02em;line-height:1.2;">'
        f'{icon} {title}</h1>'
        f'{sub}'
        f'</div>'
    )


def _score_ring_html(score: int, label: str = "スコア", color: str = "#C0C0C8") -> str:
    """スコアリングのSVG HTML生成（クロームシルバー調）"""
    pct = min(100, max(0, score))
    circumference = 2 * 3.14159 * 38
    dash = circumference * pct / 100
    # スコアに応じてクロームシルバー系の色を自動設定
    if score >= 80:
        color = "#E8E8EC"  # S/A: プラチナホワイト
        glow_color = "rgba(232,232,236,0.35)"
    elif score >= 70:
        color = "#D4B886"  # A: スモークドゴールド
        glow_color = "rgba(212,184,134,0.3)"
    elif score >= 55:
        color = "#A8A8B0"  # B: ガンメタルシルバー
        glow_color = "rgba(168,168,176,0.25)"
    else:
        color = "#484850"  # C/D: ダークスレート
        glow_color = "rgba(72,72,80,0.2)"
    return f"""
    <div class="score-ring-outer">
        <svg width="110" height="110" viewBox="0 0 110 110" style="transform:rotate(-90deg)">
            <defs>
                <filter id="glow-{score}">
                    <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
                    <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
                <linearGradient id="ring-grad-{score}" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="{color}" stop-opacity="0.6"/>
                    <stop offset="100%" stop-color="{color}" stop-opacity="1"/>
                </linearGradient>
            </defs>
            <circle class="score-ring-bg" cx="55" cy="55" r="38" stroke="rgba(255,255,255,0.07)" stroke-width="7" fill="none"/>
            <circle cx="55" cy="55" r="38" stroke="url(#ring-grad-{score})" stroke-width="7" fill="none"
                stroke-linecap="round" filter="url(#glow-{score})"
                stroke-dasharray="{dash:.1f} {circumference:.1f}"/>
        </svg>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-55%);text-align:center">
            <div class="score-num">{score}</div>
            <div class="score-lbl">{label}</div>
        </div>
    </div>"""


def _extract_pdf_via_gemini_vision(pdf_bytes: bytes) -> str:
    """
    スキャンPDF（テキストレイヤー無し）を Gemini Vision API に直接送って
    物件情報テキストを抽出する。Gemini は PDF を inlineData として受け取れる。
    """
    import base64
    import json
    import os
    import urllib.request
    import urllib.error

    # APIキー取得（Streamlit Secrets 優先、次に環境変数）
    api_key = ""
    try:
        import streamlit as _st
        api_key = _st.secrets.get("GEMINI_API_KEY", "")  # type: ignore
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "PDF読み込みエラー: スキャンPDFですがGEMINI_API_KEYが未設定のためOCRできません"

    # PDFサイズ上限チェック（Geminiは20MB / リクエストまで）
    if len(pdf_bytes) > 20 * 1024 * 1024:
        return "PDF読み込みエラー: PDFが大きすぎます（20MB超）。分割してください"

    b64 = base64.b64encode(pdf_bytes).decode('ascii')
    prompt = (
        "以下は不動産売物件の資料PDFです。OCRしてすべての記載情報をプレーンテキストで抽出してください。"
        "特に以下の項目を漏れなく拾ってください：物件名、所在地、最寄り駅、徒歩分数、売出価格、"
        "土地面積、建物面積、専有面積、構造、築年、用途地域、建ぺい率、容積率、満室想定年収、"
        "現況年収、表面利回り、実質利回り、稼働率、駐車場、エレベーター、レントロール（号室・賃料）、"
        "管理形態、修繕履歴、瑕疵情報、接道、商流（仲介履歴）、売主、売却理由。"
        "ページ区切りは `--- ページ N ---` の形式にしてください。"
    )
    body = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": "application/pdf", "data": b64}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {"maxOutputTokens": 8000, "temperature": 0.1}
    }

    # 試行モデル順 (v1beta で実在し PDF inlineData をサポートするもの)
    # 注: `gemini-1.5-pro` (suffix なし) は v1beta で 404。`-latest` または `-002` 等が必要
    candidate_models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-002",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-8b",
    ]
    errors = []   # 全試行のエラーを蓄積
    for model in candidate_models:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={api_key}")
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            # 成功レスポンス検証
            cands = result.get('candidates') or []
            if not cands:
                errors.append(f"{model}=空候補")
                continue
            parts = cands[0].get('content', {}).get('parts', [])
            text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict))
            if text and text.strip():
                return text
            errors.append(f"{model}=空テキスト")
            continue
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8', errors='replace')[:160]
            except Exception:
                err_body = str(e)[:160]
            errors.append(f"{model}=HTTP{e.code}")
            # 404 / 429 / 503 など、どんなエラーでも次のモデルへフォールバック継続
            continue
        except Exception as e:
            errors.append(f"{model}={type(e).__name__}")
            continue

    return f"PDF読み込みエラー: 全Geminiモデル失敗 [{' / '.join(errors)}]"


def _extract_pdf_text(uploaded_file) -> str:
    """
    PDFからテキスト抽出。
    1) PyMuPDFのネイティブテキスト抽出を試行
    2) テキストが空（=スキャンPDF）の場合は Gemini Vision にフォールバック
    """
    # アップロードされたファイルのバイト列を取得（streamlitのUploadedFileはreadで消費されるためseekで戻す）
    pdf_bytes = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    # ── ステップ1: PyMuPDF ネイティブ抽出
    fitz_err = None
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # 多モード抽出を順に試行（最も情報量の多い結果を採用）
            best = ""
            for mode in ("text", "blocks", "words"):
                try:
                    if mode == "text":
                        t = page.get_text("text")
                    elif mode == "blocks":
                        blocks = page.get_text("blocks") or []
                        t = "\n".join(b[4] for b in blocks if len(b) > 4 and b[4])
                    else:
                        words = page.get_text("words") or []
                        t = " ".join(w[4] for w in words if len(w) > 4 and w[4])
                except Exception:
                    t = ""
                if len(t.strip()) > len(best.strip()):
                    best = t
            if best.strip():
                texts.append(f"--- ページ {page_num + 1} ---\n{best}")
        doc.close()
        joined = "\n\n".join(texts).strip()
        if joined and len(joined) >= 30:
            return joined
        # テキストが極端に少ない → スキャンPDFと判断してVisionに送る
    except Exception as e:
        fitz_err = e

    # ── ステップ2: Gemini Vision フォールバック (スキャンPDF対応)
    vision_result = _extract_pdf_via_gemini_vision(pdf_bytes)
    if vision_result and not vision_result.startswith("PDF読み込みエラー"):
        # Visionで抽出成功
        return "[スキャンPDFをGemini Visionで抽出]\n\n" + vision_result

    # ── 両方失敗 → 詳細なエラーメッセージ
    msgs = []
    if fitz_err:
        msgs.append(f"PyMuPDF: {type(fitz_err).__name__}: {fitz_err}")
    msgs.append(vision_result)
    return "PDF読み込みエラー: " + " ／ ".join(msgs)


def render_pdf_upload_section():
    """PDF物件資料アップロードセクション（ヒーローUI）"""
    st.markdown("""
    <div class="pdf-hero">
        <div class="pdf-hero-icon">📄</div>
        <div class="pdf-hero-title">物件資料PDFをアップロード</div>
        <div class="pdf-hero-sub">
            1〜10ページの物件資料PDF対応 · 複数物件の一括抽出も可能<br>
            AIが自動で物件情報を読み取り、フォームに反映します
        </div>
        <div class="pdf-hero-badge">⚡ AI自動抽出 POWERED BY GEMINI</div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_pdf = st.file_uploader(
        "PDFファイルを選択またはドラッグ＆ドロップ",
        type=["pdf"],
        key="pdf_uploader",
        label_visibility="collapsed",
        help="物件資料PDF（1〜10ページ）をアップロードしてください"
    )

    if uploaded_pdf is not None:
        llm = get_llm_service()
        if not llm.is_available():
            st.warning("AIサービスが未設定のため自動抽出できません。テキストを手動でコピーしてください。")
            pdf_text = _extract_pdf_text(uploaded_pdf)
            with st.expander("📄 抽出テキスト（手動コピー用）"):
                st.text_area("", value=pdf_text, height=200, key="pdf_text_manual")
            return

        with st.spinner("📄 PDFを解析中...（スキャンPDFの場合は Gemini Vision にフォールバック）"):
            pdf_text = _extract_pdf_text(uploaded_pdf)

        if not pdf_text or pdf_text.startswith("PDF読み込みエラー"):
            st.error(f"❌ {pdf_text or 'PDF読み込みに失敗しました（空のテキスト）'}")
            st.info(
                "💡 対処法：①PDFがパスワード保護されていないか確認 "
                "②20MB以下に分割 "
                "③GEMINI_API_KEY が Streamlit Secrets に設定されているか確認 "
                "④下の「テキストから物件情報を自動抽出」エリアにテキストを手動貼付"
            )
            return

        # Vision使用時のバッジ
        if pdf_text.startswith("[スキャンPDFをGemini Visionで抽出]"):
            st.info("📷 スキャンPDFを検出。Gemini Vision でOCR抽出を実施しました。")

        st.success(f"✅ PDF読み込み完了（{len(pdf_text):,}文字）")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div style="background:rgba(0,200,255,0.05);border:1px solid rgba(0,200,255,0.15);
                 border-radius:10px;padding:10px 14px;font-size:0.8rem;color:#64748B;">
                📋 {uploaded_pdf.name} · {len(pdf_text):,}文字抽出済み
            </div>""", unsafe_allow_html=True)
        with col2:
            extract_btn = st.button("🤖 AI抽出実行", type="primary", use_container_width=True, key="pdf_extract_btn")

        if extract_btn:
            with st.spinner("🤖 AIが物件情報を抽出中...（10〜30秒）"):
                try:
                    extracted_json = llm.extract_property_from_text(pdf_text)
                    if extracted_json:
                        # セッション状態に保存してフォームへ反映
                        for k, v in extracted_json.items():
                            st.session_state[f"form_{k}"] = v
                        st.success("✅ 物件情報を抽出しました！下のフォームをご確認ください。")
                        st.rerun()
                    else:
                        st.warning("物件情報を抽出できませんでした。テキストを直接入力してください。")
                except RuntimeError as e:
                    if "RATE_LIMIT_429" in str(e):
                        st.warning(
                            "⏳ **APIレート制限中です。** Gemini APIの無料枠の上限に達しました。\n\n"
                            "📌 **対処法:** 1〜2分待ってから再度「AI抽出実行」を押してください。"
                        )
                    else:
                        st.error(f"抽出エラー: {e}")
                except Exception as e:
                    st.error(f"抽出エラー: {e}")

    st.divider()


def render_risk_badge(level: str) -> str:
    return _RISK_BADGES.get(level, level)


def _get_target_yield(service: DealJudgementService, prop: PropertyData) -> float:
    """_get_target_yield があれば使い、なければ service.target_yield にフォールバック"""
    if hasattr(service, "_get_target_yield"):
        return service._get_target_yield(prop)
    return service.target_yield


def _show_api_unavailable_warning():
    """AI APIが利用不可の場合にユーザーへ警告を表示する"""
    st.markdown("""
    <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);
         border-radius:12px;padding:12px 16px;margin-bottom:16px;
         display:flex;align-items:center;gap:10px;">
        <span style="font-size:1.2rem;">⚡</span>
        <div>
            <div style="font-weight:700;color:#F59E0B;font-size:0.85rem;">AI分析サービス未接続</div>
            <div style="color:#64748B;font-size:0.78rem;margin-top:2px;">
                GEMINI_API_KEY を Streamlit Secrets に設定することでAI自動抽出が有効になります。
                手動入力での基本分析は利用可能です。
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


@st.cache_resource
def get_judgement_service():
    """DealJudgementServiceをキャッシュ（毎クリックでCSV再読み込みを防止）"""
    return DealJudgementService()


@st.cache_resource
def get_llm_service():
    from app.services.llm_service import LLMService
    return LLMService()


def main():
    # Google Translate 自動翻訳防止（親documentのheadにnotranslate metaを注入）
    _components.html("""<script>
try {
    var p = window.parent.document;
    if (!p.querySelector('meta[name="google"][content="notranslate"]')) {
        var m = p.createElement('meta');
        m.name = 'google'; m.content = 'notranslate';
        p.head.appendChild(m);
    }
    p.documentElement.setAttribute('translate','no');
    p.documentElement.lang = 'ja';
    if (!p.documentElement.classList.contains('notranslate'))
        p.documentElement.classList.add('notranslate');
} catch(e) {}
</script>""", height=0, scrolling=False)

    # サイドバー
    with st.sidebar:
        _sb_logo = _logo_b64(40)
        _sb_logo_html = f'<img src="data:image/png;base64,{_sb_logo}" width="36" height="36" style="border-radius:8px;vertical-align:middle;margin-right:8px;" />' if _sb_logo else ""
        st.markdown(f"""
        <div lang="ja" style="padding:12px 0 8px;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                {_sb_logo_html}
                <div>
                    <div lang="ja" style="font-size:1.15rem;font-weight:900;
                         background:linear-gradient(90deg,#E8E8EC,#A8A8B0);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         background-clip:text;letter-spacing:-0.02em;line-height:1.2;
                         font-family:'Noto Sans JP','Inter',sans-serif;">
                        My Agent Match
                    </div>
                    <div style="font-size:0.58rem;color:#334155;margin-top:2px;
                         letter-spacing:0.1em;text-transform:uppercase;font-weight:600;">
                        NEURAL ESTATE · AI
                    </div>
                </div>
            </div>
            <div style="height:1px;background:linear-gradient(90deg,rgba(0,200,255,0.4),rgba(124,58,237,0.4),transparent);border-radius:1px;"></div>
        </div>""", unsafe_allow_html=True)
        st.divider()

        # バルクページから詳細分析へのナビゲーション
        _nav = st.session_state.pop("_nav_to", None)
        _page_options = [
            "🏠 ダッシュボード",
            "💬 AI チャット入力",
            "📋 案件分析",
            "📦 バルク案件",
            "📊 比較分析",
            "📁 保存済み案件",
            "❓ 使い方",
        ]
        # 初回起動時はダッシュボードをデフォルト表示。_nav_to があればそれを優先
        _default_idx = _page_options.index(_nav) if _nav and _nav in _page_options else 0

        page = st.radio(
            "メニュー",
            _page_options,
            index=_default_idx,
            label_visibility="collapsed"
        )

        st.divider()
        st.info("**使い方**\n\n1. 物件情報を入力\n2. 「分析実行」をクリック\n3. レポートを確認")

        st.markdown("""<div style='background:rgba(0,200,255,0.08);border:1px solid rgba(0,200,255,0.2);
    border-radius:8px;padding:8px 12px;font-size:0.72rem;color:#E8E8EC;margin-top:8px;'>
    🏢 <strong>業者取引モード</strong><br>
    <span style='color:#7DD3FC;font-size:0.68rem;'>エリア実勢Cap Rate自動適用<br>港区3.0% · 世田谷3.5% · 23区4.8%</span>
</div>""", unsafe_allow_html=True)

        # APIプロバイダー表示
        llm_svc_sidebar = get_llm_service()
        if llm_svc_sidebar.is_available():
            provider = llm_svc_sidebar.provider_name if hasattr(llm_svc_sidebar, 'provider_name') else "AI"
            # マルチプロバイダ時: 利用可能プロバイダ数を取得
            from app.services.llm_service import _MultiProviderClient
            _client = getattr(llm_svc_sidebar, 'client', None)
            if isinstance(_client, _MultiProviderClient):
                n_providers = len(_client._providers)
                sub_label = f"（{n_providers}プロバイダ待機中）" if n_providers > 1 else ""
            else:
                sub_label = ""
            st.markdown(f"""<div style='background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);
                border-radius:10px;padding:8px 12px;font-size:0.73rem;color:#10B981;font-weight:700;
                display:flex;align-items:center;gap:6px;'>
                <span style='display:inline-block;width:7px;height:7px;border-radius:50%;
                background:#10B981;box-shadow:0 0 6px rgba(16,185,129,0.6);flex-shrink:0;'></span>
                {provider} 接続中{sub_label}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style='background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.25);
                border-radius:10px;padding:8px 12px;font-size:0.73rem;color:#F59E0B;font-weight:700;
                display:flex;align-items:center;gap:6px;'>
                <span style='display:inline-block;width:7px;height:7px;border-radius:50%;
                background:#F59E0B;flex-shrink:0;'></span>
                APIキー未設定（Gemini/OpenAI/Grok/Anthropic）
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
<div style="font-size:0.65rem;color:#475569;line-height:1.5;padding:8px 0">
⚠️ <strong>免責事項</strong><br>
本ツールの分析結果は参考情報です。<br>
投資判断は必ずご自身の責任で行ってください。<br>
本サービスは投資助言を行うものではありません。
</div>
""", unsafe_allow_html=True)

    # API未接続時のメインコンテンツ上部警告
    if not get_llm_service().is_available():
        _show_api_unavailable_warning()

    if page == "🏠 ダッシュボード":
        render_dashboard_page()
    elif page == "💬 AI チャット入力":
        render_chat_input_page()
    elif page == "📋 案件分析":
        render_analysis_page()
    elif page == "📦 バルク案件":
        render_bulk_page()
    elif page == "📊 比較分析":
        render_comparison_page()
    elif page == "📁 保存済み案件":
        render_history_page()
    else:
        render_howto_page()


def _init_form_defaults():
    """セッション状態にフォームのデフォルト値を設定（未設定の場合のみ）"""
    if "_form_defaults_initialized" in st.session_state:
        return
    defaults = {
        "form_property_name": "",
        "form_asset_type": AssetType.APARTMENT_WHOLE.value,
        "form_address": "",
        "form_price": 100_000_000,
        "form_land_area": 0.0,
        "form_building_area": 0.0,
        "form_structure": "",
        "form_built_year": 2000,
        "form_gross_income": 0,
        "form_actual_income": 0,
        "form_market_annual_income": 0,
        "form_noi": 0,
        "form_occupancy_rate": 1.0,
        "form_gross_yield": 0.0,
        "form_zoning": "",
        "form_floor_area_ratio": 0.0,
        "form_building_coverage_ratio": 0.0,
        "form_road_access": "",
        "form_road_frontage_m": 0.0,
        "form_walk_minutes": 0,
        "form_seller_reason": "",
        "form_seller_motivation": "",
        "form_broker_chain_count": 1,
        "form_document_freshness_days": 0,
        "form_planned_repairs_cost": 0,
        "form_legal_notes": "",
        "form_notes": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    st.session_state["_form_defaults_initialized"] = True


def _apply_extracted_to_session_state(extracted: PropertyData):
    """AI抽出結果をセッション状態のフォームフィールドに反映"""
    asset_type_values = [e.value for e in AssetType]
    structure_options = ["", "RC造", "SRC造", "鉄骨造", "木造", "軽量鉄骨造"]
    seller_motivation_options = ["", "高い（早期売却希望）", "中程度", "低い（様子見）"]

    if extracted.property_name:
        st.session_state["form_property_name"] = extracted.property_name
    if extracted.asset_type and extracted.asset_type.value in asset_type_values:
        st.session_state["form_asset_type"] = extracted.asset_type.value
    if extracted.address:
        st.session_state["form_address"] = extracted.address
    if extracted.price:
        st.session_state["form_price"] = int(extracted.price)
    if extracted.land_area_sqm:
        st.session_state["form_land_area"] = float(extracted.land_area_sqm)
    if extracted.building_area_sqm:
        st.session_state["form_building_area"] = float(extracted.building_area_sqm)
    if extracted.structure and extracted.structure in structure_options:
        st.session_state["form_structure"] = extracted.structure
    if extracted.built_year and 1900 <= extracted.built_year <= _dt.date.today().year:
        st.session_state["form_built_year"] = int(extracted.built_year)
    if extracted.gross_income:
        st.session_state["form_gross_income"] = int(extracted.gross_income)
    if extracted.actual_income:
        st.session_state["form_actual_income"] = int(extracted.actual_income)
    if extracted.market_annual_income:
        st.session_state["form_market_annual_income"] = int(extracted.market_annual_income)
    if extracted.noi:
        st.session_state["form_noi"] = int(extracted.noi)
    if extracted.occupancy_rate is not None:
        st.session_state["form_occupancy_rate"] = float(extracted.occupancy_rate)
    if extracted.gross_yield is not None:
        st.session_state["form_gross_yield"] = float(extracted.gross_yield * 100)  # % に変換
    if extracted.zoning:
        st.session_state["form_zoning"] = extracted.zoning
    if extracted.floor_area_ratio is not None:
        st.session_state["form_floor_area_ratio"] = float(extracted.floor_area_ratio * 100)  # % に変換
    if extracted.building_coverage_ratio is not None:
        st.session_state["form_building_coverage_ratio"] = float(extracted.building_coverage_ratio * 100)
    if extracted.road_access:
        st.session_state["form_road_access"] = extracted.road_access
    if extracted.road_frontage_m:
        st.session_state["form_road_frontage_m"] = float(extracted.road_frontage_m)
    if extracted.walk_minutes_to_station:
        st.session_state["form_walk_minutes"] = int(extracted.walk_minutes_to_station)
    if extracted.seller_reason:
        st.session_state["form_seller_reason"] = extracted.seller_reason
    if extracted.seller_motivation and extracted.seller_motivation in seller_motivation_options:
        st.session_state["form_seller_motivation"] = extracted.seller_motivation
    if extracted.broker_chain_count:
        st.session_state["form_broker_chain_count"] = int(extracted.broker_chain_count)
    if extracted.planned_repairs_cost:
        st.session_state["form_planned_repairs_cost"] = int(extracted.planned_repairs_cost)
    if extracted.legal_notes:
        st.session_state["form_legal_notes"] = extracted.legal_notes
    if extracted.notes:
        st.session_state["form_notes"] = extracted.notes


def render_analysis_page():
    st.markdown(_page_title_html("📋", "案件分析", "物件情報を入力して案件の検討にふさわしいか判断します"), unsafe_allow_html=True)

    render_pdf_upload_section()

    _init_form_defaults()

    # テキストから自動抽出
    with st.expander("📝 テキストから物件情報を自動抽出（AI）", expanded=False):
        llm = get_llm_service()
        if not llm.is_available():
            st.warning("APIキー（Gemini/OpenAI/Grok/Anthropic いずれか）が設定されていないためAI抽出は使用できません。")
        else:
            paste_text = st.text_area(
                "物件情報テキストを貼り付けてください",
                height=200,
                placeholder="物件名、所在地、価格、利回りなどを含む物件概要を貼り付けてください..."
            )
            if st.button("🤖 AI で情報を抽出"):
                if paste_text:
                    extracted = None
                    rate_limited = False
                    with st.spinner("AIが物件情報を解析中..."):
                        try:
                            extracted = llm.extract_property_from_text(paste_text)
                        except RuntimeError as e:
                            if "RATE_LIMIT_429" in str(e):
                                rate_limited = True
                            else:
                                st.error(f"抽出エラー: {e}")
                    if rate_limited:
                        st.warning("⏳ **APIレート制限中です。** 1〜2分待ってから再試行してください。")
                    elif extracted:
                        _apply_extracted_to_session_state(extracted)
                        st.success("✅ 抽出成功！下のフォームに自動入力しました。内容を確認・修正してから「分析実行」してください。")
                        with st.expander("抽出された値を確認"):
                            st.json(extracted.model_dump(exclude_none=True))
                        st.rerun()
                    else:
                        st.error("抽出に失敗しました。テキストを確認してください。")

    with st.form("analysis_form"):
        # ── 基本情報 ──
        st.subheader("基本情報")
        col1, col2 = st.columns(2)
        with col1:
            property_name = st.text_input("物件名", placeholder="例）サンプル収益マンション",
                                          key="form_property_name")
            asset_type = st.selectbox(
                "物件種別 *",
                options=[e.value for e in AssetType],
                key="form_asset_type"
            )
        with col2:
            address = st.text_input("所在地 *", placeholder="例）東京都新宿区", key="form_address")
            price = st.number_input("売出価格（円）*", min_value=0, step=1_000_000,
                                    format="%d", key="form_price")

        # ── 建物・土地情報 ──
        st.subheader("建物・土地情報")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            land_area = st.number_input("土地面積（㎡）", min_value=0.0, step=1.0, key="form_land_area")
        with col2:
            building_area = st.number_input("建物面積（㎡）", min_value=0.0, step=1.0, key="form_building_area")
        with col3:
            structure = st.selectbox("構造", ["", "RC造", "SRC造", "鉄骨造", "木造", "軽量鉄骨造"],
                                     key="form_structure")
        with col4:
            built_year = st.number_input("築年（西暦）", min_value=1900,
                                         max_value=_dt.date.today().year, key="form_built_year")

        # ── 収益情報 ──
        st.subheader("収益情報")
        col1, col2, col3 = st.columns(3)
        with col1:
            gross_income = st.number_input("満室想定年収（円）", min_value=0, step=100_000,
                                           format="%d", key="form_gross_income")
            actual_income = st.number_input("現況年収（円）", min_value=0, step=100_000,
                                            format="%d", key="form_actual_income")
            market_annual_income = st.number_input(
                "相場年収（円）",
                min_value=0, step=100_000, format="%d",
                help="エリア相場賃料での満室想定年収。現況賃料との乖離から賃料アップサイドを評価します。",
                key="form_market_annual_income"
            )
        with col2:
            noi = st.number_input("NOI（円）", min_value=0, step=100_000, format="%d",
                                  help="Net Operating Income（純営業利益）。年間家賃収入から管理費・修繕費・固定資産税等の運営費を引いた実質収益",
                                  key="form_noi")
            occupancy_rate = st.slider("稼働率", min_value=0.0, max_value=1.0, step=0.01,
                                       format="%.0f%%",
                                       help="現在入居中の割合。1.0=満室。0.85以下は要注意",
                                       key="form_occupancy_rate")
        with col3:
            gross_yield_input = st.number_input("表面利回り（%）", min_value=0.0, step=0.1,
                                                key="form_gross_yield")

        # ── 法令・接道情報 ──
        st.subheader("法令・接道情報")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            zoning = st.text_input("用途地域", placeholder="例）近隣商業地域", key="form_zoning")
        with col2:
            floor_area_ratio = st.number_input(
                "容積率（%）", min_value=0.0, step=10.0,
                help="敷地面積に対する建物延床面積の割合。200%なら土地100㎡に200㎡の建物が建てられる。開発規模の根拠",
                key="form_floor_area_ratio")
        with col3:
            building_coverage_ratio = st.number_input("建蔽率（%）", min_value=0.0, step=5.0,
                                                       key="form_building_coverage_ratio")
        with col4:
            road_access = st.text_input("接道情報", placeholder="例）公道 6m接道", key="form_road_access")
        with col5:
            road_frontage_m = st.number_input("間口（m）", min_value=0.0, step=0.5,
                                               help="土地の前面道路への接道幅。マンション用地では18m以上が目安",
                                               key="form_road_frontage_m")
        with col6:
            walk_minutes = st.number_input("駅徒歩（分）", min_value=0, max_value=60, step=1,
                                            help="最寄駅からの徒歩分数。デベロッパー買取では10分以内が目安",
                                            key="form_walk_minutes")

        # ── 商流・売主情報 ──
        st.subheader("商流・売主情報")
        col1, col2, col3 = st.columns(3)
        with col1:
            seller_reason = st.text_input("売却理由", placeholder="例）相続、転居、事業縮小",
                                          key="form_seller_reason")
            seller_motivation = st.selectbox("売主温度感",
                                             ["", "高い（早期売却希望）", "中程度", "低い（様子見）"],
                                             key="form_seller_motivation")
        with col2:
            broker_chain_count = st.number_input(
                "商流の段数", min_value=1, max_value=10,
                help="紹介元が何社経由で来た情報か。1=元付け直接、2=1社挟む、4以上=情報が古く温度感不明なリスク",
                key="form_broker_chain_count")
            document_freshness_days = st.number_input("資料更新からの日数", min_value=0,
                                                       key="form_document_freshness_days")
        with col3:
            planned_repairs_cost = st.number_input("想定修繕費（円）", min_value=0, step=100_000,
                                                    format="%d", key="form_planned_repairs_cost")
            legal_notes = st.text_area("法的懸念事項", height=80, key="form_legal_notes")

        # ── 物件種別固有情報 ──
        selected_asset_type = AssetType(asset_type)
        if selected_asset_type == AssetType.UNIT:
            st.subheader("区分マンション固有情報")
            col1, col2 = st.columns(2)
            with col1:
                mgmt_fee = st.number_input("管理費（月額・円）", min_value=0, value=0, step=1000, format="%d")
            with col2:
                repair_reserve = st.number_input("修繕積立金（月額・円）", min_value=0, value=0, step=1000, format="%d")
        else:
            mgmt_fee, repair_reserve = 0, 0

        if selected_asset_type in (AssetType.COMMERCIAL, AssetType.OFFICE):
            st.subheader("商業・オフィス固有情報")
            col1, col2, col3 = st.columns(3)
            with col1:
                tenant_name = st.text_input("テナント名")
            with col2:
                lease_expiry_date = st.date_input("契約満了日", value=None, min_value=None, key="lease_expiry_date")
                lease_expiry = lease_expiry_date.strftime("%Y-%m-%d") if lease_expiry_date else ""
            with col3:
                lease_type = st.selectbox("賃貸借種類", ["", "普通借家", "定期借家"])
        else:
            tenant_name, lease_expiry, lease_type = "", "", ""

        if selected_asset_type == AssetType.FACTORY:
            st.subheader("工場・倉庫固有情報")
            truck_access = st.selectbox("トラック接車", ["", "大型トラック可", "中型まで可", "不可"])
        else:
            truck_access = ""

        notes = st.text_area("その他メモ", height=80, key="form_notes")

        # ── 融資・出口戦略の設定（任意） ──
        with st.expander("融資・出口戦略の設定（任意）"):
            loan_term = st.slider("返済期間（年）", 15, 35, 25)
            custom_rate = st.number_input(
                "カスタム金利（%）（空欄=自動）",
                min_value=0.0,
                max_value=10.0,
                value=0.0,
                step=0.1
            )

        submitted = st.form_submit_button("🔍 分析実行", type="primary", use_container_width=True)

    if submitted:
        if not address:
            st.error("所在地は必須です。")
            return
        if price <= 0:
            st.error("売出価格を入力してください。")
            return

        prop = PropertyData(
            property_name=property_name or None,
            asset_type=selected_asset_type,
            address=address,
            price=int(price),
            land_area_sqm=land_area or None,
            building_area_sqm=building_area or None,
            structure=structure or None,
            built_year=built_year if built_year > 1900 else None,
            gross_income=int(gross_income) if gross_income > 0 else None,
            actual_income=int(actual_income) if actual_income > 0 else None,
            market_annual_income=int(market_annual_income) if market_annual_income > 0 else None,
            noi=int(noi) if noi > 0 else None,
            occupancy_rate=occupancy_rate if occupancy_rate < 1.0 else None,
            gross_yield=gross_yield_input / 100 if gross_yield_input > 0 else None,
            zoning=zoning or None,
            floor_area_ratio=floor_area_ratio / 100 if floor_area_ratio > 0 else None,
            building_coverage_ratio=building_coverage_ratio / 100 if building_coverage_ratio > 0 else None,
            road_access=road_access or None,
            road_frontage_m=road_frontage_m if road_frontage_m > 0 else None,
            walk_minutes_to_station=int(walk_minutes) if walk_minutes > 0 else None,
            seller_reason=seller_reason or None,
            seller_motivation=seller_motivation or None,
            broker_chain_count=int(broker_chain_count),
            document_freshness_days=int(document_freshness_days) if document_freshness_days > 0 else None,
            planned_repairs_cost=int(planned_repairs_cost),
            legal_notes=legal_notes or None,
            notes=notes or None,
            management_fee_monthly=int(mgmt_fee) if mgmt_fee > 0 else None,
            repair_reserve_monthly=int(repair_reserve) if repair_reserve > 0 else None,
            tenant_name=tenant_name or None,
            lease_expiry=lease_expiry or None,
            lease_type=lease_type or None,
            truck_access=truck_access or None,
        )

        with st.spinner("分析中..."):
            service = get_judgement_service()
            # net_yield を事前計算
            calculated_net_yield = service.yield_engine.calculate_net_yield(prop.noi, prop.price)
            if prop.net_yield is None:
                prop.net_yield = calculated_net_yield

            target_yield = _get_target_yield(service, prop)
            income_value = service.price_engine.calculate_income_value(prop.noi, target_yield)
            price_result = service.price_engine.judge_price(prop.price, income_value)
            risks = service.risk_engine.detect_risks(prop)
            price_score = service.scoring_engine.price_score(price_result["status"])
            yield_score = service.yield_engine.score_yield(prop.net_yield, target_yield)
            liquidity_score = service.scoring_engine.liquidity_score(prop)
            development_score = service.development_engine.score_development(prop)
            risk_score = service.risk_engine.score_risk(risks)
            broker_score = service.scoring_engine.broker_score(prop.broker_chain_count, prop.seller_motivation)
            score_result = service.scoring_engine.total_score(
                price_score, yield_score, liquidity_score, development_score,
                risk_score, broker_score, asset_type=prop.asset_type
            )
            report = service.analyze(prop)

            # 各エンジンを直接呼び出してUIタブ用データを取得
            finance_engine = service.finance_engine
            exit_engine = service.exit_strategy_engine
            repair_engine = service.repair_cost_engine
            asset_type_key = finance_engine.get_asset_type_key(prop.asset_type.value)

            custom_rate_val = custom_rate if custom_rate > 0.0 else None
            try:
                finance_result: FinanceResult = finance_engine.simulate(
                    prop.price,
                    prop.noi,
                    asset_type_key,
                    loan_term_years=loan_term,
                    custom_rate=custom_rate_val,
                    built_year=prop.built_year,
                )
            except Exception as e:
                finance_result = None
                st.warning(f"融資シミュレーション計算中にエラーが発生しました: {e}")

            try:
                exit_result: ExitStrategyResult = exit_engine.evaluate(
                    prop.price,
                    prop.noi,
                    asset_type_key,
                    prop.address,
                    prop.built_year,
                    prop.occupancy_rate,
                )
            except Exception as e:
                exit_result = None
                st.warning(f"出口戦略評価中にエラーが発生しました: {e}")

            try:
                repair_result: RepairCostResult = repair_engine.estimate(
                    asset_type_key,
                    prop.building_area_sqm,
                    prop.built_year,
                    prop.structure,
                    prop.planned_repairs_cost,
                )
            except Exception as e:
                repair_result = None
                st.warning(f"修繕費積算中にエラーが発生しました: {e}")

            # デベロッパー用地分析（土地案件のみ）
            dev_land_result_ui: DevLandResult | None = None
            land_plan_analysis_result = None
            if prop.asset_type == AssetType.LAND:
                try:
                    dev_land_engine_ui = DeveloperLandEngine()
                    dev_land_result_ui = dev_land_engine_ui.analyze(
                        address=prop.address,
                        price=prop.price,
                        land_area_sqm=prop.land_area_sqm,
                        floor_area_ratio=prop.floor_area_ratio,
                        building_coverage_ratio=prop.building_coverage_ratio,
                        zoning=prop.zoning,
                    )
                except Exception as e:
                    dev_land_result_ui = None
                    st.warning(f"デベロッパー用地分析中にエラーが発生しました: {e}")

                # 用地プラン総合分析（土地案件のみ）
                if prop.land_area_sqm and prop.floor_area_ratio and prop.building_coverage_ratio:
                    try:
                        from app.engines.land_plan_engine import LandPlanEngine
                        lpe = LandPlanEngine()
                        land_plan_analysis_result = lpe.analyze(
                            address=prop.address,
                            price=prop.price,
                            land_area_sqm=prop.land_area_sqm,
                            far=prop.floor_area_ratio * 100,
                            bcr=prop.building_coverage_ratio * 100,
                            road_width_m=prop.road_frontage_m,
                            zoning=prop.zoning,
                            walk_minutes=prop.walk_minutes_to_station,
                        )
                    except Exception as e:
                        land_plan_analysis_result = None
                        st.warning(f"用地プラン分析中にエラーが発生しました: {e}")

            # バイヤーマッチング（土地・収益物件に対応）
            buyer_match_results = None
            _income_types = (
                AssetType.LAND, AssetType.APARTMENT_WHOLE, AssetType.APARTMENT_WOOD,
                AssetType.UNIT, AssetType.OFFICE, AssetType.COMMERCIAL,
            )
            if prop.asset_type in _income_types:
                try:
                    from app.engines.buyer_matching_engine import BuyerMatchingEngine
                    buyer_engine = BuyerMatchingEngine()
                    buyer_match_results = buyer_engine.match(
                        address=prop.address,
                        price=prop.price,
                        land_area_sqm=prop.land_area_sqm,
                        walk_minutes=prop.walk_minutes_to_station,
                        floor_area_ratio=prop.floor_area_ratio,
                        building_coverage_ratio=prop.building_coverage_ratio,
                        road_frontage_m=prop.road_frontage_m,
                        zoning=prop.zoning,
                        legal_notes=prop.legal_notes,
                        gross_yield=prop.gross_yield,
                        asset_type_str=prop.asset_type.value if prop.asset_type else None,
                    )
                except Exception as e:
                    buyer_match_results = None
                    st.warning(f"バイヤーマッチング中にエラーが発生しました: {e}")

        # ── 結果表示 ──
        st.divider()
        st.subheader("📊 分析結果")

        # ACTION BANNER: go_no_goと今日やることを最上部に大きく表示
        go_no_go_display = ""
        today_action_display = ""
        go_no_go_color = "#E74C3C"  # デフォルト赤
        for line in report.split('\n')[:15]:
            if any(e in line for e in ['🟢', '🟡', '🔵', '🔴']) and '**' in line:
                m = re.search(r'\*\*([🟢🟡🔵🔴][^*]+)\*\*', line)
                if m:
                    go_no_go_display = m.group(1).strip()
                    if '🟢' in go_no_go_display:
                        go_no_go_color = "#27AE60"
                    elif '🟡' in go_no_go_display:
                        go_no_go_color = "#F39C12"
                    elif '🔵' in go_no_go_display:
                        go_no_go_color = "#2980B9"
            if '📍 **今日やること**:' in line:
                today_action_display = line.split('📍 **今日やること**:')[-1].strip()

        if go_no_go_display:
            st.markdown(_decision_banner_html(go_no_go_display, today_action_display), unsafe_allow_html=True)

        # ランク表示（タブ外の共通ヘッダー）
        rank = score_result["rank"]
        total_score = score_result['total_score']

        # Hero Banner
        st.markdown(f"""
        <div class="page-hero">
            <div class="hero-badge">🏢 分析結果</div>
            <h2 class="hero-title">{prop.property_name or prop.address or "物件分析結果"}</h2>
            <p class="hero-subtitle">{prop.address} ｜ {prop.asset_type.value} ｜ {prop.price:,}円</p>
        </div>""", unsafe_allow_html=True)

        # ランク + スコアリング + 主要KPI
        col_rank, col_score, col_kpi = st.columns([1, 1, 4])
        with col_rank:
            st.markdown(_rank_badge_html(rank, total_score), unsafe_allow_html=True)
        with col_score:
            score_color = "#10B981" if total_score >= 70 else ("#F59E0B" if total_score >= 50 else "#EF4444")
            st.markdown(_score_ring_html(int(total_score), "総合スコア", score_color), unsafe_allow_html=True)
        with col_kpi:
            # KPIカードを横並びで表示
            kpi_html = '<div class="kpi-row">'
            kpi_html += _kpi_card_html("判断", score_result["judgement"], "", "c-blue")
            kpi_html += _kpi_card_html("価格評価", price_result["status"], "", "c-green" if "適正" in price_result["status"] or "割安" in price_result["status"] else "c-amber")
            if prop.gross_yield:
                kpi_html += _kpi_card_html("表面利回り", f"{prop.gross_yield*100:.2f}", "%", "c-teal")
            if prop.price:
                kpi_html += _kpi_card_html("売出価格", f"{prop.price//10000:,}", "万円", "c-purple")
            kpi_html += '</div>'
            st.markdown(kpi_html, unsafe_allow_html=True)

        # ── F3: 類似過去案件レコメンド ──
        try:
            _sim_svc = SimilarityService()
            _similar_cases = _sim_svc.find_similar(prop, top_k=3, min_similarity=0.3)
        except Exception:
            _similar_cases = []
        if _similar_cases:
            with st.expander(f"🔁 類似する過去案件 {len(_similar_cases)}件（前回の判断・結果を即座に思い出す）",
                              expanded=False):
                for sc in _similar_cases:
                    _yld = f"{sc.gross_yield*100:.2f}%" if sc.gross_yield else "-"
                    _rank_disp = sc.rank or "?"
                    _score = f"{sc.total_score}点" if sc.total_score is not None else "-"
                    _sim_pct = int(sc.similarity * 100)
                    _reasons = " · ".join(sc.match_reasons) if sc.match_reasons else ""
                    st.markdown(
                        f"<div style='display:grid;grid-template-columns:60px 1fr auto;gap:12px;"
                        f"align-items:center;padding:10px 14px;margin-bottom:6px;"
                        f"background:linear-gradient(180deg,rgba(232,232,236,0.04),rgba(0,0,0,0.3));"
                        f"border:1px solid rgba(232,232,236,0.08);border-radius:10px;'>"
                        f"<div style='text-align:center;font-size:1.2rem;font-weight:900;color:#E8E8EC;"
                        f"background:#1A1A1D;border:1.5px solid #A8A8B0;border-radius:8px;padding:8px 0;'>{_rank_disp}</div>"
                        f"<div>"
                        f"<div style='font-size:0.92rem;font-weight:700;color:#FFFFFF;margin-bottom:2px;'>"
                        f"{sc.property_name or sc.address}</div>"
                        f"<div style='font-size:0.74rem;color:#9A9AA0;'>{sc.address} ｜ {sc.asset_type} ｜ "
                        f"{sc.price//10000:,}万円 ｜ 利回り{_yld}</div>"
                        f"<div style='font-size:0.7rem;color:#D4B886;margin-top:3px;'>類似{_sim_pct}% — {_reasons}</div>"
                        f"</div>"
                        f"<div style='text-align:right;'>"
                        f"<div style='font-size:1rem;font-weight:800;color:#E8E8EC;'>{_score}</div>"
                        f"<div style='font-size:0.7rem;color:#686870;'>{sc.saved_at[:10] if sc.saved_at else ''}</div>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        # ── 共通: F2/ビジュアルレポート用に必要な追加データを準備 ──
        # 6軸スコア内訳
        component_scores = {
            "価格妥当性": price_score,
            "収益性":     yield_score,
            "流動性":     liquidity_score,
            "開発可能性": development_score,
            "リスク耐性": risk_score,
            "商流・売主": broker_score,
        }
        # 路線価分析（推定土地値・路線価比）
        try:
            rosenka_result = service.rosenka_engine.lookup(
                prop.address, prop.price, prop.land_area_sqm, prop.zoning
            )
        except Exception:
            rosenka_result = None
        # 推奨指値レンジ
        try:
            offer_result = service.offer_engine.calculate_offer_range(
                income_value, prop.planned_repairs_cost, risk_discount_rate=0.05
            )
        except Exception:
            offer_result = None

        # ── F2: AI セカンドオピニオン用にコンテキストをセッションに保存 ──
        st.session_state["_so_context_kwargs"] = dict(
            property_data=prop,
            score_result=score_result,
            price_result=price_result,
            finance_result=finance_result,
            risks=risks,
            component_scores=component_scores,
            rosenka_result=rosenka_result,
            exit_result=exit_result,
            target_yield=target_yield,
        )

        # ── ビジュアルレポート用データ集約（後段ボタンで使用） ──
        st.session_state["_visual_report_inputs"] = dict(
            prop=prop,
            score_result=score_result,
            price_result=price_result,
            finance_result=finance_result,
            exit_result=exit_result,
            offer_result=offer_result,
            rosenka_result=rosenka_result,
            risks=risks,
            component_scores=component_scores,
            target_yield=target_yield,
            income_value=income_value,
            today_action=today_action_display,
            go_no_go=go_no_go_display,
        )

        # ── タブ表示 ──
        _tab_labels = ["📊 総合判定", "🏦 融資分析", "🚪 出口戦略", "🔧 修繕費",
                       "🏢 買主マッチング", "📋 全レポート", "🧠 セカンドオピニオン"]
        if prop.asset_type == AssetType.LAND:
            _tab_labels.insert(5, "🏗️ 用地プラン分析")
        _tabs = st.tabs(_tab_labels)
        tab1 = _tabs[0]; tab2 = _tabs[1]; tab3 = _tabs[2]; tab4 = _tabs[3]
        if prop.asset_type == AssetType.LAND:
            tab5_buyer = _tabs[4]; tab_land_plan = _tabs[5]; tab6 = _tabs[6]
            tab_so = _tabs[7]
        else:
            tab5_buyer = _tabs[4]; tab_land_plan = None; tab6 = _tabs[5]
            tab_so = _tabs[6]

        with tab1:
            # スコア内訳
            st.subheader("📊 スコア内訳")
            scores = {
                "価格妥当性": price_score,
                "収益性": yield_score,
                "流動性": liquidity_score,
                "開発可能性": development_score,
                "リスク耐性": risk_score,
                "商流・売主": broker_score,
            }

            col_radar, col_gauge = st.columns([3, 2])

            with col_radar:
                # レーダーチャート
                categories = list(scores.keys())
                values = list(scores.values())
                values_closed = values + [values[0]]  # 閉じる
                categories_closed = categories + [categories[0]]

                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=values_closed,
                    theta=categories_closed,
                    fill='toself',
                    fillcolor='rgba(99, 179, 237, 0.3)',
                    line=dict(color='#4299E1', width=2),
                    marker=dict(color='#4299E1', size=8),
                    name='スコア'
                ))
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            tickfont=dict(size=10),
                            gridcolor='rgba(255,255,255,0.2)',
                            linecolor='rgba(255,255,255,0.3)',
                        ),
                        angularaxis=dict(
                            tickfont=dict(size=12, family=_plotly_font()),
                            linecolor='rgba(255,255,255,0.3)',
                            gridcolor='rgba(255,255,255,0.2)',
                        )
                    ),
                    showlegend=False,
                    margin=dict(l=60, r=60, t=30, b=30),
                    height=320,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(family=_plotly_font(), size=12)
                )
                st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})

            with col_gauge:
                # 総合スコアゲージ
                gauge_color = "#10B981" if total_score >= 70 else ("#F59E0B" if total_score >= 50 else "#EF4444")
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=total_score,
                    title={'text': "総合スコア", 'font': {'size': 14, 'family': _plotly_font()}},
                    number={'suffix': '/100', 'font': {'size': 28, 'color': gauge_color}},
                    gauge={
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#888"},
                        'bar': {'color': gauge_color, 'thickness': 0.6},
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 0,
                        'steps': [
                            {'range': [0, 50], 'color': 'rgba(239, 68, 68, 0.15)'},
                            {'range': [50, 70], 'color': 'rgba(245, 158, 11, 0.15)'},
                            {'range': [70, 100], 'color': 'rgba(16, 185, 129, 0.15)'},
                        ],
                        'threshold': {
                            'line': {'color': gauge_color, 'width': 3},
                            'thickness': 0.75,
                            'value': total_score
                        }
                    }
                ))
                fig_gauge.update_layout(
                    height=260,
                    margin=dict(l=20, r=20, t=40, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(family=_plotly_font())
                )
                st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

            # スコアバーチャート（6項目横並び）
            fig_bar = go.Figure()
            bar_colors = ['#10B981' if v >= 70 else '#F59E0B' if v >= 50 else '#EF4444' for v in values]
            fig_bar.add_trace(go.Bar(
                x=categories,
                y=values,
                marker_color=bar_colors,
                text=[f'{v}点' for v in values],
                textposition='outside',
                cliponaxis=False,
            ))
            fig_bar.update_layout(
                height=220,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 115], showgrid=True, gridcolor='rgba(0,0,0,0.1)', tickfont=dict(size=10)),
                xaxis=dict(tickfont=dict(size=11, family=_plotly_font())),
                font=dict(family=_plotly_font()),
                showlegend=False,
            )
            fig_bar.update_xaxes(showline=False)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

            # デベロッパー用地価格乖離の可視化（土地案件のみ）
            if dev_land_result_ui is not None:
                st.subheader("🏗️ デベロッパー用地分析")
                dr = dev_land_result_ui
                col1, col2, col3 = st.columns(3)
                col1.metric("売出価格", f"{prop.price:,}円")
                if dr.dev_max_land_price:
                    col2.metric("デベ最大買値", f"{dr.dev_max_land_price:,}円")
                    ratio = prop.price / dr.dev_max_land_price
                    gap_pct = (ratio - 1) * 100
                    delta_label = f"売値が{gap_pct:.0f}%高い" if gap_pct > 0 else f"デベ余裕あり"
                    col3.metric(
                        "乖離倍率（売値÷デベ最大）",
                        f"{ratio:.2f}倍",
                        delta=delta_label,
                        delta_color="inverse"
                    )
                    # バー可視化（デベ最大買値を100%として売値の割合を表示）
                    bar_val = min(dr.dev_max_land_price / prop.price, 1.0)
                    st.caption(
                        f"▼ デベが出せる上限（{dr.dev_max_land_price:,}円）に対する充足率"
                        f"　　信頼度: {dr.confidence}"
                    )
                    st.progress(bar_val)
                    if ratio <= 1.05:
                        st.success(f"✅ 売値はデベ上限以内（{ratio:.2f}倍） — 用地として成立の可能性あり")
                    elif ratio <= 1.20:
                        st.warning(f"⚠️ 売値がデベ上限の{ratio:.2f}倍 — 指値交渉で成立の余地あり")
                    else:
                        st.error(f"❌ 売値がデベ上限の{ratio:.2f}倍 — 現状では用地として成立しません")
                elif dr.dev_land_price_per_tsubo:
                    col2.metric("デベ上限坪単価", f"{dr.dev_land_price_per_tsubo:,}円/坪")
                    col3.metric("判定", dr.price_evaluation)
                st.caption(dr.comment)
                st.caption(f"マッチエリア: {dr.matched_area} ／ 開発タイプ: {dr.dev_type}")

            # リスク表示
            st.subheader(f"⚠️ 検出リスク（{len(risks)}件）")
            if risks:
                for risk in risks:
                    badge = render_risk_badge(risk["level"])
                    level_class = f"risk-{risk['level']}"
                    st.markdown(
                        f"<div class='{level_class}'>"
                        f"<b>{risk['type']}</b> {badge}<br>{risk['message']}</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.success("重大なリスクは検出されませんでした。")

        with tab2:
            st.subheader("🏦 融資シミュレーション")
            if finance_result is None:
                st.error("融資シミュレーションの結果を取得できませんでした。")
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric(
                    "DSCR（通常）",
                    f"{finance_result.dscr_base:.2f}" if finance_result.dscr_base is not None else "算出不可"
                )
                col2.metric(
                    "DSCR（ストレス）",
                    f"{finance_result.dscr_stress:.2f}" if finance_result.dscr_stress is not None else "算出不可"
                )
                col3.metric("融資可能性", finance_result.feasibility)

                st.caption(finance_result.comment)

                st.subheader("詳細")
                detail_df = pd.DataFrame({
                    "項目": [
                        "LTV",
                        "融資額",
                        "必要自己資金",
                        "月次返済（通常）",
                        "月次返済（ストレス）",
                        "年間返済額",
                        "適用金利",
                        "ストレス金利",
                        "返済期間",
                        "DSCR評価",
                    ],
                    "値": [
                        f"{finance_result.ltv:.0%}",
                        f"{finance_result.loan_amount:,}円",
                        f"{finance_result.equity_required:,}円",
                        f"{finance_result.monthly_payment_base:,}円",
                        f"{finance_result.monthly_payment_stress:,}円",
                        f"{finance_result.annual_debt_service:,}円",
                        f"{finance_result.interest_rate_used:.1f}%",
                        f"{finance_result.stress_rate:.1f}%",
                        f"{finance_result.loan_term_years}年",
                        finance_result.dscr_evaluation,
                    ],
                })
                st.table(detail_df)

                # DSCRビジュアライズ
                dscr_vals = []
                dscr_labels = []
                dscr_colors = []
                if finance_result.dscr_base is not None:
                    dscr_vals.append(finance_result.dscr_base)
                    dscr_labels.append('DSCR（通常）')
                    dscr_colors.append('#10B981' if finance_result.dscr_base >= 1.2 else '#F59E0B' if finance_result.dscr_base >= 1.0 else '#EF4444')
                if finance_result.dscr_stress is not None:
                    dscr_vals.append(finance_result.dscr_stress)
                    dscr_labels.append('DSCR（ストレス）')
                    dscr_colors.append('#10B981' if finance_result.dscr_stress >= 1.2 else '#F59E0B' if finance_result.dscr_stress >= 1.0 else '#EF4444')

                if dscr_vals:
                    fig_dscr = go.Figure()
                    fig_dscr.add_trace(go.Bar(
                        x=dscr_labels,
                        y=dscr_vals,
                        marker_color=dscr_colors,
                        text=[f'{v:.2f}' for v in dscr_vals],
                        textposition='outside',
                        width=0.4,
                    ))
                    # 基準線（1.2）
                    fig_dscr.add_hline(y=1.2, line_dash="dash", line_color="#10B981", annotation_text="安全圏(1.2)", annotation_position="right")
                    fig_dscr.add_hline(y=1.0, line_dash="dot", line_color="#EF4444", annotation_text="NG(1.0)", annotation_position="right")
                    fig_dscr.update_layout(
                        title="DSCR（返済余力）チャート",
                        height=280,
                        margin=dict(l=10, r=80, t=40, b=10),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis=dict(range=[0, max(dscr_vals)*1.4], gridcolor='rgba(0,0,0,0.1)'),
                        font=dict(family=_plotly_font(), size=12),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_dscr, use_container_width=True, config={'displayModeBar': False})

                # 資金構成ウォーターフォール
                if finance_result.loan_amount and finance_result.equity_required:
                    fig_waterfall = go.Figure(go.Waterfall(
                        name="資金構成",
                        orientation="v",
                        measure=["absolute", "relative", "total"],
                        x=["売出価格", "融資額", "自己資金"],
                        y=[prop.price / 10000, -finance_result.loan_amount / 10000, finance_result.equity_required / 10000],
                        text=[
                            f'{prop.price//10000:,}万',
                            f'-{finance_result.loan_amount//10000:,}万',
                            f'{finance_result.equity_required//10000:,}万',
                        ],
                        textposition="outside",
                        connector={"line": {"color": "rgba(99,179,237,0.5)"}},
                        increasing={"marker": {"color": "#4299E1"}},
                        decreasing={"marker": {"color": "#10B981"}},
                        totals={"marker": {"color": "#F59E0B"}},
                    ))
                    fig_waterfall.update_layout(
                        title='資金構成（万円）',
                        height=280,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis=dict(title='万円', gridcolor='rgba(0,0,0,0.1)'),
                        xaxis=dict(tickfont=dict(size=12, family=_plotly_font())),
                        font=dict(family=_plotly_font(), size=12),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_waterfall, use_container_width=True, config={'displayModeBar': False})

        with tab3:
            st.subheader("🚪 出口戦略評価")
            if exit_result is None:
                st.error("出口戦略評価の結果を取得できませんでした。")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("総合評価", exit_result.overall_evaluation)
                    st.metric("推奨シナリオ", exit_result.best_scenario)
                with col2:
                    st.metric("流動性見通し", exit_result.liquidity_outlook)
                    st.metric("想定買主", exit_result.buyer_type)

                if exit_result.scenarios:
                    st.subheader("シナリオ別シミュレーション")
                    scenarios_data = [
                        {
                            "シナリオ": s.name,
                            "保有年数": f"{s.holding_years}年",
                            "売却Cap Rate": f"{s.exit_cap_rate:.2%}",
                            "想定売却価格": f"{s.expected_exit_price:,}円",
                            "累積NOI": f"{s.total_noi_accumulated:,}円",
                            "トータルリターン": f"{s.total_return:.1%}",
                            "IRR（近似）": f"{s.irr_approx:.1%}",
                        }
                        for s in exit_result.scenarios
                    ]
                    st.dataframe(pd.DataFrame(scenarios_data), use_container_width=True)

                    # シナリオ比較チャート
                    if exit_result.scenarios:
                        scenario_names = [s.name for s in exit_result.scenarios]
                        irr_vals = [s.irr_approx * 100 for s in exit_result.scenarios]
                        total_returns = [s.total_return * 100 for s in exit_result.scenarios]

                        fig_scenario = go.Figure()
                        fig_scenario.add_trace(go.Bar(
                            name='IRR(%)',
                            x=scenario_names,
                            y=irr_vals,
                            marker_color='#4299E1',
                            yaxis='y',
                            text=[f'{v:.1f}%' for v in irr_vals],
                            textposition='outside',
                        ))
                        fig_scenario.add_trace(go.Scatter(
                            name='トータルリターン(%)',
                            x=scenario_names,
                            y=total_returns,
                            mode='lines+markers+text',
                            marker=dict(color='#F59E0B', size=10),
                            line=dict(color='#F59E0B', width=2),
                            text=[f'{v:.0f}%' for v in total_returns],
                            textposition='top center',
                            yaxis='y2',
                        ))
                        fig_scenario.update_layout(
                            title='出口シナリオ比較',
                            height=300,
                            margin=dict(l=20, r=60, t=40, b=10),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            yaxis=dict(title='IRR(%)', gridcolor='rgba(0,0,0,0.1)', side='left'),
                            yaxis2=dict(title='トータルリターン(%)', overlaying='y', side='right', showgrid=False),
                            font=dict(family=_plotly_font(), size=11),
                            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                            barmode='group',
                        )
                        st.plotly_chart(fig_scenario, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("NOIが設定されていないためシナリオシミュレーションは算出不可です。")

                st.subheader("推奨アクション")
                st.info(exit_result.recommendation)

                if exit_result.risk_factors:
                    st.subheader("出口リスク要因")
                    for rf in exit_result.risk_factors:
                        st.warning(rf)

        with tab4:
            st.subheader("🔧 修繕費積算")
            if repair_result is None:
                st.error("修繕費積算の結果を取得できませんでした。")
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric("即時対応", f"{repair_result.immediate_cost:,}円")
                col2.metric("5年以内", f"{repair_result.five_year_cost:,}円")
                col3.metric("10年以内", f"{repair_result.ten_year_cost:,}円")

                st.metric(
                    "ライフサイクル総修繕費",
                    f"{repair_result.total_lifecycle_cost:,}円",
                    help="即時＋5年以内＋10年以内＋20年以内の合計"
                )
                # 修繕費時系列バーチャート
                cost_labels = ['即時', '5年以内', '10年以内']
                cost_values = [repair_result.immediate_cost, repair_result.five_year_cost, repair_result.ten_year_cost]
                cost_colors = ['#EF4444', '#F59E0B', '#3B82F6']
                fig_repair = go.Figure()
                for label, value, color in zip(cost_labels, cost_values, cost_colors):
                    if value > 0:
                        fig_repair.add_trace(go.Bar(
                            name=label,
                            x=[label],
                            y=[value / 10000],
                            marker_color=color,
                            text=[f'{value//10000:,}万'],
                            textposition='outside',
                            cliponaxis=False,
                        ))
                # 合計ライン
                total_man = repair_result.total_lifecycle_cost / 10000
                fig_repair.update_layout(
                    title='修繕費タイムライン（万円）',
                    height=300,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title='万円', gridcolor='rgba(0,0,0,0.1)'),
                    xaxis=dict(tickfont=dict(size=12, family=_plotly_font())),
                    font=dict(family=_plotly_font(), size=12),
                    showlegend=False,
                    barmode='group',
                )
                if cost_values:
                    st.plotly_chart(fig_repair, use_container_width=True, config={'displayModeBar': False})
                st.caption(repair_result.comment)

                if repair_result.repair_items:
                    st.subheader("修繕項目明細")
                    items_data = [
                        {
                            "工事名称": item.name,
                            "緊急度": item.urgency,
                            "費用見積もり": f"{item.cost_estimate:,}円",
                            "単価": f"{item.unit_cost:,}",
                            "単位": item.unit,
                        }
                        for item in repair_result.repair_items
                    ]
                    st.dataframe(pd.DataFrame(items_data), use_container_width=True)
                else:
                    st.info("算出対象の修繕項目はありませんでした。")

        with tab5_buyer:
            st.subheader("🏢 買主マッチング（デベロッパー・投資家）")

            # 買主マッチング横棒チャート（サマリー）
            if buyer_match_results:
                sorted_results = sorted(buyer_match_results, key=lambda r: r.match_score, reverse=True)
                buyer_names = [r.buyer_short for r in sorted_results]
                buyer_scores = [r.match_score for r in sorted_results]
                buyer_verdicts = [r.verdict for r in sorted_results]
                bar_colors_buyer = []
                for v in buyer_verdicts:
                    if '◎' in v: bar_colors_buyer.append('#10B981')
                    elif '○' in v: bar_colors_buyer.append('#F59E0B')
                    elif '△' in v: bar_colors_buyer.append('#4299E1')
                    else: bar_colors_buyer.append('#EF4444')

                fig_buyers = go.Figure(go.Bar(
                    x=buyer_scores,
                    y=buyer_names,
                    orientation='h',
                    marker_color=bar_colors_buyer,
                    text=[f'{s}点 {v}' for s, v in zip(buyer_scores, buyer_verdicts)],
                    textposition='outside',
                    cliponaxis=False,
                ))
                fig_buyers.add_vline(x=50, line_dash="dash", line_color="#888", annotation_text="合致ライン(50)", annotation_position="top right")
                fig_buyers.update_layout(
                    title='バイヤースコア一覧（高スコア順）',
                    height=max(300, len(sorted_results) * 40 + 80),
                    margin=dict(l=10, r=120, t=40, b=10),
                    xaxis=dict(range=[0, 130], showgrid=True, gridcolor='rgba(0,0,0,0.1)'),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(family=_plotly_font(), size=11),
                    showlegend=False,
                )
                st.plotly_chart(fig_buyers, use_container_width=True, config={'displayModeBar': False})

            if buyer_match_results is None:
                st.info("土地・収益物件（一棟マンション・アパート・オフィス・商業）を選択すると、各バイヤーのクライテリアと照合したマッチング結果が表示されます。")
            else:
                # サマリーバー（上位マッチのみ）
                matched = [r for r in buyer_match_results if r.match_score >= 50]
                all_results = buyer_match_results

                verdict_colors = {
                    "◎ 合致":   "#2ECC71",
                    "○ 条件次第": "#F39C12",
                    "△ 要確認":  "#3498DB",
                    "× 不合致":  "#E74C3C",
                }

                if matched:
                    st.success(f"✅ {len(matched)}社が買取候補として合致しています（スコア50以上）")
                else:
                    st.warning("⚠️ 合致するデベロッパーは見つかりませんでした。条件の見直しをご検討ください。")

                # 全バイヤーをカード表示
                for r in all_results:
                    color = verdict_colors.get(r.verdict, "#888")
                    ng_badge = f" ｜ NG: {', '.join(r.ng_reasons[:2])}" if r.ng_reasons else ""
                    with st.expander(
                        f"{r.verdict}  {r.buyer_short}（{r.dev_type}）  スコア: {r.match_score}/100{ng_badge}",
                        expanded=(r.match_score >= 50)
                    ):
                        col_l, col_r = st.columns([2, 1])
                        with col_l:
                            st.markdown(f"**{r.buyer_name}**")
                            st.caption(r.dev_type)
                            st.info(r.summary)
                            if r.ng_reasons:
                                for ng in r.ng_reasons:
                                    st.error(f"❌ {ng}")
                        with col_r:
                            st.markdown(
                                f"<div style='text-align:center;padding:16px;border-radius:10px;"
                                f"background:{color}22;border:2px solid {color}'>"
                                f"<div style='font-size:2.2em;font-weight:bold;color:{color}'>"
                                f"{r.match_score}</div>"
                                f"<div style='font-size:0.85em;color:{color};margin-top:4px'>"
                                f"{r.verdict}</div></div>",
                                unsafe_allow_html=True
                            )

                        # チェック項目一覧
                        st.markdown("**チェック項目**")
                        status_icons = {"ok": "✅", "warn": "⚠️", "ng": "❌"}
                        check_data = [
                            {
                                "": status_icons.get(c["status"], "?"),
                                "項目": c["item"],
                                "結果": c["note"],
                            }
                            for c in r.checks
                        ]
                        if check_data:
                            st.dataframe(
                                pd.DataFrame(check_data),
                                use_container_width=True,
                                hide_index=True,
                            )

                        # ネクストアクション
                        if r.verdict in ("◎ 合致", "○ 条件次第"):
                            st.success(f"📋 **ネクストアクション:** {r.action}")
                        elif r.verdict == "△ 要確認":
                            st.warning(f"📋 **ネクストアクション:** {r.action}")
                        else:
                            st.error(f"📋 {r.action}")

        # ── 用地プラン分析タブ（土地案件のみ表示）──
        if tab_land_plan is not None:
            with tab_land_plan:
                _render_land_plan_tab(land_plan_analysis_result, prop, get_llm_service())

        with tab6:
            st.subheader("📋 詳細レポート")
            st.markdown(report)

        # ── F2: 🧠 AI セカンドオピニオン Q&A タブ ──
        with tab_so:
            st.subheader("🧠 AI セカンドオピニオン")
            st.caption(
                "分析結果すべてを文脈として保持しています。融資・出口・指値・買主・"
                "リスク等、もう一段の確認をしたい論点を自由に質問してください。"
            )

            # SecondOpinionService 初期化（セッションキャッシュ）
            _so_svc = st.session_state.get("_so_svc_instance")
            if _so_svc is None:
                _so_svc = SecondOpinionService()
                st.session_state["_so_svc_instance"] = _so_svc

            # 分析が走るたびにコンテキストを更新
            _so_kwargs = st.session_state.get("_so_context_kwargs")
            if _so_kwargs:
                _so_svc.set_context(**_so_kwargs)

            if not _so_svc.is_available():
                st.warning(
                    "LLM が利用できません。Streamlit Secrets の "
                    "GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY を確認してください。"
                )
            else:
                # チャット履歴
                _so_history_key = f"_so_history_{prop.address}_{prop.price}"
                if _so_history_key not in st.session_state:
                    st.session_state[_so_history_key] = []
                _history = st.session_state[_so_history_key]

                # 質問サジェスト（初回のみ）
                if not _history:
                    st.markdown(
                        "<div style='font-size:0.78rem;color:#9A9AA0;margin:6px 0 10px;'>"
                        "💡 例えばこんな質問ができます：</div>",
                        unsafe_allow_html=True,
                    )
                    sug_cols = st.columns(2)
                    suggestions = [
                        "この物件、銀行融資は通りそう？どこの金融機関がベスト？",
                        "指値はいくらが妥当？根拠も含めて教えて",
                        "売却出口はどのシナリオが現実的？",
                        "見送るべき決定的な理由はある？",
                    ]
                    for i, s in enumerate(suggestions):
                        if sug_cols[i % 2].button(f"💬 {s}", key=f"so_sug_{i}",
                                                   use_container_width=True):
                            st.session_state[f"_so_pending_q"] = s
                            st.rerun()

                # 過去のやりとり表示
                for msg in _history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                # 入力欄
                _pending = st.session_state.pop("_so_pending_q", None)
                _new_q = st.chat_input("質問を入力...") if _pending is None else _pending
                if _new_q:
                    _history.append({"role": "user", "content": _new_q})
                    with st.chat_message("user"):
                        st.markdown(_new_q)
                    with st.chat_message("assistant"):
                        with st.spinner("🧠 分析結果を踏まえて検討中..."):
                            _ans = _so_svc.ask(_new_q,
                                               chat_history=_history[:-1])
                        st.markdown(_ans)
                    _history.append({"role": "assistant", "content": _ans})
                    st.session_state[_so_history_key] = _history

                # クリアボタン
                if _history:
                    if st.button("🗑️ 会話をクリア", key="so_clear"):
                        st.session_state[_so_history_key] = []
                        st.rerun()

        # ダウンロード・保存
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.download_button(
                "📥 Markdown",
                data=report.encode("utf-8"),
                file_name=f"anken_report_{property_name or 'unnamed'}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col2:
            # 🎨 モノトーンビジュアルレポート (新標準)
            if st.button("🎨 ビジュアルPDF", use_container_width=True, type="primary",
                         help="白・黒・ライトシルバー基調のモノトーン金融ダッシュボード形式PDF"):
                with st.spinner("モノトーンビジュアルレポートを生成中..."):
                    try:
                        from app.services.visual_report_service import (
                            generate_visual_report, ReportInputs
                        )
                        import tempfile
                        vri = st.session_state.get("_visual_report_inputs", {})
                        # データ整形
                        _addr_meta = []
                        if prop.walk_minutes_to_station:
                            _addr_meta.append(f"徒歩{prop.walk_minutes_to_station}分")
                        if prop.built_year:
                            _addr_meta.append(f"築{prop.built_year}年")
                        if prop.structure:
                            _addr_meta.append(f"{prop.structure}造")
                        addr_full = prop.address + (
                            " ｜ " + " ｜ ".join(_addr_meta) if _addr_meta else ""
                        )
                        # 路線価評価額
                        _land_val = None
                        _ros_ratio = None
                        _ros = vri.get("rosenka_result")
                        if _ros and prop.land_area_sqm:
                            try:
                                if getattr(_ros, "land_price_per_sqm", None):
                                    _land_val = int(_ros.land_price_per_sqm * prop.land_area_sqm)
                                _ros_ratio = getattr(_ros, "rosenka_ratio", None)
                            except Exception: pass
                        # 出口戦略シナリオ
                        _exit_scen = []
                        _ex = vri.get("exit_result")
                        if _ex and getattr(_ex, "scenarios", None):
                            for s in _ex.scenarios[:3]:
                                _exit_scen.append((
                                    getattr(s, "name", ""),
                                    int(getattr(s, "sell_price", 0) or 0),
                                    float(getattr(s, "irr_approx", 0) or 0) * 100,
                                ))
                        # リスク
                        _risk_list = [
                            {"level": (r.get("level") or "INFO").upper(),
                             "type":  r.get("type", ""),
                             "message": r.get("message", "")}
                            for r in (vri.get("risks") or [])
                        ]
                        # 推奨指値
                        _of = vri.get("offer_result") or {}
                        _of_low = _of.get("offer_low") if isinstance(_of, dict) else None
                        _of_high = _of.get("offer_high") if isinstance(_of, dict) else None
                        # 推計NOI
                        _noi = prop.noi or int((prop.actual_income or prop.gross_income or 0) * 0.82)
                        # 判定文
                        _verdict = (vri.get("go_no_go") or "").strip() or score_result.get("judgement", "")
                        if vri.get("today_action"):
                            _verdict += f" ─ 今日: {vri['today_action'][:40]}"
                        # アクションプラン
                        _actions = [
                            ("URGENT", "今日中", "紹介元に売却理由・売主温度感を確認"),
                            ("URGENT", "今日中", "接道情報（種別・幅員）を取得"),
                            ("HIGH",   "今週中", "推奨指値の根拠資料を作成し打診"),
                            ("HIGH",   "今週中", "想定買主候補に非公式打診（出口確認）"),
                            ("CHECK",  "確認",   "レントロール最新版で現況・想定の整合性確認"),
                        ]
                        data = ReportInputs(
                            property_name=prop.property_name or prop.address,
                            address=addr_full,
                            rank=score_result.get("rank", "?"),
                            total_score=float(score_result.get("total_score", 0)),
                            price=prop.price,
                            income_value=vri.get("income_value"),
                            offer_low=_of_low, offer_high=_of_high,
                            actual_income=prop.actual_income,
                            noi=_noi,
                            gross_yield=prop.gross_yield,
                            target_yield=vri.get("target_yield"),
                            dscr=getattr(vri.get("finance_result"), "dscr_base", None),
                            occupancy_rate=prop.occupancy_rate or 1.0,
                            ltv=0.8,
                            built_year=prop.built_year,
                            structure=prop.structure,
                            land_area_sqm=prop.land_area_sqm,
                            building_area_sqm=prop.building_area_sqm,
                            asset_type=prop.asset_type.value if prop.asset_type else None,
                            estimated_land_value=_land_val,
                            rosenka_ratio=_ros_ratio,
                            component_scores=vri.get("component_scores", {}),
                            exit_scenarios=_exit_scen,
                            risks=_risk_list,
                            one_line_verdict=_verdict[:80],
                            actions=_actions,
                        )
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                            generate_visual_report(tmp.name, data)
                            tmp_path = tmp.name
                        with open(tmp_path, "rb") as f:
                            vr_bytes = f.read()
                        st.session_state["_vr_pdf_bytes"] = vr_bytes
                        st.session_state["_vr_pdf_name"] = f"MAM_{property_name or 'report'}.pdf"
                        st.success("✅ ビジュアルレポート生成完了")
                    except Exception as e:
                        import traceback
                        st.error(f"生成失敗: {type(e).__name__}: {e}")
                        st.code(traceback.format_exc()[:1500])
            # ダウンロードボタンは生成済みの場合のみ表示
            if st.session_state.get("_vr_pdf_bytes"):
                st.download_button(
                    "📥 ダウンロード",
                    data=st.session_state["_vr_pdf_bytes"],
                    file_name=st.session_state.get("_vr_pdf_name", "MAM_report.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_visual_pdf",
                )
        with col3:
            # テキスト版PDF (旧形式 / バックアップ)
            if st.button("📄 テキストPDF", use_container_width=True,
                         help="従来のMarkdownベースPDF（バックアップ用）"):
                from app.services.pdf_service import PDFService
                pdf_service = PDFService()
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = pdf_service.generate(report, tmp.name, property_name or "案件")
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                ext = "pdf" if pdf_path.endswith(".pdf") else "html"
                st.download_button(
                    f"📥 {ext.upper()}",
                    data=pdf_bytes,
                    file_name=f"anken_report_{property_name or 'unnamed'}.{ext}",
                    mime=f"application/{'pdf' if ext == 'pdf' else 'html'}",
                    use_container_width=True,
                    key="dl_text_pdf",
                )
        with col4:
            if st.button("💾 履歴保存", use_container_width=True):
                storage = StorageService()
                path = storage.save_deal(prop, report, score_result["total_score"], rank)
                st.success(f"保存: {os.path.basename(path)}")

        # AIアドバイス（API Key設定時のみ）
        llm_svc = get_llm_service()
        if llm_svc.is_available():
            with st.expander("🤖 AIアドバイスを取得", expanded=False):
                if st.button("AIにアドバイスを求める"):
                    with st.spinner("AIが分析中..."):
                        advice = llm_svc.generate_advice(report)
                    if advice:
                        st.markdown(advice)
                    else:
                        st.error("アドバイスの取得に失敗しました。")


def _render_land_plan_tab(analysis, prop, llm_svc):
    """🏗️ 用地プラン分析タブのUI描画"""
    st.subheader("🏗️ 用地プラン総合分析（7プランタイプ検証）")

    if analysis is None:
        st.info(
            "用地プラン分析には **土地面積・容積率・建蔽率** の入力が必要です。\n\n"
            "フォームで「土地面積(㎡)」「容積率」「建蔽率」を入力して再度実行してください。"
        )
        return

    # ── 基本指標ヘッダー ──
    st.markdown("### 📐 用地基本スペック")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("土地面積", f"{analysis.land_area_sqm:.1f}㎡\n({analysis.land_area_tsubo:.1f}坪)")
    c2.metric("容積率", f"{analysis.far_pct:.0f}%")
    c3.metric("建蔽率", f"{analysis.bcr_pct:.0f}%")
    c4.metric("最大延床", f"{analysis.max_floor_area_sqm:.0f}㎡")
    c5.metric("売出坪単価", f"{analysis.land_price_per_tsubo:,}円/坪")

    # ── 最適プランバナー ──
    if analysis.best_plan:
        best = next((s for s in analysis.scenarios if s.plan_name == analysis.best_plan), None)
        if best:
            verdict_color = "#27AE60" if best.recommendation == "追う" else (
                "#F39C12" if best.recommendation == "条件次第" else "#E74C3C"
            )
            st.markdown(
                f"""<div style='background:{verdict_color}18;border-left:6px solid {verdict_color};
                border-radius:8px;padding:16px 20px;margin:12px 0;'>
                <div style='font-size:1.3em;font-weight:bold;color:{verdict_color}'>
                🏆 最有力プラン: {best.plan_name}</div>
                <div style='margin-top:6px;font-size:1em;color:#333'>{analysis.top_buyer_recommendation}</div>
                </div>""",
                unsafe_allow_html=True
            )

    # ── プラン比較チャート ──
    if analysis and analysis.scenarios:
        plan_names = [s.plan_name for s in analysis.scenarios]
        plan_scores = [s.score for s in analysis.scenarios]
        plan_feasible = [s.is_feasible for s in analysis.scenarios]
        plan_revenues = [s.total_revenue / 10000 if s.total_revenue else 0 for s in analysis.scenarios]
        plan_max_prices = [s.max_land_price / 10000 if s.max_land_price else 0 for s in analysis.scenarios]

        bar_colors_plan = ['#10B981' if f else '#94A3B8' for f in plan_feasible]

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            # スコア比較バーチャート
            fig_plan_score = go.Figure(go.Bar(
                x=plan_names,
                y=plan_scores,
                marker_color=bar_colors_plan,
                text=[f'{s}点' for s in plan_scores],
                textposition='outside',
                cliponaxis=False,
            ))
            fig_plan_score.update_layout(
                title='プラン別スコア',
                height=280,
                margin=dict(l=10, r=10, t=40, b=60),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 120], gridcolor='rgba(0,0,0,0.1)'),
                xaxis=dict(tickangle=-30, tickfont=dict(size=10, family=_plotly_font())),
                font=dict(family=_plotly_font(), size=11),
                showlegend=False,
            )
            st.plotly_chart(fig_plan_score, use_container_width=True, config={'displayModeBar': False})

        with col_chart2:
            # 想定売上 vs デベ最大買値 比較
            fig_plan_rev = go.Figure()
            fig_plan_rev.add_trace(go.Bar(
                name='想定売上(万円)',
                x=plan_names,
                y=plan_revenues,
                marker_color='rgba(99, 179, 237, 0.8)',
            ))
            fig_plan_rev.add_trace(go.Bar(
                name='デベ最大買値(万円)',
                x=plan_names,
                y=plan_max_prices,
                marker_color='rgba(240, 147, 43, 0.8)',
            ))
            fig_plan_rev.update_layout(
                title='想定売上 vs デベ最大買値',
                barmode='group',
                height=280,
                margin=dict(l=10, r=10, t=40, b=60),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(gridcolor='rgba(0,0,0,0.1)', title='万円'),
                xaxis=dict(tickangle=-30, tickfont=dict(size=10, family=_plotly_font())),
                font=dict(family=_plotly_font(), size=11),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            st.plotly_chart(fig_plan_rev, use_container_width=True, config={'displayModeBar': False})

        # リスク vs 収益 散布図
        if any(s.gross_yield_pct for s in analysis.scenarios):
            fig_scatter = go.Figure()
            for i, s in enumerate(analysis.scenarios):
                fig_scatter.add_trace(go.Scatter(
                    x=[s.gross_yield_pct or 0],
                    y=[s.score],
                    mode='markers+text',
                    name=s.plan_name,
                    text=[s.plan_name],
                    textposition='top center',
                    marker=dict(
                        size=16,
                        color=bar_colors_plan[i],
                        opacity=0.8,
                    ),
                ))
            fig_scatter.update_layout(
                title='利回り vs スコア（バブルポジション分析）',
                height=300,
                margin=dict(l=40, r=20, t=40, b=40),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title='利回り(%)', gridcolor='rgba(0,0,0,0.1)'),
                yaxis=dict(title='スコア', gridcolor='rgba(0,0,0,0.1)'),
                font=dict(family=_plotly_font(), size=11),
                showlegend=False,
            )
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})

    # ── 7プランシナリオ比較表 ──
    st.markdown("### 📊 全7プラン収支比較")
    plan_rows = []
    for s in analysis.scenarios:
        feasible_mark = "✅" if s.is_feasible else "❌"
        stars = "★" * (s.buyer_ratings[0]["rating"] if s.buyer_ratings else 0)
        plan_rows.append({
            "": feasible_mark,
            "プランタイプ": s.plan_name,
            "構造": s.structure,
            "延床面積": f"{s.estimated_floor_area_sqm:.0f}㎡" if s.estimated_floor_area_sqm else "-",
            "戸数/室数": str(s.estimated_units) + "戸" if s.estimated_units else "-",
            "想定売上/評価額": f"{s.total_revenue/10000:,.0f}万円" if s.total_revenue else "-",
            "デベ最大買値": f"{s.max_land_price/10000:,.0f}万円" if s.max_land_price else "-",
            "価格評価": s.land_price_evaluation,
            "一種単価": f"{s.price_per_land_sqm:,}円/㎡" if s.price_per_land_sqm else "-",
            "二種単価": f"{s.price_per_floor_sqm:,}円/㎡" if s.price_per_floor_sqm else "-",
            "主力バイヤー評価": stars,
            "スコア": s.score,
        })
    if plan_rows:
        st.dataframe(
            pd.DataFrame(plan_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ── 各プラン詳細カード ──
    st.markdown("### 🔍 プラン別詳細分析")

    # スコア降順・実現可能プランを先頭に
    sorted_scenarios = sorted(
        analysis.scenarios,
        key=lambda s: (s.is_feasible, s.score),
        reverse=True,
    )

    _PLAN_ICONS = {
        "区分1K投資マンション": "🏙️",
        "ファミリーマンション": "🏠",
        "単身&ファミリーミックス": "🏘️",
        "商業施設": "🏪",
        "オフィスビル": "🏢",
        "ホテル": "🏨",
        "工場・倉庫": "🏭",
    }
    _EVAL_COLORS = {
        "割安": "#27AE60", "適正": "#2ECC71", "やや高い": "#F39C12",
        "高い": "#E74C3C", "高すぎる": "#C0392B", "評価不能": "#888",
    }

    for sc in sorted_scenarios:
        icon = _PLAN_ICONS.get(sc.plan_name, "🏗️")
        eval_color = _EVAL_COLORS.get(sc.land_price_evaluation, "#888")
        status = "✅ 実現可能" if sc.is_feasible else "❌ 実現困難"
        label = f"{icon} {sc.plan_name}　|　{status}　|　スコア: {sc.score}/100　|　{sc.land_price_evaluation}"
        with st.expander(label, expanded=(sc.plan_name == analysis.best_plan)):
            if not sc.is_feasible:
                st.error(f"❌ 実現不可の理由: {sc.feasibility_reason}")
                continue

            st.caption(f"実現可能性: {sc.feasibility_reason}")

            # 3列レイアウト
            col_left, col_mid, col_right = st.columns([3, 3, 2])

            with col_left:
                st.markdown("**📐 建築計画**")
                st.write(f"- 構造: {sc.structure}")
                st.write(f"- 延床面積: {sc.estimated_floor_area_sqm:.0f}㎡ ({sc.estimated_floor_area_tsubo:.1f}坪)" if sc.estimated_floor_area_sqm else "- 延床面積: -")
                st.write(f"- 想定階数: {sc.floors_estimated}階" if sc.floors_estimated else "- 想定階数: -")
                if sc.estimated_units:
                    label_unit = "室" if sc.plan_name == "ホテル" else "戸"
                    st.write(f"- 想定{label_unit}数: {sc.estimated_units}{label_unit}")
                    if sc.avg_unit_size_sqm:
                        st.write(f"- 平均専有面積: {sc.avg_unit_size_sqm:.0f}㎡")

                st.markdown("**💰 収支試算**")
                if sc.total_revenue:
                    st.write(f"- 想定売上/評価額: **{sc.total_revenue/10000:,.0f}万円**")
                if sc.construction_cost:
                    st.write(f"- 建築費: {sc.construction_cost/10000:,.0f}万円")
                if sc.soft_cost:
                    st.write(f"- 諸費用: {sc.soft_cost/10000:,.0f}万円")
                if sc.dev_profit:
                    st.write(f"- デベ利益目標: {sc.dev_profit/10000:,.0f}万円")
                if sc.max_land_price:
                    st.write(f"- **デベ最大買値: {sc.max_land_price/10000:,.0f}万円**")
                    residual_pct = sc.land_residual_ratio * 100
                    st.caption(f"（残地価率 {residual_pct:.0f}% ベース）")

            with col_mid:
                st.markdown("**📊 単価指標**")
                if sc.price_per_land_sqm:
                    st.write(f"- 一種単価（土地㎡当）: {sc.price_per_land_sqm:,}円/㎡")
                if sc.price_per_floor_sqm:
                    st.write(f"- 二種単価（延床㎡当）: {sc.price_per_floor_sqm:,}円/㎡")
                if sc.sale_price_per_sqm:
                    st.write(f"- 分譲/賃料換算単価: {sc.sale_price_per_sqm:,}円/㎡")
                if sc.gross_yield_pct:
                    st.write(f"- 利回り目線: {sc.gross_yield_pct:.1f}%")
                if sc.noi_annual:
                    st.write(f"- NOI（年間）: {sc.noi_annual/10000:,.0f}万円")

                st.markdown("**📈 価格評価**")
                if sc.price_vs_max is not None:
                    ratio_pct = sc.price_vs_max * 100
                    st.markdown(
                        f"<div style='background:{eval_color}22;border-left:4px solid {eval_color};"
                        f"border-radius:6px;padding:10px;margin:4px 0'>"
                        f"<b style='color:{eval_color}'>{sc.land_price_evaluation}</b><br>"
                        f"売値 / デベ最大買値 = {ratio_pct:.0f}%<br>"
                        f"<small>{sc.market_comment}</small></div>",
                        unsafe_allow_html=True
                    )
                rec_color = "#27AE60" if sc.recommendation == "追う" else (
                    "#F39C12" if sc.recommendation == "条件次第" else "#E74C3C"
                )
                st.markdown(
                    f"<div style='text-align:center;margin-top:8px;"
                    f"background:{rec_color}22;border-radius:6px;padding:8px'>"
                    f"<b style='color:{rec_color};font-size:1.2em'>{sc.recommendation}</b></div>",
                    unsafe_allow_html=True
                )

            with col_right:
                st.markdown("**🏢 バイヤー評価（5段階）**")
                for r in sc.buyer_ratings:
                    rating = r["rating"]
                    stars_filled = "★" * rating + "☆" * (5 - rating)
                    star_color = (
                        "#F39C12" if rating >= 4 else (
                            "#3498DB" if rating == 3 else "#E74C3C"
                        )
                    )
                    threshold_str = f"〜{r['price_threshold_man']:,}万円" if r.get("price_threshold_man") else ""
                    st.markdown(
                        f"<div style='margin-bottom:8px;padding:6px;background:#f8f8f8;border-radius:6px'>"
                        f"<div style='font-size:0.85em;font-weight:bold'>{r['buyer_type']}</div>"
                        f"<div style='color:{star_color};font-size:1.1em'>{stars_filled}</div>"
                        f"<div style='font-size:0.75em;color:#666'>{threshold_str}</div></div>",
                        unsafe_allow_html=True
                    )

    # ── スコアレーダーチャート（実現可能プランのみ）──
    feasible_scenarios = [s for s in analysis.scenarios if s.is_feasible]
    if len(feasible_scenarios) >= 2:
        st.markdown("### 📉 プランスコア比較")
        chart_data = pd.DataFrame({
            "プラン": [s.plan_name for s in feasible_scenarios],
            "スコア": [s.score for s in feasible_scenarios],
            "価格評価(%)": [
                max(0, 100 - int((s.price_vs_max - 1.0) * 200)) if s.price_vs_max else 50
                for s in feasible_scenarios
            ],
        }).set_index("プラン")
        st.bar_chart(chart_data["スコア"])

    # ── AI多専門家分析セクション ──
    st.divider()
    st.markdown("### 🤖 AI多専門家分析（4名のプロが評価）")

    if not llm_svc.is_available():
        st.info("🔑 APIキー（Gemini/OpenAI/Grok/Anthropic）を設定するとAI専門家分析が利用できます。")
    else:
        col_btn, col_note = st.columns([1, 3])
        with col_btn:
            run_ai = st.button("🚀 AI専門家分析を実行", type="primary", use_container_width=True)
        with col_note:
            st.caption("一級建築士・用地仕入れ担当・経済アナリスト・デベ販売担当の4名が用地を分析します。（約30-60秒）")

        if run_ai:
            from app.services.land_plan_service import LandPlanAnalysisService
            _svc = LandPlanAnalysisService()

            land_info_text = LandPlanAnalysisService.build_land_info_text(
                address=prop.address,
                price=prop.price,
                land_area_sqm=prop.land_area_sqm or 0,
                far=prop.floor_area_ratio * 100 if prop.floor_area_ratio else 0,
                bcr=prop.building_coverage_ratio * 100 if prop.building_coverage_ratio else 0,
                road_width_m=prop.road_frontage_m,
                zoning=prop.zoning,
                walk_minutes=prop.walk_minutes_to_station,
            )
            scenarios_text = LandPlanAnalysisService.build_scenarios_summary_text(
                analysis.scenarios if analysis else []
            )

            progress_bar = st.progress(0, text="専門家分析を実行中...")
            results_placeholder = st.empty()

            def _progress_cb(done, total):
                progress_bar.progress(
                    min(int(done / total * 80), 80),
                    text=f"専門家 {done}/{total} 人が分析完了..."
                )

            with st.spinner("4名の専門家が並列分析中..."):
                expert_results = _svc.analyze_all_experts(
                    land_info=land_info_text,
                    scenarios_summary=scenarios_text,
                    progress_callback=_progress_cb,
                )

            progress_bar.progress(90, text="最終推奨を生成中...")
            with st.spinner("総合推奨を統合中..."):
                overall = _svc.generate_overall_recommendation(
                    land_info=land_info_text,
                    scenarios_summary=scenarios_text,
                    expert_analyses=expert_results,
                )
            progress_bar.progress(100, text="分析完了！")
            progress_bar.empty()

            # 専門家パネルを4列で表示
            st.markdown("#### 📋 専門家別評価")
            experts = [
                ("🏗️ 一級建築士", expert_results.get("architect", ""), "#3498DB"),
                ("🏘️ 用地仕入れ担当", expert_results.get("land_acquisitioner", ""), "#27AE60"),
                ("📊 経済アナリスト", expert_results.get("economist", ""), "#E67E22"),
                ("🏢 デベ販売担当", expert_results.get("sales", ""), "#9B59B6"),
            ]
            col_e1, col_e2 = st.columns(2)
            for i, (title, content, color) in enumerate(experts):
                col = col_e1 if i % 2 == 0 else col_e2
                with col:
                    st.markdown(
                        f"<div style='background:{color}0F;border-left:4px solid {color};"
                        f"border-radius:8px;padding:14px;margin-bottom:12px'>"
                        f"<b style='color:{color}'>{title}</b></div>",
                        unsafe_allow_html=True
                    )
                    st.markdown(content)

            # 総合推奨
            st.markdown("#### 🏆 総合推奨レポート")
            st.markdown(
                f"<div style='background:#27AE6010;border:2px solid #27AE60;"
                f"border-radius:10px;padding:20px;margin-top:8px'>{overall}</div>",
                unsafe_allow_html=True
            )


def _render_bulk_howto():
    """バルク案件ページの使い方ガイド"""
    with st.expander("📖 使い方ガイド（はじめての方へ）", expanded=False):
        st.markdown("""
**🎯 このページでできること**
複数の物件情報（PDF・URL・テキスト）を一括でAIが読み取り、スコアリングして「追う／捨てる」を即判断できます。

**📥 入力方法（3種類）**
| 方法 | 使い方 |
|------|--------|
| 📄 テキスト貼り付け | PDFをコピーしてそのまま貼り付け。複数物件OK |
| 📎 PDFアップロード | 物件一覧PDFを直接アップロード |
| 🌐 URLから取得 | 翔栄グループ等の物件一覧ページURLを入力 |

**📊 スコアの見方（100点満点）**
- **市場相対利回り 40点** — エリアの期待Cap Rateとの差分で評価（東京4%は普通、地方4%は低い）
- **エリア×駅距離 30点** — 都心6区・23区・都下・主要都市・地方の区分
- **築年 20点** — 新築〜旧耐震まで段階評価
- **商流 10点** — 売主直（満点）〜3段以上（0点）

**🏷️ 判定ラベル**
🟢 即対応（70点〜）　🟡 要検討（55〜69点）　🟠 条件次第（40〜54点）　🔴 後回し（〜39点）

**✅ 判断記録の使い方**
各物件カードの「🟢 追う」「🟡 様子見」「🔴 見送り」ボタンを押して記録。
上部の行動リストに「追う」物件だけまとめて表示されます。
""")


def _transfer_to_analysis(it) -> None:
    """BulkPropertyItem の情報を案件分析フォームに転記してページ遷移"""
    _init_form_defaults()
    st.session_state["form_property_name"] = it.property_name or ""
    st.session_state["form_address"] = it.address or ""
    if it.price_man:
        st.session_state["form_price"] = int(it.price_man * 10_000)
    if it.gross_yield_pct:
        st.session_state["form_gross_yield"] = it.gross_yield_pct
    if it.built_year:
        st.session_state["form_built_year"] = it.built_year
    if it.walk_minutes:
        st.session_state["form_walk_minutes"] = it.walk_minutes
    if it.land_area_tsubo:
        st.session_state["form_land_area"] = it.land_area_tsubo * 3.3058
    if it.building_area_tsubo:
        st.session_state["form_building_area"] = it.building_area_tsubo * 3.3058
    if it.structure:
        for s in ["RC造", "SRC造", "鉄骨造", "木造", "軽量鉄骨造"]:
            if s in it.structure:
                st.session_state["form_structure"] = s
                break
    if it.annual_rent_man:
        st.session_state["form_gross_income"] = int(it.annual_rent_man * 10_000)
    if it.broker:
        st.session_state["form_broker_chain_count"] = 1 if "売主" in it.broker else 2
    _asset_map = {
        "一棟マンション": "一棟マンション", "一棟アパート": "一棟アパート",
        "区分マンション": "区分マンション", "戸建て": "戸建て",
        "土地": "土地", "商業・店舗": "商業・店舗",
        "オフィス": "オフィス", "工場・倉庫": "工場・倉庫",
    }
    st.session_state["form_asset_type"] = _asset_map.get(it.asset_type, "一棟マンション")
    st.session_state["_nav_to"] = "📋 案件分析"
    st.rerun()


def render_bulk_page():
    """📦 バルク案件 — PDF/URL/テキストから複数物件を一括抽出してランキング表示"""
    st.title("📦 バルク案件 一括スクリーニング")
    st.caption("PDF・URL・テキストから複数物件を一括抽出し、「追う／捨てる」を即判断")

    _render_bulk_howto()

    from app.engines.bulk_extractor import (
        BulkPropertyItem,
        extract_from_url,
        extract_from_pdf_bytes,
        DECISION_OPTIONS,
    )

    llm = get_llm_service()
    has_llm = llm.is_available()

    # ── 判断記録の初期化 ──────────────────────────────────────────────────────
    if "bulk_decisions" not in st.session_state:
        st.session_state["bulk_decisions"] = {}  # {source_index: decision_str}

    # ── 入力エリア（タブで3種類） ─────────────────────────────────────────────
    inp_tab1, inp_tab2, inp_tab3 = st.tabs(
        ["📄 テキスト貼り付け", "📎 PDFアップロード", "🌐 URLから取得"]
    )

    raw_text = ""

    with inp_tab1:
        st.markdown(
            "物件概要書・在庫一覧・ポートフォリオシートのテキストをそのまま貼り付けてください。"
            "PDF をコピーして貼り付けるだけで OK です。"
        )
        raw_text_input = st.text_area(
            "物件リストを貼り付け",
            height=240,
            placeholder=(
                "例）\n"
                "物件名: FACE 三軒茶屋\n"
                "価格: 13億3000万円　利回り: 4.01%\n"
                "所在: 東京都世田谷区三軒茶屋 1-32-7\n"
                "交通: 田園都市線「三軒茶屋」2分\n"
                "-----\n"
                "（複数物件はそのまま全て貼り付けてください）"
            ),
            key="bulk_text_input"
        )
        if raw_text_input:
            raw_text = raw_text_input

    with inp_tab2:
        st.markdown(
            "物件一覧の PDF をアップロードしてください。テキストレイヤーのある PDF はそのまま読み込まれます。"
        )
        pdf_file = st.file_uploader(
            "PDF をアップロード", type=["pdf"], key="bulk_pdf_upload"
        )
        if pdf_file:
            # PDFバイトをセッションに保存（タブ切替後も保持）
            pdf_bytes = pdf_file.read()
            st.session_state["bulk_pdf_bytes"] = pdf_bytes
            with st.spinner("PDF を読み込み中..."):
                pdf_text, err = extract_from_pdf_bytes(pdf_bytes)
            if err:
                st.error(f"PDF 読み込みエラー: {err}")
            else:
                st.success(f"✅ PDF 読み込み完了（{len(pdf_text):,} 文字）")
                with st.expander("読み込んだテキストを確認（先頭3,000文字）"):
                    st.text(pdf_text[:3000])
                raw_text = pdf_text
                st.session_state["bulk_fetched_text"] = pdf_text
        elif "bulk_pdf_bytes" in st.session_state and not raw_text:
            # タブ切替後の保持
            if "bulk_fetched_text" in st.session_state:
                raw_text = st.session_state["bulk_fetched_text"]

    with inp_tab3:
        st.markdown(
            "物件一覧が掲載されているページの URL を入力してください。"
            "（例: 翔栄グループの販売物件ページなど）"
        )
        col_url, col_btn = st.columns([4, 1])
        with col_url:
            url_input = st.text_input(
                "URL",
                placeholder="https://shoeigroup.co.jp/property-tokyo/",
                key="bulk_url_input"
            )
        with col_btn:
            st.write("")
            fetch_btn = st.button("取得", key="bulk_fetch_btn")

        if fetch_btn and url_input:
            with st.spinner(f"{url_input} を取得中..."):
                url_text, err = extract_from_url(url_input)
            if err:
                st.error(f"URL 取得エラー: {err}")
            else:
                st.success(f"✅ 取得完了（{len(url_text):,} 文字）")
                with st.expander("取得したテキストを確認（先頭3,000文字）"):
                    st.text(url_text[:3000])
                raw_text = url_text
                st.session_state["bulk_fetched_text"] = url_text

        if not raw_text and "bulk_fetched_text" in st.session_state:
            raw_text = st.session_state["bulk_fetched_text"]

    st.divider()

    # ── 抽出実行ボタン ────────────────────────────────────────────────────────
    col_exec, col_clear = st.columns([3, 1])
    with col_exec:
        if not has_llm:
            st.warning("⚠️ APIキー（Gemini/OpenAI/Grok/Anthropic いずれか）が未設定のため LLM 抽出は使用できません。")
        exec_btn = st.button(
            "🔍 物件を一括抽出してスクリーニング",
            type="primary",
            use_container_width=True,
            disabled=not raw_text
        )
    with col_clear:
        if st.button("🗑️ クリア", use_container_width=True):
            for k in ["bulk_results", "bulk_fetched_text", "bulk_pdf_bytes", "bulk_decisions"]:
                st.session_state.pop(k, None)
            st.rerun()

    if exec_btn and raw_text:
        # チャンク数を事前に計算してプログレスバーを表示
        from app.engines.bulk_extractor import get_text_chunks
        chunks = get_text_chunks(raw_text, max_chars=14000)
        total_chunks = len(chunks)

        status_text = st.empty()
        progress_bar = st.progress(0)

        def _on_progress(chunk_idx: int, total: int):
            pct = int((chunk_idx + 1) / max(total, 1) * 100)
            progress_bar.progress(min(pct, 99))
            status_text.caption(
                f"🔄 抽出中... チャンク {chunk_idx + 1}/{total}（テキストを {total} ブロックに分割）"
            )

        if has_llm:
            items = llm.extract_bulk_properties(raw_text, progress_callback=_on_progress)
        else:
            from app.engines.bulk_extractor import extract_from_text_simple
            items = extract_from_text_simple(raw_text)
            for it in items:
                it.compute_quick_score()

        progress_bar.progress(100)
        status_text.empty()
        progress_bar.empty()

        st.session_state["bulk_results"] = items
        # 判断記録をリセット（新しい抽出結果に合わせる）
        st.session_state["bulk_decisions"] = {}

    # ── 結果表示 ──────────────────────────────────────────────────────────────
    items: list[BulkPropertyItem] = st.session_state.get("bulk_results", [])

    if not items:
        st.info("👆 物件リストを入力して「一括抽出」を実行してください")
        return

    decisions: dict = st.session_state["bulk_decisions"]
    st.success(f"✅ **{len(items)} 件**の物件を抽出しました")

    # ── 判断サマリーバナー ────────────────────────────────────────────────────
    n_go   = sum(1 for v in decisions.values() if v == "🟢 追う")
    n_hold = sum(1 for v in decisions.values() if v == "🟡 様子見")
    n_drop = sum(1 for v in decisions.values() if v == "🔴 見送り")
    n_undecided = len(items) - len(decisions)

    st.markdown(
        f"""<div style='background:#1a1a2e;color:#fff;border-radius:10px;padding:14px 20px;
        display:flex;gap:32px;align-items:center;margin-bottom:8px'>
        <span style='font-size:1.1em;font-weight:bold'>📊 判断状況</span>
        <span>🟢 追う <b style='font-size:1.3em'>{n_go}</b></span>
        <span>🟡 様子見 <b style='font-size:1.3em'>{n_hold}</b></span>
        <span>🔴 見送り <b style='font-size:1.3em'>{n_drop}</b></span>
        <span style='color:#aaa'>未決定 {n_undecided}</span>
        </div>""",
        unsafe_allow_html=True
    )

    # ── 行動リスト（「追う」物件のみ） ───────────────────────────────────────
    go_items = [it for it in items if decisions.get(it.source_index) == "🟢 追う"]
    if go_items:
        with st.expander(f"🟢 行動リスト（追う案件 {len(go_items)} 件）", expanded=True):
            for i, it in enumerate(go_items, 1):
                price_str = f"{it.price_man:,.0f}万円" if it.price_man else "—"
                yield_str = f"{it.gross_yield_pct:.2f}%" if it.gross_yield_pct else "—"
                st.markdown(
                    f"**{i}. {it.property_name or '名称不明'}**　{price_str} / {yield_str}　"
                    f"{it.address[:30]}　[{it.area_label}]"
                )

    st.divider()

    # ── スコアサマリーカウンター ──────────────────────────────────────────────
    cnt: dict[str, int] = {"即対応": 0, "要検討": 0, "条件次第": 0, "後回し": 0}
    for it in items:
        cnt[it.quick_verdict] = cnt.get(it.quick_verdict, 0) + 1

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("🟢 即対応", cnt["即対応"])
    mc2.metric("🟡 要検討", cnt["要検討"])
    mc3.metric("🟠 条件次第", cnt["条件次第"])
    mc4.metric("🔴 後回し", cnt["後回し"])

    # ── フィルター・ソート ────────────────────────────────────────────────────
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 1, 1])
    with filter_col1:
        kw_search = st.text_input(
            "🔍 キーワード検索",
            placeholder="物件名・住所・駅名",
            key="bulk_kw_search"
        )
    with filter_col2:
        filter_verdict = st.multiselect(
            "判定フィルター",
            ["🟢 即対応", "🟡 要検討", "🟠 条件次第", "🔴 後回し"],
            default=["🟢 即対応", "🟡 要検討", "🟠 条件次第", "🔴 後回し"],
            key="bulk_filter_verdict"
        )
    with filter_col3:
        min_yield = st.number_input("最低利回り(%)", 0.0, 20.0, 0.0, 0.5, key="bulk_min_yield")
    with filter_col4:
        show_only_go = st.checkbox("🟢 追うのみ", key="bulk_show_go")

    sort_col1, sort_col2 = st.columns([2, 4])
    with sort_col1:
        sort_by = st.selectbox(
            "並び替え",
            ["スコア（高い順）", "利回り（高い順）", "価格（安い順）", "築年（新しい順）"],
            key="bulk_sort_by"
        )

    # フィルタリング
    def _match_kw(it) -> bool:
        if not kw_search:
            return True
        kw = kw_search.lower()
        return (
            kw in (it.property_name or "").lower()
            or kw in (it.address or "").lower()
            or kw in (it.station or "").lower()
        )

    filtered = [
        it for it in items
        if (f"{it.quick_emoji} {it.quick_verdict}" in filter_verdict)
        and (it.gross_yield_pct or 0) >= min_yield
        and _match_kw(it)
        and (not show_only_go or decisions.get(it.source_index) == "🟢 追う")
    ]

    # ソート
    if sort_by == "スコア（高い順）":
        filtered.sort(key=lambda x: x.quick_score, reverse=True)
    elif sort_by == "利回り（高い順）":
        filtered.sort(key=lambda x: x.gross_yield_pct or 0, reverse=True)
    elif sort_by == "価格（安い順）":
        filtered.sort(key=lambda x: x.price_man or 9_999_999)
    elif sort_by == "築年（新しい順）":
        filtered.sort(key=lambda x: x.built_year or 0, reverse=True)

    st.caption(f"表示: {len(filtered)} 件 / 全 {len(items)} 件")

    # ── ランキングテーブル ────────────────────────────────────────────────────
    verdict_colors = {
        "即対応":   "#2ECC71",
        "要検討":   "#F39C12",
        "条件次第": "#E67E22",
        "後回し":   "#E74C3C",
    }

    table_rows = []
    for it in filtered:
        mkt_delta = f"+{it.yield_vs_market:.1f}%" if it.yield_vs_market >= 0 else f"{it.yield_vs_market:.1f}%"
        table_rows.append({
            "判定": f"{it.quick_emoji} {it.quick_verdict}",
            "スコア": it.quick_score,
            "判断": decisions.get(it.source_index, "未決定"),
            "物件名": it.property_name or "（名称不明）",
            "所在地": it.address,
            "最寄駅": f"{it.station} {it.walk_minutes}分" if it.station else "—",
            "価格（万円）": f"{it.price_man:,.0f}" if it.price_man else "—",
            "表面利回り": f"{it.gross_yield_pct:.2f}%" if it.gross_yield_pct else "—",
            "市場比": mkt_delta if it.gross_yield_pct else "—",
            "期待利回り": f"{it.expected_yield:.1f}%",
            "築年": str(it.built_year) if it.built_year else "—",
            "戸数": str(it.units) if it.units else "—",
            "種別": it.asset_type,
            "商流": it.broker,
        })

    if table_rows:
        df_display = pd.DataFrame(table_rows)
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "スコア": st.column_config.ProgressColumn(
                    "スコア", min_value=0, max_value=100, format="%d"
                ),
            }
        )

    # ── CSV ダウンロード ──────────────────────────────────────────────────────
    if table_rows:
        import io
        csv_buf = io.StringIO()
        df_display.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 一覧CSVをダウンロード",
            data=csv_buf.getvalue().encode("utf-8-sig"),
            file_name="bulk_screening.csv",
            mime="text/csv"
        )

    st.divider()

    # ── 物件別カード詳細 ─────────────────────────────────────────────────────
    st.subheader("📋 物件別詳細")

    for it in filtered:
        color = verdict_colors.get(it.quick_verdict, "#888")
        price_str = f"{it.price_man:,.0f}万円" if it.price_man else "—"
        yield_str = f"{it.gross_yield_pct:.2f}%" if it.gross_yield_pct else "—"
        walk_str = f"{it.station} 徒歩{it.walk_minutes}分" if it.station else "（最寄駅不明）"
        current_decision = decisions.get(it.source_index, "未決定")

        # カードヘッダー
        expand_default = it.quick_verdict in ("即対応", "要検討")
        with st.expander(
            f"{it.quick_emoji} [{it.quick_score}点] {it.property_name or '名称不明'}"
            f"　{price_str} / {yield_str}　{it.address[:25]}",
            expanded=expand_default
        ):
            col_info, col_score = st.columns([3, 1])

            with col_info:
                # 基本指標
                ic1, ic2, ic3 = st.columns(3)
                ic1.metric("価格", price_str)
                if it.gross_yield_pct and it.expected_yield:
                    delta_val = f"市場比 {it.yield_vs_market:+.1f}%"
                    ic2.metric("表面利回り", yield_str, delta=delta_val)
                else:
                    ic2.metric("表面利回り", yield_str)
                ic3.metric("最寄駅", walk_str)

                ic4, ic5, ic6, ic7 = st.columns(4)
                ic4.metric("種別", it.asset_type or "—")
                ic5.metric("築年", str(it.built_year) if it.built_year else "—")
                ic6.metric("戸数", str(it.units) if it.units else "—")
                ic7.metric("商流", it.broker or "—")

                if it.land_area_tsubo or it.building_area_tsubo:
                    ic8, ic9, ic10 = st.columns(3)
                    ic8.metric("土地面積", f"{it.land_area_tsubo:.1f}坪" if it.land_area_tsubo else "—")
                    ic9.metric("延床面積", f"{it.building_area_tsubo:.1f}坪" if it.building_area_tsubo else "—")
                    ic10.metric("稼働率", f"{it.occupancy_pct:.0f}%" if it.occupancy_pct else "—")

                if it.annual_rent_man:
                    st.caption(f"年間賃料: {it.annual_rent_man:,.0f}万円")
                if it.notes:
                    st.info(f"📝 {it.notes[:200]}")

                # スコア根拠
                st.caption(
                    f"スコア内訳 — 利回り:{it.score_yield}pt (市場比{it.yield_vs_market:+.1f}% / 期待{it.expected_yield:.1f}%)"
                    f" ＋ エリア:{it.score_area}pt [{it.area_label}]"
                    f" ＋ 築年:{it.score_age}pt ＋ 商流:{it.score_broker}pt"
                )

            with col_score:
                # スコアカード
                st.markdown(
                    f"<div style='text-align:center;padding:16px;border-radius:10px;"
                    f"background:{color}22;border:2px solid {color}'>"
                    f"<div style='font-size:2.4em;font-weight:bold;color:{color}'>"
                    f"{it.quick_score}</div>"
                    f"<div style='font-size:0.85em;color:{color};margin-top:4px'>"
                    f"{it.quick_emoji} {it.quick_verdict}</div></div>",
                    unsafe_allow_html=True
                )

            st.markdown("---")

            # ── 判断ボタン ────────────────────────────────────────────────────
            st.markdown("**この案件をどうする？**")
            dec_cols = st.columns(4)
            dec_options = ["未決定", "🟢 追う", "🟡 様子見", "🔴 見送り"]
            for di, dec_opt in enumerate(dec_options):
                btn_type = "primary" if current_decision == dec_opt else "secondary"
                if dec_cols[di].button(
                    dec_opt,
                    key=f"dec_{it.source_index}_{di}",
                    type=btn_type,
                    use_container_width=True
                ):
                    if dec_opt == "未決定":
                        st.session_state["bulk_decisions"].pop(it.source_index, None)
                    else:
                        st.session_state["bulk_decisions"][it.source_index] = dec_opt
                    st.rerun()

            # ── 詳細分析ボタン ────────────────────────────────────────────────
            if st.button(
                "🔍 この物件を詳細分析する",
                key=f"bulk_detail_{it.source_index}",
                use_container_width=True
            ):
                _transfer_to_analysis(it)


def render_comparison_page():
    st.title("📊 比較分析")
    st.caption("複数の案件を並べて比較します")

    from app.services.comparison_service import ComparisonService

    SAMPLES = {
        "【サンプル】一棟マンション（東京）": PropertyData(
            property_name="サンプル収益マンション", asset_type=AssetType.APARTMENT_WHOLE,
            address="東京都新宿区", price=120_000_000,
            noi=7_200_000, occupancy_rate=0.92, built_year=1995,
            broker_chain_count=3, document_freshness_days=75, planned_repairs_cost=2_000_000,
            zoning="近隣商業地域", road_access="公道", floor_area_ratio=3.0,
        ),
        "【サンプル】木造アパート（大阪）": PropertyData(
            property_name="木造アパート", asset_type=AssetType.APARTMENT_WOOD,
            address="大阪府大阪市", price=50_000_000,
            noi=3_800_000, occupancy_rate=1.0, built_year=2005,
            seller_reason="相続", seller_motivation="高い", broker_chain_count=1,
            zoning="第一種住居地域", road_access="公道 4m",
        ),
        "【サンプル】区分マンション（渋谷）": PropertyData(
            property_name="区分マンション", asset_type=AssetType.UNIT,
            address="東京都渋谷区", price=25_000_000,
            noi=1_080_000, occupancy_rate=1.0, built_year=2010,
            seller_reason="転勤", seller_motivation="高い", broker_chain_count=1,
            management_fee_monthly=18000, repair_reserve_monthly=8000,
            zoning="第一種住居地域", road_access="公道",
        ),
        "【サンプル】更地（横浜）": PropertyData(
            property_name="更地", asset_type=AssetType.LAND,
            address="神奈川県横浜市", price=80_000_000,
            land_area_sqm=200.0, zoning="第一種住居地域",
            building_coverage_ratio=0.6, floor_area_ratio=2.0, road_access="公道 6m",
            seller_reason="相続", seller_motivation="高い", broker_chain_count=1,
        ),
    }

    # 保存済み案件を追加
    storage_svc = StorageService()
    saved_deals = storage_svc.list_deals()
    saved_props: dict[str, PropertyData] = {}
    for deal in saved_deals:
        fname = deal.get("filename", "")
        full = storage_svc.load_deal(fname)
        if full and full.get("property"):
            try:
                prop_data = PropertyData(**{
                    k: v for k, v in full["property"].items()
                    if v is not None
                })
                label = (
                    f"【保存済み】{deal.get('property_name') or '名称未設定'} "
                    f"| {deal.get('asset_type', '')} "
                    f"| {int(deal.get('price', 0)):,}円 "
                    f"| Rank {deal.get('rank', '-')}"
                )
                saved_props[label] = prop_data
            except Exception:
                pass

    all_options = list(SAMPLES.keys()) + list(saved_props.keys())

    if saved_props:
        st.info(f"💾 保存済み案件 {len(saved_props)}件 が選択肢に追加されました")

    selected = st.multiselect(
        "比較する案件を選択（2件以上）",
        options=all_options,
        default=list(SAMPLES.keys())[:2]
    )

    if len(selected) < 2:
        st.warning("2件以上選択してください。")
        return

    if st.button("🔍 比較実行", type="primary"):
        all_prop_map = {**SAMPLES, **saved_props}
        props = [all_prop_map[k] for k in selected if k in all_prop_map]
        with st.spinner("比較分析中..."):
            service = ComparisonService()
            report = service.compare(props)

        st.markdown(report)
        st.download_button(
            "📥 比較レポートをダウンロード",
            data=report.encode("utf-8"),
            file_name="comparison_report.md",
            mime="text/markdown"
        )


def render_history_page():
    st.title("📁 保存済み案件")
    storage = StorageService()
    deals = storage.list_deals()

    if not deals:
        st.info("保存済みの案件はありません。「案件分析」で分析後、「履歴に保存」をクリックしてください。")
        return

    st.caption(f"保存済み: {len(deals)}件")

    rank_filter = st.multiselect("ランクでフィルタ", ["S", "A", "B", "C", "D"], default=["S", "A", "B", "C", "D"])
    filtered = [d for d in deals if d.get("rank") in rank_filter]

    for deal in filtered:
        rank_color = get_rank_color(deal.get("rank", ""))
        with st.expander(
            f"**{deal.get('rank', '-')}** | "
            f"{deal.get('property_name') or '名称未設定'} | "
            f"{deal.get('asset_type', '')} | "
            f"{int(deal.get('price', 0)):,}円 | "
            f"スコア: {deal.get('score', '-')}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**保存日時:** {deal.get('saved_at', '')}")
                st.write(f"**所在地:** {deal.get('address', '')}")
            with col2:
                st.write(f"**ランク:** {deal.get('rank', '')}")
                st.write(f"**スコア:** {deal.get('score', '')}")
            full_data = storage.load_deal(deal.get("filename", ""))
            if full_data and full_data.get("report"):
                if st.button("📋 フルレポートを見る", key=f"report_{deal.get('filename', '')}"):
                    st.markdown(full_data["report"])
                st.download_button(
                    "📥 レポートをダウンロード",
                    data=full_data["report"].encode("utf-8"),
                    file_name=f"report_{deal.get('filename', '').replace('.json', '')}.md",
                    mime="text/markdown",
                    key=f"dl_{deal.get('filename', '')}",
                )


def render_howto_page():
    """マルチOS向け使い方説明ページ"""
    import platform as _plat

    # OS自動判定（サーバーサイド）
    _server_os = _plat.system()  # "Windows" / "Darwin" / "Linux"

    st.markdown("""
    <div style="margin-bottom:24px;">
        <h1 style="font-size:1.8rem;font-weight:900;margin:0 0 6px;
            background:linear-gradient(90deg,#E8E8EC,#A8A8B0);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            background-clip:text;">
            ❓ 使い方ガイド
        </h1>
        <p style="color:#94A3B8;font-size:0.88rem;margin:0;">
            Windows · macOS · Linux · iOS Safari — 全プラットフォーム対応
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ─── フィーチャーカード（機能概要）────────────────────────────────
    st.markdown("""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:28px;">
        <div style="background:rgba(0,200,255,0.06);border:1px solid rgba(0,200,255,0.2);
            border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:1.8rem;margin-bottom:6px;">📄</div>
            <div style="font-size:0.82rem;font-weight:700;color:#E8E8EC;margin-bottom:4px;">PDFアップロード</div>
            <div style="font-size:0.72rem;color:#94A3B8;">物件資料PDFをそのまま読み込み。AIが自動で情報を抽出します。</div>
        </div>
        <div style="background:rgba(124,58,237,0.06);border:1px solid rgba(124,58,237,0.2);
            border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:1.8rem;margin-bottom:6px;">🔍</div>
            <div style="font-size:0.82rem;font-weight:700;color:#D4B886;margin-bottom:4px;">AI案件分析</div>
            <div style="font-size:0.72rem;color:#94A3B8;">18のエンジンが価格・利回り・リスクを瞬時にスコアリング。</div>
        </div>
        <div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);
            border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:1.8rem;margin-bottom:6px;">📦</div>
            <div style="font-size:0.82rem;font-weight:700;color:#10B981;margin-bottom:4px;">バルクスクリーニング</div>
            <div style="font-size:0.72rem;color:#94A3B8;">複数物件を一括入力。一度に最大20件を瞬時に比較できます。</div>
        </div>
        <div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.2);
            border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:1.8rem;margin-bottom:6px;">📊</div>
            <div style="font-size:0.82rem;font-weight:700;color:#F59E0B;margin-bottom:4px;">比較・履歴</div>
            <div style="font-size:0.72rem;color:#94A3B8;">保存した案件を横並び比較。過去の判断を振り返れます。</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── OS別タブ ────────────────────────────────────────────────────
    # デフォルトタブをサーバーOSに合わせる
    _os_tabs = ["🪟 Windows", "🍎 macOS", "🐧 Linux", "📱 iOS Safari"]
    _default_os_index = {"Windows": 0, "Darwin": 1, "Linux": 2}.get(_server_os, 0)

    tab_win, tab_mac, tab_linux, tab_ios = st.tabs(_os_tabs)

    # ── Windows ────────────────────────────────────────────────────
    with tab_win:
        st.markdown("""
<div style="margin:16px 0 8px;">
    <span style="font-size:1.1rem;font-weight:800;color:#E8E8EC;">🪟 Windowsでの起動と利用</span>
</div>
""", unsafe_allow_html=True)

        st.markdown("#### ▶ アプリの起動")
        st.markdown("""
| 方法 | 手順 |
|---|---|
| **ダブルクリック起動（推奨）** | デスクトップの `MAM` ショートカットをダブルクリック |
| **バッチファイル** | `start.bat` をダブルクリック → ブラウザが自動起動 |
| **サイレント起動** | `start_silent.vbs` → コンソール非表示で起動 |
| **コマンドプロンプト** | 下記コマンドを実行 |
""")
        st.code(r'cd "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Match\my-agent-much"'
                '\nstreamlit run app/ui/streamlit_app.py', language="bat")

        st.markdown("#### ▶ PDFのアップロード方法")
        st.markdown("""
1. 「**📋 案件分析**」ページを開く
2. 上部の **「物件資料PDFをアップロード」** エリアをクリック
   → ファイルエクスプローラーが開く
3. 物件資料PDFを選択して「開く」
4. **「⚡ AIで物件情報を自動抽出」** ボタンをクリック
5. フォームに自動入力されたら内容を確認 → **「🔍 分析実行」**

> 💡 **ドラッグ&ドロップ対応**: エクスプローラーからPDFをアップロードエリアに直接ドロップできます。
""")

        st.markdown("#### ▶ スマホ・タブレットからのLANアクセス")
        st.code("streamlit run app/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8501",
                language="bat")
        st.info("起動後、同じWi-Fi内のスマホから `http://[PCのIPアドレス]:8501` にアクセス")

        st.markdown("#### ▶ ショートカットキー")
        st.markdown("""
| キー | 動作 |
|---|---|
| `Ctrl + Enter` | フォーム送信（分析実行） |
| `Ctrl + R` | ページリロード |
| `F5` | アプリ再起動 |
""")

    # ── macOS ──────────────────────────────────────────────────────
    with tab_mac:
        st.markdown("""
<div style="margin:16px 0 8px;">
    <span style="font-size:1.1rem;font-weight:800;color:#E8E8EC;">🍎 macOSでの起動と利用</span>
</div>
""", unsafe_allow_html=True)

        st.markdown("#### ▶ アプリの起動")
        st.markdown("""
**前提**: Python 3.9+ と Streamlit がインストール済みであること
""")
        st.code("""cd ~/path/to/my-agent-much
# 依存パッケージインストール（初回のみ）
pip install -r requirements.txt

# 起動
streamlit run app/ui/streamlit_app.py""", language="bash")

        st.markdown("""
起動後、ブラウザで `http://localhost:8501` が自動的に開きます。
自動で開かない場合は Safari / Chrome で手動アクセスしてください。
""")

        st.markdown("#### ▶ PDFのアップロード方法")
        st.markdown("""
1. 「**📋 案件分析**」ページを開く
2. 上部の **「物件資料PDFをアップロード」** エリアをクリック
   → Finder が開く
3. 物件資料PDFを選択して「開く」
4. **「⚡ AIで物件情報を自動抽出」** ボタンをクリック
5. フォームに自動入力されたら内容を確認 → **「🔍 分析実行」**

> 💡 **ドラッグ&ドロップ対応**: FinderからPDFをアップロードエリアに直接ドロップできます。
""")

        st.markdown("#### ▶ バックグラウンド起動（ターミナルを閉じても動かし続ける）")
        st.code("nohup streamlit run app/ui/streamlit_app.py &", language="bash")

        st.markdown("#### ▶ ショートカットキー")
        st.markdown("""
| キー | 動作 |
|---|---|
| `⌘ + Enter` | フォーム送信（分析実行） |
| `⌘ + R` | ページリロード |
""")

    # ── Linux ──────────────────────────────────────────────────────
    with tab_linux:
        st.markdown("""
<div style="margin:16px 0 8px;">
    <span style="font-size:1.1rem;font-weight:800;color:#E8E8EC;">🐧 Linuxでの起動と利用</span>
</div>
""", unsafe_allow_html=True)

        st.markdown("#### ▶ インストールと起動")
        st.code("""# Python 3.9+ が必要
python3 --version

# 仮想環境（推奨）
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージインストール
pip install -r requirements.txt

# 起動
streamlit run app/ui/streamlit_app.py --server.address 0.0.0.0""", language="bash")

        st.markdown("#### ▶ systemdサービス化（常時起動）")
        st.code("""# /etc/systemd/system/mam.service を作成
[Unit]
Description=My Agent Match
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/my-agent-much
ExecStart=/path/to/.venv/bin/streamlit run app/ui/streamlit_app.py --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target""", language="ini")
        st.code("sudo systemctl enable mam && sudo systemctl start mam", language="bash")

        st.markdown("#### ▶ Streamlit Cloud（クラウド版）")
        st.markdown("""
ローカルインストール不要でブラウザからすぐ使えます：
👉 **[https://my-agent-much.streamlit.app](https://my-agent-much.streamlit.app)**

| 項目 | 内容 |
|---|---|
| 推奨ブラウザ | Chrome / Firefox / Safari |
| 必要なもの | インターネット接続のみ |
| 無料で利用 | ✅ |
""")

    # ── iOS Safari ─────────────────────────────────────────────────
    with tab_ios:
        st.markdown("""
<div style="margin:16px 0 8px;">
    <span style="font-size:1.1rem;font-weight:800;color:#E8E8EC;">📱 iOS Safari での利用</span>
</div>
""", unsafe_allow_html=True)

        st.info("iOSではクラウド版（Streamlit Cloud）の利用を推奨します。インストール不要です。")

        st.markdown("#### ▶ クラウド版へのアクセス")
        st.code("https://my-agent-much.streamlit.app", language="text")
        st.markdown("""
1. Safari で上記URLを開く
2. 下部のツールバーから **「共有」** → **「ホーム画面に追加」**
   → アプリのように起動できます（PWA風ショートカット）
""")

        st.markdown("#### ▶ iOSでのPDFアップロード手順")
        st.markdown("""
1. 「**📋 案件分析**」ページを開く
2. **「物件資料PDFをアップロード」** エリアをタップ
3. **「ファイルを選択」** をタップ
4. 「**ファイル**」アプリ または「**写真**」から PDF を選択
   （メールで受け取ったPDFは「ファイル」→「ダウンロード」に保存されています）
5. **「⚡ AIで物件情報を自動抽出」** をタップ
6. 内容を確認して **「🔍 分析実行」** をタップ
""")

        st.markdown("#### ▶ iOS Safariの注意点")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**✅ 対応**
- PDF アップロード
- フォーム入力
- 分析実行・レポート表示
- バルクスクリーニング
- 横向き（ランドスケープ）対応
""")
        with col2:
            st.markdown("""
**⚠️ 制限事項**
- PDFダウンロードはSafariの制限に従う
  （レポートDLはiOSのファイルアプリに保存）
- Popupブロックが有効だと一部動作が異なる場合あり
""")

        st.markdown("#### ▶ PCからLAN経由でスマホ接続する場合")
        st.markdown("""
PCでStreamlitをLANモードで起動している場合は、iPhoneのSafariから：
```
http://[PCのIPアドレス]:8501
```
でアクセスできます（同じWi-Fiが必要）。
""")

    # ─── よくある質問 ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
<div style="font-size:1.0rem;font-weight:800;color:#E8E8EC;margin:16px 0 12px;">
    💬 よくある質問
</div>
""", unsafe_allow_html=True)

    with st.expander("⚡ 「AI分析サービス未接続」と表示される"):
        st.markdown("""
**原因**: GEMINI_API_KEY が設定されていません。

**ローカル環境の場合**: `.streamlit/secrets.toml` を開き、以下を追加してください：
```toml
GEMINI_API_KEY = "AIzaSy..."
```
設定後、アプリを再起動してください。

**クラウド版の場合**: [share.streamlit.io](https://share.streamlit.io) → App Settings → Secrets で設定します。

> ⚠️ APIキーがなくても**手動入力による基本分析**は利用できます。
""")

    with st.expander("📄 PDFが読み込めない / 文字化けする"):
        st.markdown("""
- **対応形式**: テキスト埋め込みPDF（スキャンした画像PDFは非対応）
- **ファイルサイズ**: 最大200MB
- **ページ数**: 1〜10ページを推奨
- スキャンPDFの場合は、テキストをコピーして「テキストから自動抽出」欄に貼り付けてください
""")

    with st.expander("📦 バルク案件で複数物件を一度に分析したい"):
        st.markdown("""
1. サイドバーの「**📦 バルク案件**」をクリック
2. テキストエリアに複数物件の情報を貼り付け
   （1物件ずつ空行で区切るか、箇条書きで列挙）
3. 「**バルクスクリーニング実行**」をクリック
4. 一覧からスコアの高い案件を詳細分析へ送れます

1ページに複数物件が掲載されたPDFの場合もバルクページで処理できます。
""")

    with st.expander("💾 分析結果を保存・共有したい"):
        st.markdown("""
**保存方法**:
- 分析完了後、レポート下部の「**💾 履歴に保存**」をクリック

**共有方法**:
- 「📥 レポートをダウンロード」でMarkdownファイルとして保存
- 「📑 PDF出力」でPDF形式でエクスポート
- 保存済み案件は「**📁 保存済み案件**」ページで管理できます
""")

    with st.expander("🏠 物件種別ごとに分析基準が変わる？"):
        st.markdown("""
はい。MAMは**8種別の物件タイプ**に対応し、それぞれ異なる分析基準を適用します：

| 種別 | 目標利回り（地方基準） | 特記 |
|---|---|---|
| 一棟マンション（RC） | 7.5% | エリアで大幅補正あり（港区3.0%等） |
| 一棟アパート（木造） | 8.5% | 老朽化リスク加算 |
| 区分マンション | 6.0% | 管理費・積立金を考慮 |
| 戸建て | 6.5% | 空家リスク評価 |
| 土地 | — | 路線価・開発ポテンシャルで評価 |
| 商業施設 | 6.5% | テナントリスク評価 |
| オフィス | 5.5% | テナント退去リスク |
| 工場・倉庫 | 7.0% | 用途地域・接車条件 |
""")

    # ─── バージョン情報 ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"""
<div style="font-size:0.68rem;color:#475569;text-align:center;padding:8px 0;">
    My Agent Match (MAM) · 動作環境: {_server_os} · Python {_plat.python_version()} ·
    <a href="https://my-agent-much.streamlit.app" style="color:#E8E8EC;text-decoration:none;">
        🌐 クラウド版
    </a>
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
