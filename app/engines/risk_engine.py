import os
from typing import List, Optional
from app.models.property import PropertyData
from app.engines.asset_type_engine import AssetTypeEngine


class RiskEngine:
    def __init__(self):
        self._asset_type_engine = AssetTypeEngine()
        import csv as _csv_mod
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
        """現況賃料と相場賃料を比較し、割高の場合はリスクを返す"""
        if not self._rent_data:
            return None

        # 必要なデータが揃っていない場合はスキップ
        if not property_data.actual_income or not property_data.building_area_sqm:
            return None
        if property_data.building_area_sqm <= 0:
            return None

        # 現況賃料の㎡単価（月額）
        actual_monthly_per_sqm = (property_data.actual_income / 12) / property_data.building_area_sqm

        # rent_market.csv から相場を検索
        try:
            market_rent = None
            asset_label = property_data.asset_type.value if property_data.asset_type else ""
            # 物件種別のマッピング
            type_map = {"一棟マンション": "マンション", "一棟アパート": "マンション",
                        "区分マンション": "マンション", "戸建て": "マンション",
                        "商業・店舗": "商業", "オフィス": "オフィス",
                        "工場・倉庫": "マンション", "土地": None}
            csv_type = type_map.get(asset_label)
            if not csv_type:
                return None  # 土地はスキップ

            best_score = 0
            for row in self._rent_data:
                if row.get("asset_type") != csv_type:
                    continue
                score = 0
                area = row.get("area", "")
                if area and area in property_data.address:
                    score += 50
                elif area and property_data.address and area in property_data.address[:20]:
                    score += 20
                if score > best_score:
                    best_score = score
                    try:
                        market_rent = float(row["avg_rent_per_sqm"])
                    except (ValueError, KeyError):
                        market_rent = None

            if market_rent and market_rent > 0:
                ratio = actual_monthly_per_sqm / market_rent
                if ratio > 1.20:
                    return {
                        "type": "賃料割高リスク",
                        "level": "high",
                        "message": f"現況賃料が相場の約{ratio:.0%}（相場:{market_rent:,.0f}円/㎡、現況:{actual_monthly_per_sqm:,.0f}円/㎡）。"
                                   f"退去後に賃料が約{(1-1/ratio)*100:.0f}%下落する可能性があり、NOI・利回りが大幅に低下するリスクあり。"
                    }
                elif ratio > 1.10:
                    return {
                        "type": "賃料やや割高",
                        "level": "low",
                        "message": f"現況賃料が相場の約{ratio:.0%}。やや割高で、退去後の賃料設定に注意。"
                    }
        except (FileNotFoundError, Exception):
            pass
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
