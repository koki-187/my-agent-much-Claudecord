from typing import Optional, Tuple
from app.models.property import PropertyData, AssetType
from app.engines.asset_type_engine import AssetTypeEngine


class ScoringEngine:
    def __init__(self):
        self._asset_type_engine = AssetTypeEngine()

    def price_score(self, price_status: str) -> int:
        mapping = {
            "割安": 95, "適正": 80, "やや高い": 55, "高すぎる": 25, "判定不可": 40,
            "参考値": 50,  # 土地など収益還元不可の場合
        }
        return mapping.get(price_status, 40)

    def broker_score(self, broker_chain_count: Optional[int], seller_motivation: Optional[str]) -> int:
        score = 80
        if broker_chain_count is not None:
            if broker_chain_count >= 4:
                score -= 35
            elif broker_chain_count == 3:
                score -= 25
            elif broker_chain_count == 2:
                score -= 10
        if seller_motivation:
            if "高い" in seller_motivation:
                score += 10
            if "低い" in seller_motivation:
                score -= 20
        else:
            score -= 10
        return max(min(score, 100), 0)

    def liquidity_score(self, property_data: PropertyData) -> int:
        score = self._asset_type_engine.get_liquidity_base_score(property_data.asset_type)

        if property_data.address and any(
            area in property_data.address
            for area in ["東京", "大阪", "名古屋", "福岡", "横浜", "京都", "神戸", "札幌", "仙台"]
        ):
            score += 10

        if property_data.occupancy_rate is not None:
            if property_data.occupancy_rate >= 0.95:
                score += 10
            elif property_data.occupancy_rate < 0.85:
                score -= 20

        if property_data.built_year and property_data.built_year < 1981:
            score -= 15

        # 土地は稼働率・築年関係なし
        if property_data.asset_type == AssetType.LAND:
            score = self._asset_type_engine.get_liquidity_base_score(AssetType.LAND)
            if property_data.address and any(
                area in property_data.address
                for area in ["東京", "大阪", "名古屋", "福岡", "横浜", "京都", "神戸"]
            ):
                score += 15

        return max(min(score, 100), 0)

    def total_score(
        self,
        price_score: int,
        yield_score: int,
        liquidity_score: int,
        development_score: int,
        risk_score: int,
        broker_score: int,
        asset_type: Optional[AssetType] = None
    ) -> dict:
        if asset_type:
            w = self._asset_type_engine.get_score_weights(asset_type)
        else:
            w = (0.25, 0.20, 0.15, 0.15, 0.15, 0.10)

        total = (
            price_score * w[0] +
            yield_score * w[1] +
            liquidity_score * w[2] +
            development_score * w[3] +
            risk_score * w[4] +
            broker_score * w[5]
        )

        if total >= 85:
            rank, judgement = "S", "即対応・重点案件"
        elif total >= 70:
            rank, judgement = "A", "条件次第で積極検討"
        elif total >= 55:
            rank, judgement = "B", "指値前提で検討"
        elif total >= 40:
            rank, judgement = "C", "基本様子見・追加確認後判断"
        else:
            rank, judgement = "D", "原則追わない"

        return {"total_score": round(total, 1), "rank": rank, "judgement": judgement}
