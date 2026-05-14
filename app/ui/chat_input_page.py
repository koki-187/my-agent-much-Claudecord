"""
chat_input_page.py
──────────────────
AI会話型物件入力ページ。
`render_chat_input_page()` を streamlit_app.py から呼び出す。

デザイン: クロームシルバー × モノクロームラグジュアリー
         LINE風メッセージバブル（ユーザー右・AI左）
"""

import streamlit as st

from app.services.chat_input_service import ChatInputService, CRITICAL_FIELDS, RECOMMENDED_FIELDS

# ────────────────────────────────────────────────────────────────────────────
# CSS（既存テーマに準拠: Black × Chrome Silver × Off-White）
# ────────────────────────────────────────────────────────────────────────────

_CHAT_CSS = """
<style>
/* ── Chat Page Layout ── */
.chat-page-header {
    display: flex; align-items: center; gap: 14px;
    padding: 18px 0 14px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 20px;
    position: relative;
}
.chat-page-header::after {
    content: ''; position: absolute; bottom: -1px; left: 0; width: 64px; height: 1px;
    background: linear-gradient(90deg, #A8A8B0, transparent);
}
.chat-page-title {
    font-size: 1.25rem; font-weight: 900; color: #FFFFFF;
    letter-spacing: -0.02em; margin: 0;
    font-family: 'Noto Sans JP', 'Inter', sans-serif;
}
.chat-page-sub {
    font-size: 0.72rem; color: #606068; font-weight: 600;
    letter-spacing: 0.12em; text-transform: uppercase;
    margin: 2px 0 0;
}

/* ── AI Status Bar ── */
.ai-status-bar {
    background: rgba(26,26,29,0.9);
    border: 1px solid rgba(168,168,176,0.15);
    border-radius: 8px; padding: 8px 14px;
    font-size: 0.75rem; color: #A8A8B0;
    font-weight: 500; letter-spacing: 0.02em;
    margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
}
.ai-status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #A8D8B9; flex-shrink: 0;
    animation: pulse-dot 2s ease infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ── Progress Bar ── */
.progress-wrap {
    margin-bottom: 18px;
}
.progress-label {
    display: flex; justify-content: space-between;
    font-size: 0.7rem; color: #686870; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 6px;
}
.progress-label span:last-child { color: #C0C0C8; }
.progress-track {
    height: 4px; background: rgba(255,255,255,0.06);
    border-radius: 4px; overflow: hidden;
}
.progress-fill {
    height: 100%; border-radius: 4px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    background: linear-gradient(90deg, #A8A8B0 0%, #E8E8EC 50%, #A8A8B0 100%);
    background-size: 200% 100%;
    animation: chrome-shimmer-prog 2s linear infinite;
}
@keyframes chrome-shimmer-prog {
    0%   { background-position: 200% center; }
    100% { background-position: -200% center; }
}

/* ── Chat Viewport ── */
.chat-viewport {
    display: flex; flex-direction: column; gap: 12px;
    padding: 4px 2px 20px;
    min-height: 200px;
}

/* ── Message Bubbles ── */
.chat-msg-row {
    display: flex; align-items: flex-end; gap: 10px;
    animation: float-in-msg 0.3s ease both;
}
.chat-msg-row.user { flex-direction: row-reverse; }
.chat-msg-row.ai   { flex-direction: row; }

@keyframes float-in-msg {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}

.chat-avatar {
    width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; line-height: 1;
}
.chat-avatar.ai {
    background: linear-gradient(145deg, #2A2A2D, #1A1A1D);
    border: 1px solid rgba(192,192,200,0.2);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);
}
.chat-avatar.user {
    background: linear-gradient(145deg, #3A3A3F, #252528);
    border: 1px solid rgba(192,192,200,0.15);
}

.chat-bubble {
    max-width: 72%; padding: 12px 16px;
    border-radius: 18px; font-size: 0.88rem;
    line-height: 1.65; position: relative;
    word-break: break-word;
}

/* AI bubble: left / gunmetal chrome */
.chat-bubble.ai {
    background: linear-gradient(145deg, #1E1E21 0%, #161618 100%);
    border: 1px solid rgba(192,192,200,0.14);
    border-bottom-left-radius: 4px;
    color: #E8E8EC;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.07),
                0 4px 16px rgba(0,0,0,0.5);
}

/* User bubble: right / polished chrome */
.chat-bubble.user {
    background: linear-gradient(145deg, #2E2E32 0%, #232326 100%);
    border: 1px solid rgba(232,232,236,0.18);
    border-bottom-right-radius: 4px;
    color: #F4F4F6;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.1),
                0 4px 16px rgba(0,0,0,0.5);
}

.chat-bubble-time {
    font-size: 0.62rem; color: #505058; margin-top: 4px;
    font-weight: 500;
}
.chat-msg-row.ai   .chat-bubble-time { text-align: left; }
.chat-msg-row.user .chat-bubble-time { text-align: right; }

/* ── Field Checklist Card ── */
.field-checklist-card {
    background: linear-gradient(180deg, #141416 0%, #101012 100%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 18px 16px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05),
                0 4px 20px rgba(0,0,0,0.6);
}
.field-checklist-title {
    font-size: 0.68rem; font-weight: 700;
    color: #686870; text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.field-item {
    display: flex; align-items: center; gap: 8px;
    padding: 5px 0; font-size: 0.78rem;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.field-item:last-child { border-bottom: none; }
.field-check {
    width: 16px; height: 16px; border-radius: 50%;
    flex-shrink: 0; display: flex; align-items: center; justify-content: center;
    font-size: 0.6rem; font-weight: 900;
}
.field-check.done {
    background: linear-gradient(145deg, #A8D8B9, #78C8A0);
    color: #0A1A12;
}
.field-check.pending {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    color: transparent;
}
.field-label.done { color: #A8A8B0; }
.field-label.pending { color: #505058; }
.field-value {
    margin-left: auto; font-size: 0.72rem; color: #E8E8EC;
    font-weight: 600; max-width: 90px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Completion Banner ── */
.completion-banner {
    background: linear-gradient(135deg, rgba(168,216,185,0.08) 0%, rgba(192,192,200,0.04) 100%);
    border: 1px solid rgba(168,216,185,0.3);
    border-radius: 14px; padding: 24px 28px;
    text-align: center; margin: 16px 0;
    box-shadow: inset 0 1px 0 rgba(168,216,185,0.12),
                0 8px 32px rgba(0,0,0,0.6);
    animation: float-in-msg 0.5s ease both;
}
.completion-icon { font-size: 2.4rem; margin-bottom: 10px; line-height: 1; }
.completion-title {
    font-size: 1.1rem; font-weight: 900; color: #A8D8B9;
    letter-spacing: -0.01em; margin-bottom: 6px;
    font-family: 'Noto Sans JP', 'Inter', sans-serif;
}
.completion-sub {
    font-size: 0.82rem; color: #686870; margin-bottom: 0;
}

/* ── Empty State ── */
.chat-empty-state {
    display: flex; flex-direction: column; align-items: center;
    padding: 40px 20px; text-align: center;
    color: #505058;
}
.chat-empty-icon { font-size: 2.8rem; margin-bottom: 14px; line-height: 1; }
.chat-empty-title { font-size: 0.95rem; font-weight: 700; color: #686870; margin-bottom: 6px; }
.chat-empty-sub { font-size: 0.78rem; line-height: 1.7; }

/* ── Rate limit warning ── */
.rate-limit-warn {
    background: rgba(232,153,153,0.06);
    border: 1px solid rgba(232,153,153,0.25);
    border-radius: 10px; padding: 12px 16px;
    font-size: 0.8rem; color: #E89999;
    margin: 8px 0;
}
</style>
"""


# ────────────────────────────────────────────────────────────────────────────
# Field display helpers
# ────────────────────────────────────────────────────────────────────────────

def _format_field_value(field_key: str, partial_data: dict) -> str:
    """フィールド値を表示用にフォーマット"""
    val = partial_data.get(field_key)
    if val is None:
        return ""
    if field_key == "price":
        # PropertyData.price は「円」単位。1億円 = 100,000,000
        try:
            v = int(val)
            oku = v // 100_000_000           # 億の桁
            man = (v % 100_000_000) // 10_000  # 万の桁
            if oku >= 1:
                return f"{oku}億{man:,}万円" if man > 0 else f"{oku}億円"
            if man >= 1:
                return f"{man:,}万円"
            return f"{v:,}円"
        except Exception:
            return str(val)
    if field_key in ("noi", "gross_income", "actual_income", "planned_repairs_cost"):
        try:
            v = int(val)
            return f"{v:,}円"
        except Exception:
            return str(val)
    if field_key in ("gross_yield", "net_yield", "occupancy_rate"):
        try:
            return f"{float(val) * 100:.1f}%"
        except Exception:
            return str(val)
    if field_key == "built_year":
        return f"{val}年"
    if field_key in ("land_area_sqm", "building_area_sqm"):
        try:
            return f"{float(val):.1f}㎡"
        except Exception:
            return str(val)
    return str(val)[:12]


def _is_field_filled(field_key: str, partial_data: dict) -> bool:
    """フィールドが有効な値で埋まっているか"""
    val = partial_data.get(field_key)
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    if isinstance(val, (int, float)) and val == 0:
        return False
    return True


def _noi_or_yield_filled(partial_data: dict) -> bool:
    """NOI または 表面利回り のどちらかが埋まっているか"""
    return _is_field_filled("noi", partial_data) or _is_field_filled("gross_yield", partial_data)


# ────────────────────────────────────────────────────────────────────────────
# Progress calculation
# ────────────────────────────────────────────────────────────────────────────

def _calc_progress(partial_data: dict) -> tuple[int, int, float]:
    """(filled_count, total_count, ratio)"""
    filled = 0
    total = len(CRITICAL_FIELDS)
    for label, field_key in CRITICAL_FIELDS.items():
        if label == "NOI（実質収益）":
            if _noi_or_yield_filled(partial_data):
                filled += 1
        elif _is_field_filled(field_key, partial_data):
            filled += 1
    return filled, total, filled / total if total > 0 else 0.0


# ────────────────────────────────────────────────────────────────────────────
# Session state management
# ────────────────────────────────────────────────────────────────────────────

def _init_session():
    if "chat_input_history" not in st.session_state:
        st.session_state["chat_input_history"] = []
    if "chat_input_partial" not in st.session_state:
        st.session_state["chat_input_partial"] = {}
    if "chat_input_complete" not in st.session_state:
        st.session_state["chat_input_complete"] = False
    if "chat_input_status" not in st.session_state:
        st.session_state["chat_input_status"] = "物件情報を貼り付けてください。PDFの内容・メール文面・URL何でもOKです。"
    if "chat_input_confidence" not in st.session_state:
        st.session_state["chat_input_confidence"] = 0.0
    if "_chat_svc" not in st.session_state:
        st.session_state["_chat_svc"] = None


def _get_service() -> ChatInputService:
    if st.session_state.get("_chat_svc") is None:
        try:
            from app.ui.streamlit_app import get_llm_service
            llm = get_llm_service()
        except Exception:
            from app.services.llm_service import LLMService
            llm = LLMService()
        st.session_state["_chat_svc"] = ChatInputService(llm_service=llm)
    return st.session_state["_chat_svc"]


# ────────────────────────────────────────────────────────────────────────────
# HTML rendering helpers
# ────────────────────────────────────────────────────────────────────────────

def _render_progress(partial_data: dict):
    filled, total, ratio = _calc_progress(partial_data)
    pct = int(ratio * 100)
    st.markdown(
        f"""<div class="progress-wrap">
  <div class="progress-label">
    <span>必須項目充足率</span>
    <span>{filled} / {total}項目 ({pct}%)</span>
  </div>
  <div class="progress-track">
    <div class="progress-fill" style="width:{pct}%;"></div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_status_bar(status_text: str):
    st.markdown(
        f"""<div class="ai-status-bar">
  <span class="ai-status-dot"></span>
  <span>{status_text}</span>
</div>""",
        unsafe_allow_html=True,
    )


def _render_bubble(role: str, content: str):
    if role == "user":
        avatar = "👤"
        cls = "user"
    else:
        avatar = "🤖"
        cls = "ai"

    # Escape HTML in content but preserve newlines as <br>
    import html
    safe_content = html.escape(content).replace("\n", "<br>")

    st.markdown(
        f"""<div class="chat-msg-row {cls}">
  <div class="chat-avatar {cls}">{avatar}</div>
  <div>
    <div class="chat-bubble {cls}">{safe_content}</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_field_checklist(partial_data: dict):
    rows_html = ""
    for label, field_key in CRITICAL_FIELDS.items():
        # NOI/利回り特殊処理
        if label == "NOI（実質収益）":
            filled = _noi_or_yield_filled(partial_data)
            display_key = "noi" if _is_field_filled("noi", partial_data) else "gross_yield"
        else:
            filled = _is_field_filled(field_key, partial_data)
            display_key = field_key

        check_cls = "done" if filled else "pending"
        check_icon = "✓" if filled else ""
        val_html = ""
        if filled:
            val_str = _format_field_value(display_key, partial_data)
            val_html = f'<span class="field-value">{val_str}</span>'

        rows_html += (
            f'<div class="field-item">'
            f'<div class="field-check {check_cls}">{check_icon}</div>'
            f'<span class="field-label {check_cls}">{label}</span>'
            f'{val_html}'
            f'</div>'
        )

    # Recommended fields (dimmer section)
    rows_html += '<div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);">'
    rows_html += '<div style="font-size:0.62rem;color:#404048;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;font-weight:700;">推奨項目</div>'
    for label, field_key in RECOMMENDED_FIELDS.items():
        filled = _is_field_filled(field_key, partial_data)
        check_cls = "done" if filled else "pending"
        check_icon = "✓" if filled else ""
        val_html = ""
        if filled:
            val_str = _format_field_value(field_key, partial_data)
            val_html = f'<span class="field-value">{val_str}</span>'
        rows_html += (
            f'<div class="field-item">'
            f'<div class="field-check {check_cls}" style="width:14px;height:14px;">{check_icon}</div>'
            f'<span class="field-label {check_cls}" style="font-size:0.72rem;">{label}</span>'
            f'{val_html}'
            f'</div>'
        )
    rows_html += '</div>'

    st.markdown(
        f"""<div class="field-checklist-card">
  <div class="field-checklist-title">抽出済みフィールド</div>
  {rows_html}
</div>""",
        unsafe_allow_html=True,
    )


def _render_completion_banner():
    st.markdown(
        """<div class="completion-banner">
  <div class="completion-icon">✅</div>
  <div class="completion-title">全項目確認完了</div>
  <div class="completion-sub">必須情報が揃いました。このまま分析を実行できます。</div>
</div>""",
        unsafe_allow_html=True,
    )


def _apply_partial_to_session_state(partial_data: dict):
    """partial_data を st.session_state['form_xxx'] 各フィールドにセット"""
    field_map = {
        "property_name": "form_property_name",
        "asset_type": "form_asset_type",
        "address": "form_address",
        "price": "form_price",
        "land_area_sqm": "form_land_area",
        "building_area_sqm": "form_building_area",
        "structure": "form_structure",
        "built_year": "form_built_year",
        "gross_income": "form_gross_income",
        "actual_income": "form_actual_income",
        "noi": "form_noi",
        "occupancy_rate": "form_occupancy_rate",
        "gross_yield": "form_gross_yield",
        "net_yield": "form_net_yield",
        "zoning": "form_zoning",
        "road_access": "form_road_access",
        "walk_minutes_to_station": "form_walk_minutes",
        "current_status": "form_current_status",
        "seller_reason": "form_seller_reason",
        "seller_motivation": "form_seller_motivation",
        "broker_chain_count": "form_broker_chain_count",
        "planned_repairs_cost": "form_planned_repairs_cost",
        "legal_notes": "form_legal_notes",
        "notes": "form_notes",
    }
    for src_key, dest_key in field_map.items():
        if src_key in partial_data and partial_data[src_key] is not None:
            st.session_state[dest_key] = partial_data[src_key]


# ────────────────────────────────────────────────────────────────────────────
# Main render function
# ────────────────────────────────────────────────────────────────────────────

def render_chat_input_page():
    """
    AIチャット入力ページを描画する。
    streamlit_app.py のページルーターから呼び出す。
    """
    _init_session()

    # CSS injection
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    # ── Header ──
    st.markdown(
        """<div class="chat-page-header">
  <div>
    <div class="chat-page-title">💬 AI 物件入力</div>
    <div class="chat-page-sub">会話3往復で30項目を自動入力</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

    partial_data: dict = st.session_state["chat_input_partial"]
    history: list = st.session_state["chat_input_history"]
    is_complete: bool = st.session_state["chat_input_complete"]

    # ── 2-column layout: chat left, checklist right ──
    col_chat, col_side = st.columns([3, 1], gap="large")

    with col_side:
        _render_field_checklist(partial_data)

        # Reset button
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 会話をリセット", use_container_width=True, key="chat_reset_btn"):
            for key in ("chat_input_history", "chat_input_partial",
                        "chat_input_complete", "chat_input_status",
                        "chat_input_confidence", "_chat_svc"):
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    with col_chat:
        # Status bar
        _render_status_bar(st.session_state["chat_input_status"])

        # Progress bar
        _render_progress(partial_data)

        # ── Chat messages ──
        if not history:
            st.markdown(
                """<div class="chat-empty-state">
  <div class="chat-empty-icon">📋</div>
  <div class="chat-empty-title">物件情報を貼り付けてください</div>
  <div class="chat-empty-sub">
    PDF内容・メール文面・URLなど<br>何でもそのまま貼り付けOK。<br>
    AIが自動で読み取り、<br>不足情報だけ質問します。
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="chat-viewport">', unsafe_allow_html=True)
            for msg in history:
                _render_bubble(msg["role"], msg["content"])
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Completion banner + navigation button ──
        if is_complete:
            _render_completion_banner()
            if st.button(
                "📊 分析実行へ進む",
                use_container_width=True,
                type="primary",
                key="chat_goto_analysis",
            ):
                _apply_partial_to_session_state(partial_data)
                st.session_state["_nav_to"] = "📋 案件分析"
                st.rerun()

        # ── Chat input ──
        if not is_complete:
            placeholder_text = (
                "物件情報を貼り付け、または質問に答えてください..."
                if history
                else "PDFの内容、メール本文、URLなど何でも貼り付けてください..."
            )
            user_input = st.chat_input(placeholder_text, key="chat_main_input")

            if user_input:
                _handle_user_message(user_input, history, partial_data)
        else:
            # 完了後も追加コメント可能
            extra = st.chat_input("追加情報や修正があれば入力できます...", key="chat_extra_input")
            if extra:
                _handle_user_message(extra, history, partial_data)


# ────────────────────────────────────────────────────────────────────────────
# Message handler
# ────────────────────────────────────────────────────────────────────────────

def _handle_user_message(user_input: str, history: list, partial_data: dict):
    """ユーザー発話を処理してセッションを更新し rerun する"""
    # ユーザーメッセージを履歴に追加
    history.append({"role": "user", "content": user_input})
    st.session_state["chat_input_history"] = history

    svc = _get_service()

    with st.spinner("AIが解析中..."):
        try:
            result = svc.next_turn(
                user_message=user_input,
                chat_history=history[:-1],  # 最新の発話はnext_turnに渡す
                partial_data=partial_data,
            )
        except RuntimeError as e:
            if "RATE_LIMIT_429" in str(e):
                history.append({
                    "role": "assistant",
                    "content": "申し訳ありません、現在APIのレート制限に達しています。少しお待ちいただいてから再度お試しください。(429 Rate Limit)",
                })
                st.session_state["chat_input_history"] = history
                st.rerun()
                return
            raise
        except Exception as e:
            history.append({
                "role": "assistant",
                "content": f"エラーが発生しました: {str(e)[:100]}。もう一度お試しください。",
            })
            st.session_state["chat_input_history"] = history
            st.rerun()
            return

    # AI返答を履歴に追加
    history.append({"role": "assistant", "content": result["assistant_message"]})

    # partial_data を更新（新規抽出フィールドをマージ）
    extracted = result.get("extracted_fields", {})
    partial_data.update(extracted)

    # セッションを更新
    st.session_state["chat_input_history"] = history
    st.session_state["chat_input_partial"] = partial_data
    st.session_state["chat_input_complete"] = result.get("is_complete", False)
    st.session_state["chat_input_status"] = result.get("ai_status_line", "")
    st.session_state["chat_input_confidence"] = result.get("completion_confidence", 0.0)

    st.rerun()
