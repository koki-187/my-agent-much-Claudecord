import streamlit as st
import sys
import os

# パスを通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService
from app.services.storage_service import StorageService

st.set_page_config(
    page_title="案件調査君",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.rank-s { color: #FF4B4B; font-size: 2em; font-weight: bold; }
.rank-a { color: #FF8C00; font-size: 2em; font-weight: bold; }
.rank-b { color: #1E90FF; font-size: 2em; font-weight: bold; }
.rank-c { color: #808080; font-size: 2em; font-weight: bold; }
.rank-d { color: #A9A9A9; font-size: 2em; font-weight: bold; }
.risk-critical { background-color: #FFE4E4; border-left: 4px solid #FF0000; padding: 8px; margin: 4px 0; }
.risk-high { background-color: #FFF3E0; border-left: 4px solid #FF8C00; padding: 8px; margin: 4px 0; }
.risk-medium { background-color: #FFFDE7; border-left: 4px solid #FFC107; padding: 8px; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)


def get_rank_color(rank: str) -> str:
    colors = {"S": "#FF4B4B", "A": "#FF8C00", "B": "#1E90FF", "C": "#808080", "D": "#696969"}
    return colors.get(rank, "#000000")


def render_risk_badge(level: str) -> str:
    badges = {
        "critical": "🔴 致命的",
        "high": "🟠 高",
        "medium": "🟡 中",
        "low": "🟢 低"
    }
    return badges.get(level, level)


def _get_target_yield(service: DealJudgementService, prop: PropertyData) -> float:
    """_get_target_yield があれば使い、なければ service.target_yield にフォールバック"""
    if hasattr(service, "_get_target_yield"):
        return service._get_target_yield(prop)
    return service.target_yield


def _total_score(service: DealJudgementService, price_score, yield_score, liquidity_score,
                 development_score, risk_score, broker_score, asset_type) -> dict:
    """asset_type 引数付き total_score を試みて、なければ従来版にフォールバック"""
    try:
        return service.scoring_engine.total_score(
            price_score, yield_score, liquidity_score, development_score,
            risk_score, broker_score, asset_type=asset_type
        )
    except TypeError:
        return service.scoring_engine.total_score(
            price_score, yield_score, liquidity_score, development_score,
            risk_score, broker_score
        )


def main():
    # サイドバー
    with st.sidebar:
        st.title("🏢 案件調査君")
        st.caption("不動産仲介営業 案件判断支援システム")
        st.divider()

        page = st.radio(
            "メニュー",
            ["📋 案件分析", "📊 比較分析", "📁 保存済み案件"],
            label_visibility="collapsed"
        )

        st.divider()
        st.info("**使い方**\n\n1. 物件情報を入力\n2. 「分析実行」をクリック\n3. レポートを確認")

    if page == "📋 案件分析":
        render_analysis_page()
    elif page == "📊 比較分析":
        render_comparison_page()
    else:
        render_history_page()


def render_analysis_page():
    st.title("📋 案件分析")
    st.caption("物件情報を入力して案件の追うべきか判断します")

    # テキストから自動抽出
    with st.expander("📝 テキストから物件情報を自動抽出（AI）", expanded=False):
        from app.services.llm_service import LLMService
        llm = LLMService()
        if not llm.is_available():
            st.warning("ANTHROPIC_API_KEY が設定されていないためAI抽出は使用できません。")
        else:
            paste_text = st.text_area(
                "物件情報テキストを貼り付けてください",
                height=200,
                placeholder="物件名、所在地、価格、利回りなどを含む物件概要を貼り付けてください..."
            )
            if st.button("🤖 AI で情報を抽出"):
                if paste_text:
                    with st.spinner("AIが物件情報を解析中..."):
                        extracted = llm.extract_property_from_text(paste_text)
                    if extracted:
                        st.session_state["extracted_property"] = extracted
                        st.success("抽出成功！下のフォームに入力されました。ご確認ください。")
                        st.json(extracted.model_dump(exclude_none=True))
                    else:
                        st.error("抽出に失敗しました。テキストを確認してください。")

    with st.form("analysis_form"):
        # ── 基本情報 ──
        st.subheader("基本情報")
        col1, col2 = st.columns(2)
        with col1:
            property_name = st.text_input("物件名", placeholder="例）サンプル収益マンション")
            asset_type = st.selectbox(
                "物件種別 *",
                options=[e.value for e in AssetType],
                index=0
            )
        with col2:
            address = st.text_input("所在地 *", placeholder="例）東京都新宿区")
            price = st.number_input("売出価格（円）*", min_value=0, value=100_000_000, step=1_000_000,
                                    format="%d")

        # ── 建物・土地情報 ──
        st.subheader("建物・土地情報")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            land_area = st.number_input("土地面積（㎡）", min_value=0.0, value=0.0, step=1.0)
        with col2:
            building_area = st.number_input("建物面積（㎡）", min_value=0.0, value=0.0, step=1.0)
        with col3:
            structure = st.selectbox("構造", ["", "RC造", "SRC造", "鉄骨造", "木造", "軽量鉄骨造"])
        with col4:
            built_year = st.number_input("築年（西暦）", min_value=1900, max_value=2024, value=2000)

        # ── 収益情報 ──
        st.subheader("収益情報")
        col1, col2, col3 = st.columns(3)
        with col1:
            gross_income = st.number_input("満室想定年収（円）", min_value=0, value=0, step=100_000, format="%d")
            actual_income = st.number_input("現況年収（円）", min_value=0, value=0, step=100_000, format="%d")
        with col2:
            noi = st.number_input("NOI（円）", min_value=0, value=0, step=100_000, format="%d")
            occupancy_rate = st.slider("稼働率", min_value=0.0, max_value=1.0, value=1.0, step=0.01,
                                       format="%.0f%%")
        with col3:
            gross_yield_input = st.number_input("表面利回り（%）", min_value=0.0, value=0.0, step=0.1)

        # ── 法令・接道情報 ──
        st.subheader("法令・接道情報")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            zoning = st.text_input("用途地域", placeholder="例）近隣商業地域")
        with col2:
            floor_area_ratio = st.number_input("容積率（%）", min_value=0.0, value=0.0, step=10.0)
        with col3:
            building_coverage_ratio = st.number_input("建蔽率（%）", min_value=0.0, value=0.0, step=5.0)
        with col4:
            road_access = st.text_input("接道情報", placeholder="例）公道 6m接道")

        # ── 商流・売主情報 ──
        st.subheader("商流・売主情報")
        col1, col2, col3 = st.columns(3)
        with col1:
            seller_reason = st.text_input("売却理由", placeholder="例）相続、転居、事業縮小")
            seller_motivation = st.selectbox("売主温度感", ["", "高い（早期売却希望）", "中程度", "低い（様子見）"])
        with col2:
            broker_chain_count = st.number_input("商流の段数", min_value=1, max_value=10, value=1)
            document_freshness_days = st.number_input("資料更新からの日数", min_value=0, value=0)
        with col3:
            planned_repairs_cost = st.number_input("想定修繕費（円）", min_value=0, value=0, step=100_000, format="%d")
            legal_notes = st.text_area("法的懸念事項", height=80)

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
                lease_expiry = st.text_input("契約満了日", placeholder="YYYY-MM-DD")
            with col3:
                lease_type = st.selectbox("賃貸借種類", ["", "普通借家", "定期借家"])
        else:
            tenant_name, lease_expiry, lease_type = "", "", ""

        if selected_asset_type == AssetType.FACTORY:
            st.subheader("工場・倉庫固有情報")
            truck_access = st.selectbox("トラック接車", ["", "大型トラック可", "中型まで可", "不可"])
        else:
            truck_access = ""

        notes = st.text_area("その他メモ", height=80)

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
            noi=int(noi) if noi > 0 else None,
            occupancy_rate=occupancy_rate if occupancy_rate < 1.0 else None,
            gross_yield=gross_yield_input / 100 if gross_yield_input > 0 else None,
            zoning=zoning or None,
            floor_area_ratio=floor_area_ratio / 100 if floor_area_ratio > 0 else None,
            building_coverage_ratio=building_coverage_ratio / 100 if building_coverage_ratio > 0 else None,
            road_access=road_access or None,
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
            service = DealJudgementService()
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
            score_result = _total_score(
                service, price_score, yield_score, liquidity_score, development_score,
                risk_score, broker_score, asset_type=prop.asset_type
            )
            report = service.analyze(prop)

        # ── 結果表示 ──
        st.divider()
        st.subheader("📊 分析結果")

        # ランク表示
        rank = score_result["rank"]
        rank_color = get_rank_color(rank)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                f"<div style='text-align:center'>"
                f"<span style='font-size:3em;font-weight:bold;color:{rank_color}'>{rank}</span>"
                f"<br><small>総合ランク</small></div>",
                unsafe_allow_html=True
            )
        with col2:
            st.metric("総合スコア", f"{score_result['total_score']}点")
        with col3:
            st.metric("判断", score_result["judgement"])
        with col4:
            st.metric("価格判定", price_result["status"])

        # スコア内訳
        st.subheader("スコア内訳")
        scores = {
            "価格妥当性": price_score,
            "収益性": yield_score,
            "流動性": liquidity_score,
            "開発可能性": development_score,
            "リスク耐性": risk_score,
            "商流・売主": broker_score,
        }
        cols = st.columns(len(scores))
        for col, (label, val) in zip(cols, scores.items()):
            color = "#2ECC71" if val >= 70 else "#F39C12" if val >= 50 else "#E74C3C"
            col.markdown(
                f"<div style='text-align:center;padding:8px;border-radius:8px;"
                f"background:{color}22;border:1px solid {color}'>"
                f"<b style='color:{color}'>{val}</b><br><small>{label}</small></div>",
                unsafe_allow_html=True
            )

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

        # Markdownレポート
        with st.expander("📄 詳細レポートを表示", expanded=False):
            st.markdown(report)

        # ダウンロード
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📥 Markdownレポートをダウンロード",
                data=report.encode("utf-8"),
                file_name=f"anken_report_{property_name or 'unnamed'}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col2:
            if st.button("📄 PDFレポートを生成", use_container_width=True):
                from app.services.pdf_service import PDFService
                pdf_service = PDFService()
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = pdf_service.generate(report, tmp.name, property_name or "案件")
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                ext = "pdf" if pdf_path.endswith(".pdf") else "html"
                st.download_button(
                    f"📥 {ext.upper()}をダウンロード",
                    data=pdf_bytes,
                    file_name=f"anken_report_{property_name or 'unnamed'}.{ext}",
                    mime=f"application/{'pdf' if ext == 'pdf' else 'html'}",
                    use_container_width=True
                )
        with col3:
            if st.button("💾 履歴に保存", use_container_width=True):
                storage = StorageService()
                path = storage.save_deal(prop, report, score_result["total_score"], rank)
                st.success(f"保存しました: {os.path.basename(path)}")

        # AIアドバイス（API Key設定時のみ）
        from app.services.llm_service import LLMService
        llm_svc = LLMService()
        if llm_svc.is_available():
            with st.expander("🤖 AIアドバイスを取得", expanded=False):
                if st.button("AIにアドバイスを求める"):
                    with st.spinner("AIが分析中..."):
                        advice = llm_svc.generate_advice(report)
                    if advice:
                        st.markdown(advice)
                    else:
                        st.error("アドバイスの取得に失敗しました。")


def render_comparison_page():
    st.title("📊 比較分析")
    st.caption("複数の案件を並べて比較します")

    from app.services.comparison_service import ComparisonService

    SAMPLES = {
        "一棟マンション（東京）": PropertyData(
            property_name="サンプル収益マンション", asset_type=AssetType.APARTMENT_WHOLE,
            address="東京都新宿区", price=120_000_000,
            noi=7_200_000, occupancy_rate=0.92, built_year=1995,
            broker_chain_count=3, document_freshness_days=75, planned_repairs_cost=2_000_000,
            zoning="近隣商業地域", road_access="公道", floor_area_ratio=3.0,
        ),
        "木造アパート（大阪）": PropertyData(
            property_name="木造アパート", asset_type=AssetType.APARTMENT_WOOD,
            address="大阪府大阪市", price=50_000_000,
            noi=3_800_000, occupancy_rate=1.0, built_year=2005,
            seller_reason="相続", seller_motivation="高い", broker_chain_count=1,
            zoning="第一種住居地域", road_access="公道 4m",
        ),
        "区分マンション（渋谷）": PropertyData(
            property_name="区分マンション", asset_type=AssetType.UNIT,
            address="東京都渋谷区", price=25_000_000,
            noi=1_080_000, occupancy_rate=1.0, built_year=2010,
            seller_reason="転勤", seller_motivation="高い", broker_chain_count=1,
            management_fee_monthly=18000, repair_reserve_monthly=8000,
            zoning="第一種住居地域", road_access="公道",
        ),
        "更地（横浜）": PropertyData(
            property_name="更地", asset_type=AssetType.LAND,
            address="神奈川県横浜市", price=80_000_000,
            land_area_sqm=200.0, zoning="第一種住居地域",
            building_coverage_ratio=0.6, floor_area_ratio=2.0, road_access="公道 6m",
            seller_reason="相続", seller_motivation="高い", broker_chain_count=1,
        ),
    }

    selected = st.multiselect(
        "比較する案件を選択（2件以上）",
        options=list(SAMPLES.keys()),
        default=list(SAMPLES.keys())[:3]
    )

    if len(selected) < 2:
        st.warning("2件以上選択してください。")
        return

    if st.button("🔍 比較実行", type="primary"):
        props = [SAMPLES[k] for k in selected]
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


if __name__ == "__main__":
    main()
