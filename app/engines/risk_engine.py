import os
import csv as _csv_mod
from datetime import date as _date
from typing import List, Optional
from app.models.property import PropertyData
from app.engines.asset_type_engine import AssetTypeEngine


class RiskEngine:
    def __init__(self):
        self._asset_type_engine = AssetTypeEngine()
        _csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'rent_market.csv')
        self._rent_data: list[dict] = []
        self._rent_data_available = False
        try:
            with open(_csv_path, encoding='utf-8') as _f:
                self._rent_data = list(_csv_mod.DictReader(_f))
                self._rent_data_available = len(self._rent_data) > 0
        except FileNotFoundError:
            import logging
            logging.getLogger(__name__).warning(
                "rent_market.csv が見つかりません。賃料相場リスク判定がスキップされます。"
                " 対処: %s を配置してください。", _csv_path
            )

    def detect_risks(self, property_data: PropertyData) -> List[dict]:
        risks: List[dict] = []

        # 共通リスク（既存ロジック）
        if property_data.broker_chain_count and property_data.broker_chain_count >= 3:
            risks.append({"type": "商流リスク", "level": "high",
                          "message": "商流が長く、売主温度感や価格交渉余地が不透明"})

        if property_data.road_access and "再建築不可" in property_data.road_access:
            risks.append({"type": "接道リスク", "level": "critical",
                          "message": "再建築不可の可能性あり。融資・出口が大きく限定される"})

        if property_data.road_access and "不明" in property_data.road_access:
            risks.append({"type": "接道確認不足", "level": "medium",
                          "message": "接道情報が不明。道路種別・幅員・接道長さの確認が必要"})

        if property_data.occupancy_rate is not None and property_data.occupancy_rate < 0.85:
            risks.append({"type": "稼働率リスク", "level": "medium",
                          "message": "稼働率が低く、賃料設定または物件競争力に懸念"})

        if property_data.built_year and property_data.built_year < 1981:
            risks.append({"type": "旧耐震リスク", "level": "high",
                          "message": "旧耐震の可能性あり。融資・出口・保険・修繕に影響"})

        if property_data.document_freshness_days and property_data.document_freshness_days > 60:
            risks.append({"type": "資料鮮度リスク", "level": "medium",
                          "message": "資料が古く、レントロール・修繕履歴・稼働状況の再確認が必要"})

        if property_data.seller_reason is None:
            risks.append({"type": "売却理由不明", "level": "medium",
                          "message": "売却理由が不明。価格交渉余地・売主温度感を判断できない"})

        if property_data.planned_repairs_cost and property_data.planned_repairs_cost >= 1_000_000:
            risks.append({"type": "修繕リスク", "level": "medium",
                          "message": f"今後修繕費として約{property_data.planned_repairs_cost:,}円の見込みあり"})

        if property_data.legal_notes:
            risks.append({"type": "法的懸念", "level": "high",
                          "message": property_data.legal_notes})

        # 物件種別固有リスク
        asset_risks = self._asset_type_engine.detect_asset_specific_risks(property_data)
        risks.extend(asset_risks)

        # 賃料割高リスク（現況賃料が相場を大きく上回る場合）
        rent_risk = self._check_rent_premium_risk(property_data)
        if rent_risk:
            risks.append(rent_risk)

        if not self._rent_data_available:
            risks.append({
                "type": "賃料相場データ未設定",
                "level": "info",
                "message": "賃料相場CSVが未設定のため賃料割高リスク判定をスキップしています"
            })

        return risks

    def _check_rent_premium_risk(self, property_data) -> Optional[dict]:
        """現況賃料と相場賃料を比較し、割高・割安の場合はリスク／情報を返す"""
        if not self._rent_data:
            return None

        # 必要データチェック
        if not property_data.actual_income:
            return None

        # ① 面積: 賃貸可能面積 > 建物面積 の優先順
        area_sqm = (
            property_data.rentable_area_sqm
            if getattr(property_data, 'rentable_area_sqm', None)
            else property_data.building_area_sqm
        )
        if not area_sqm or area_sqm <= 0:
            return None

        # ② 現況賃料の㎡単価（月額）
        actual_monthly_per_sqm = (property_data.actual_income / 12) / area_sqm

        # ③ エリア相場検索（最長一致優先）
        asset_label = property_data.asset_type.value if property_data.asset_type else ""
        type_map = {
            "一棟マンション": "マンション", "一棟アパート": "マンション",
            "区分マンション": "マンション", "戸建て": "マンション",
            "商業・店舗": "商業", "オフィス": "オフィス",
            "工場・倉庫": "マンション", "土地": None,
        }
        csv_type = type_map.get(asset_label)
        if not csv_type:
            return None

        market_rent = None
        matched_area = ""
        best_match_len = 0
        try:
            for row in self._rent_data:
                if row.get("asset_type") != csv_type:
                    continue
                area = row.get("area", "")
                if not area or not property_data.address:
                    continue
                if area in property_data.address and len(area) > best_match_len:
                    best_match_len = len(area)
                    matched_area = area
                    try:
                        market_rent = float(row["avg_rent_per_sqm"])
                    except (ValueError, KeyError):
                        market_rent = None
        except Exception:
            return None

        if not market_rent or market_rent <= 0:
            return None

        # ④ 築年補正係数（新築プレミアム・築古ディスカウントを反映）
        age_factor = 1.0
        built_year = property_data.built_year
        if built_year:
            age = _date.today().year - built_year
            if age <= 3:
                age_factor = 1.18   # 新築プレミアム
            elif age <= 7:
                age_factor = 1.09   # 築浅
            elif age <= 15:
                age_factor = 1.00   # 標準
            elif age <= 25:
                age_factor = 0.91   # 中古
            elif age <= 35:
                age_factor = 0.81   # 築古
            else:
                age_factor = 0.70   # 旧耐震世代

        adjusted_market_rent = market_rent * age_factor
        ratio = actual_monthly_per_sqm / adjusted_market_rent

        # ⑤ 面積種別ラベル
        area_label = "賃貸可能面積" if getattr(property_data, 'rentable_area_sqm', None) else "延床面積"
        age_note = f"（築年補正係数×{age_factor:.2f}適用）" if age_factor != 1.0 else ""

        # ⑥ 判定
        if ratio > 1.25:
            return {
                "type": "賃料割高リスク",
                "level": "high",
                "message": (
                    f"現況賃料が築年補正後相場の{ratio:.0%}（参照エリア: {matched_area}、"
                    f"相場: {market_rent:,.0f}円/㎡、補正後: {adjusted_market_rent:,.0f}円/㎡{age_note}、"
                    f"現況: {actual_monthly_per_sqm:,.0f}円/㎡・{area_label}基準）。"
                    f"退去後に賃料が{(1 - 1/ratio)*100:.0f}%下落する可能性あり。"
                    f"NOI・利回りが大幅低下するリスクあり。レントロールと市場賃料の乖離を必ず確認。"
                ),
            }
        elif ratio > 1.12:
            return {
                "type": "賃料やや割高",
                "level": "medium",
                "message": (
                    f"現況賃料が築年補正後相場の{ratio:.0%}（参照: {matched_area}、"
                    f"補正後相場: {adjusted_market_rent:,.0f}円/㎡{age_note}）。"
                    f"やや割高。退去後の賃料設定に注意し、新規入居者募集時の条件を確認。"
                ),
            }
        elif ratio < 0.80:
            return {
                "type": "賃料割安（アップサイドあり）",
                "level": "info",
                "message": (
                    f"現況賃料が補正後相場の{ratio:.0%}（参照: {matched_area}、"
                    f"補正後相場: {adjusted_market_rent:,.0f}円/㎡{age_note}）。"
                    f"相場より割安で賃料引上げのアップサイドが期待できる可能性あり。"
                ),
            }
        return None

    def score_risk(self, risks: List[dict]) -> int:
        if not risks:
            return 90
        score = 90
        for risk in risks:
            level = risk.get("level")
            if level == "critical":
                score -= 35
            elif level == "high":
                score -= 20
            elif level == "medium":
                score -= 10
            elif level == "low":
                score -= 5
        return max(score, 0)
