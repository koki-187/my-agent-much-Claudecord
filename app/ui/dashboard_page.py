"""
F4: 今日のダッシュボード

毎朝開いて「今日チェックすべき案件・期限・売主温度感」を即把握できるホームページ。
モバイル / PC 両対応の縦並びカードレイアウト。
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st

from app.services.storage_service import StorageService


# ── CSS （クロームシルバーテーマに合わせる） ──────────────────────────
DASHBOARD_CSS = """
<style>
.dash-hero {
    margin-bottom: 18px;
    padding: 22px 26px;
    background: linear-gradient(135deg, rgba(232,232,236,0.04) 0%, rgba(168,168,176,0.02) 100%);
    border: 1px solid rgba(232,232,236,0.08);
    border-radius: 14px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 16px rgba(0,0,0,0.4);
}
.dash-hero-greeting {
    font-size: 0.78rem;
    color: #686870;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 4px;
}
.dash-hero-title {
    font-size: clamp(1.2rem, 3vw, 1.6rem);
    font-weight: 900;
    background: linear-gradient(135deg, #FFFFFF 0%, #E8E8EC 40%, #A8A8B0 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    margin: 0 0 6px;
    line-height: 1.2;
}
.dash-hero-sub {
    font-size: 0.85rem;
    color: #9A9AA0;
    line-height: 1.6;
}

.dash-stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 18px; }
.dash-stat-card {
    background: linear-gradient(180deg, rgba(232,232,236,0.04), rgba(0,0,0,0.4));
    border: 1px solid rgba(232,232,236,0.08);
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
}
.dash-stat-label { font-size: 0.7rem; color: #686870; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.dash-stat-value {
    font-size: 1.55rem; font-weight: 900;
    background: linear-gradient(135deg, #FFFFFF 0%, #E8E8EC 50%, #A8A8B0 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    line-height: 1.15; margin-top: 4px;
}
.dash-stat-note { font-size: 0.7rem; color: #9A9AA0; margin-top: 4px; }

.dash-section-title {
    font-size: 0.95rem; font-weight: 800; color: #E8E8EC;
    margin: 18px 0 10px; padding-left: 12px; border-left: 3px solid #A8A8B0;
}

.dash-deal-card {
    display: grid; grid-template-columns: 60px 1fr auto;
    gap: 14px; align-items: center;
    padding: 14px 16px;
    background: linear-gradient(180deg, rgba(232,232,236,0.025), rgba(0,0,0,0.35));
    border: 1px solid rgba(232,232,236,0.06);
    border-radius: 10px;
    margin-bottom: 8px;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.dash-deal-card:hover {
    transform: translateY(-1px);
    border-color: rgba(232,232,236,0.18);
}
.dash-deal-rank {
    width: 50px; height: 50px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 10px;
    font-size: 1.4rem; font-weight: 900;
    background: linear-gradient(135deg, #2A2A2D, #1A1A1D);
    border: 1.5px solid currentColor;
}
.dash-deal-rank.r-S { color: #E8E8EC; }
.dash-deal-rank.r-A { color: #A8D8B9; }
.dash-deal-rank.r-B { color: #D4B886; }
.dash-deal-rank.r-C { color: #C9A878; }
.dash-deal-rank.r-D { color: #E89999; }
.dash-deal-meta-name { font-size: 0.95rem; font-weight: 700; color: #FFFFFF; margin-bottom: 2px; }
.dash-deal-meta-sub { font-size: 0.75rem; color: #9A9AA0; }
.dash-deal-meta-tags { font-size: 0.7rem; color: #686870; margin-top: 4px; }
.dash-deal-score { font-size: 1.1rem; font-weight: 800; color: #E8E8EC; text-align: right; }
.dash-deal-saved { font-size: 0.7rem; color: #686870; text-align: right; margin-top: 2px; }

.dash-empty {
    text-align: center;
    padding: 32px 24px;
    color: #9A9AA0;
    font-size: 0.9rem;
    background: rgba(232,232,236,0.02);
    border: 1px dashed rgba(232,232,236,0.1);
    border-radius: 12px;
}

@media (max-width: 768px) {
    .dash-deal-card { grid-template-columns: 48px 1fr auto; gap: 10px; padding: 10px 12px; }
    .dash-deal-rank { width: 40px; height: 40px; font-size: 1.1rem; }
    .dash-deal-meta-name { font-size: 0.85rem; }
    .dash-stat-row { grid-template-columns: repeat(2, 1fr); }
    .dash-stat-value { font-size: 1.25rem; }
}
</style>
"""


def _greeting() -> str:
    h = datetime.now().hour
    if h < 5: return "深夜のお仕事おつかれさまです"
    if h < 11: return "おはようございます"
    if h < 17: return "こんにちは"
    if h < 22: return "こんばんは"
    return "今日もおつかれさまでした"


def _format_price(yen: int) -> str:
    if not yen: return "-"
    if yen >= 100_000_000:
        return f"{yen / 1e8:.2f}億円"
    return f"{yen // 10_000:,}万円"


def _parse_saved_at(s: str) -> Optional[datetime]:
    """saved_at 文字列 (YYYYMMDD_HHMMSS or ISO) を datetime に"""
    if not s: return None
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _saved_at_label(dt: Optional[datetime]) -> str:
    if dt is None: return ""
    delta = datetime.now() - dt
    if delta.days < 1:
        h = int(delta.total_seconds() // 3600)
        return f"{h}時間前" if h > 0 else "たった今"
    if delta.days < 30:
        return f"{delta.days}日前"
    if delta.days < 365:
        return f"{delta.days // 30}ヶ月前"
    return f"{delta.days // 365}年前"


def render_dashboard_page():
    """今日のダッシュボードを描画"""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    storage = StorageService()
    deals = storage.list_deals()

    # ── 統計を計算
    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)
    rank_counts = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    week_count = 0
    high_priority = []   # S/A ランクの最近案件 (top 5)
    pending_check = []   # B ランク（指値検討中）の最近案件

    for d in deals:
        rank = (d.get("rank") or "").upper()
        if rank in rank_counts:
            rank_counts[rank] += 1
        dt = _parse_saved_at(d.get("saved_at", ""))
        if dt and dt >= week_ago:
            week_count += 1
        if rank in ("S", "A") and dt:
            high_priority.append((dt, d))
        if rank == "B" and dt:
            pending_check.append((dt, d))

    high_priority.sort(key=lambda x: x[0], reverse=True)
    pending_check.sort(key=lambda x: x[0], reverse=True)
    high_priority = high_priority[:5]
    pending_check = pending_check[:5]

    # ── ヒーロー
    st.markdown(f"""
    <div class="dash-hero">
        <div class="dash-hero-greeting">DAILY DASHBOARD · {today.strftime('%Y.%m.%d (%a)')}</div>
        <h1 class="dash-hero-title">{_greeting()}、今日の優先案件です</h1>
        <p class="dash-hero-sub">
            これまで <b style="color:#E8E8EC">{len(deals)}件</b> の案件を分析。
            直近7日で <b style="color:#E8E8EC">{week_count}件</b>。
            S+Aランクの優良案件が <b style="color:#A8D8B9">{rank_counts['S']+rank_counts['A']}件</b>、
            指値検討中(B)が <b style="color:#D4B886">{rank_counts['B']}件</b> あります。
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── 統計カード
    stats_html = '<div class="dash-stat-row">'
    for label, val, note, color in [
        ("Sランク", rank_counts["S"], "即対応", "#E8E8EC"),
        ("Aランク", rank_counts["A"], "積極検討", "#A8D8B9"),
        ("Bランク", rank_counts["B"], "指値前提", "#D4B886"),
        ("CDランク", rank_counts["C"] + rank_counts["D"], "様子見", "#9A9AA0"),
        ("今週分析", week_count, "件", "#FFFFFF"),
    ]:
        stats_html += (
            f'<div class="dash-stat-card">'
            f'<div class="dash-stat-label" style="color:{color}">{label}</div>'
            f'<div class="dash-stat-value">{val}</div>'
            f'<div class="dash-stat-note">{note}</div>'
            f'</div>'
        )
    stats_html += '</div>'
    st.markdown(stats_html, unsafe_allow_html=True)

    # ── 最優先案件 (S/A)
    st.markdown('<div class="dash-section-title">⚡ 即対応・積極検討 (S/A ランク 最新5件)</div>',
                unsafe_allow_html=True)
    if not high_priority:
        st.markdown(
            '<div class="dash-empty">'
            'まだ S・A ランクの案件はありません。<br>'
            '案件分析を実行すると、ここに優良案件が並びます。'
            '</div>', unsafe_allow_html=True)
    else:
        for dt, d in high_priority:
            _render_deal_card(d, dt)

    # ── 指値検討中 (B)
    st.markdown('<div class="dash-section-title">💰 指値検討中 (B ランク 最新5件)</div>',
                unsafe_allow_html=True)
    if not pending_check:
        st.markdown('<div class="dash-empty">B ランクの案件はまだありません</div>',
                    unsafe_allow_html=True)
    else:
        for dt, d in pending_check:
            _render_deal_card(d, dt)

    # ── ショートカット
    st.markdown('<div class="dash-section-title">🚀 クイックアクション</div>',
                unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💬 AI チャット入力", use_container_width=True, key="dash_to_chat"):
            st.session_state["_nav_to"] = "💬 AI チャット入力"
            st.rerun()
    with col2:
        if st.button("📋 案件分析", use_container_width=True, key="dash_to_analyze"):
            st.session_state["_nav_to"] = "📋 案件分析"
            st.rerun()
    with col3:
        if st.button("📁 全案件を見る", use_container_width=True, key="dash_to_saved"):
            st.session_state["_nav_to"] = "📁 保存済み案件"
            st.rerun()


def _render_deal_card(deal: dict, saved_dt: Optional[datetime]):
    rank = (deal.get("rank") or "?").upper()
    name = deal.get("property_name") or deal.get("address") or "(無名)"
    address = deal.get("address") or ""
    asset_type = deal.get("asset_type") or ""
    price = int(deal.get("price") or 0)
    score = deal.get("score") or "-"
    saved_label = _saved_at_label(saved_dt)

    # st.markdown では複雑な配置はやりにくいので、HTMLで一気に
    card_html = f"""
    <div class="dash-deal-card">
        <div class="dash-deal-rank r-{rank}">{rank}</div>
        <div>
            <div class="dash-deal-meta-name">{name}</div>
            <div class="dash-deal-meta-sub">{address} ｜ {asset_type}</div>
            <div class="dash-deal-meta-tags">価格: {_format_price(price)}</div>
        </div>
        <div>
            <div class="dash-deal-score">{score}点</div>
            <div class="dash-deal-saved">{saved_label}</div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
