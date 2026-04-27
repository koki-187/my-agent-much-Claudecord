from typing import List
from app.models.property import PropertyData
from app.engines.asset_type_engine import AssetTypeEngine


class RiskEngine:
    def __init__(self):
        self._asset_type_engine = AssetTypeEngine()

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

        return risks

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
