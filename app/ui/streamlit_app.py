import streamlit as st
import sys
import os
import re
import datetime as _dt

# パスを通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd

from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService
from app.services.storage_service import StorageService
from app.engines.finance_engine import FinanceEngine, FinanceResult
from app.engines.exit_strategy_engine import ExitStrategyEngine, ExitStrategyResult
from app.engines.repair_cost_engine import RepairCostEngine, RepairCostResult
from app.engines.developer_land_engine import DeveloperLandEngine, DevLandResult

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


@st.cache_resource
def get_judgement_service():
    """DealJudgementServiceをキャッシュ（毎クリックでCSV再読み込みを防止）"""
    return DealJudgementService()


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


def _init_form_defaults():
    """セッション状態にフォームのデフォルト値を設定（未設定の場合のみ）"""
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
        "form_noi": 0,
        "form_occupancy_rate": 1.0,
        "form_gross_yield": 0.0,
        "form_zoning": "",
        "form_floor_area_ratio": 0.0,
        "form_building_coverage_ratio": 0.0,
        "form_road_access": "",
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
    st.title("📋 案件分析")
    st.caption("物件情報を入力して案件の追うべきか判断します")

    _init_form_defaults()

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
        col1, col2, col3, col4 = st.columns(4)
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
            score_result = _total_score(
                service, price_score, yield_score, liquidity_score, development_score,
                risk_score, broker_score, asset_type=prop.asset_type
            )
            report = service.analyze(prop)

            # 各エンジンを直接呼び出してUIタブ用データを取得
            finance_engine = FinanceEngine()
            exit_engine = ExitStrategyEngine()
            repair_engine = RepairCostEngine()
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
            st.markdown(
                f"""<div style='background:{go_no_go_color}18;border-left:6px solid {go_no_go_color};
                border-radius:8px;padding:16px 20px;margin-bottom:16px;'>
                <div style='font-size:1.5em;font-weight:bold;color:{go_no_go_color}'>{go_no_go_display}</div>
                {f"<div style='margin-top:8px;font-size:1.05em;color:#333'>📍 <b>今日やること:</b> {today_action_display}</div>" if today_action_display else ""}
                </div>""",
                unsafe_allow_html=True
            )

        # ランク表示（タブ外の共通ヘッダー）
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

        # ── タブ表示 ──
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 総合判定", "🏦 融資分析", "🚪 出口戦略", "🔧 修繕費", "📋 全レポート"])

        with tab1:
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
                    f"<div style='text-align:center;padding:10px;border-radius:8px;"
                    f"background:{color}33;border:2px solid {color}'>"
                    f"<div style='font-size:1.6em;font-weight:bold;color:{color}'>{val}</div>"
                    f"<div style='font-size:0.8em;color:#444;margin-top:2px'>{label}</div></div>",
                    unsafe_allow_html=True
                )

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

        with tab5:
            st.subheader("📋 詳細レポート")
            st.markdown(report)

        # ダウンロード・保存
        st.divider()
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
            storage2 = StorageService()
            full_data = storage2.load_deal(deal.get("filename", ""))
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


if __name__ == "__main__":
    main()
