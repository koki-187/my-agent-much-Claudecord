from typing import Optional
from app.models.property import PropertyData


class ScoringEngine:
    def price_score(self, price_status: str) -> int:
        mapping = {
            "割安": 95,
            "適正": 80,
            "やや高い": 55,
            "高すぎる": 25,
            "判定不可": 40
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
        score = 70

        if property_data.address and any(
            area in property_data.address
            for area in ["東京", "大阪", "名古屋", "福岡", "横浜", "京都", "神戸"]
        ):
            score += 10

        if property_data.occupancy_rate is not None:
            if property_data.occupancy_rate >= 0.95:
                score += 10
            elif property_data.occupancy_rate < 0.85:
                score -= 20

        if property_data.built_year and property_data.built_year < 1981:
            score -= 15

        return max(min(score, 100), 0)

    def total_score(
        self,
        price_score: int,
        yield_score: int,
        liquidity_score: int,
        development_score: int,
        risk_score: int,
        broker_score: int
    ) -> dict:
        total = (
            price_score * 0.25 +
            yield_score * 0.20 +
            liquidity_score * 0.15 +
            development_score * 0.15 +
            risk_score * 0.15 +
            broker_score * 0.10
        )

        if total >= 85:
            rank = "S"
            judgement = "即対応・重点案件"
        elif total >= 70:
            rank = "A"
            judgement = "条件次第で積極検討"
        elif total >= 55:
            rank = "B"
            judgement = "指値前提で検討"
        elif total >= 40:
            rank = "C"
            judgement = "基本様子見・追加確認後判断"
        else:
            rank = "D"
            judgement = "原則追わない"

        return {
            "total_score": round(total, 1),
            "rank": rank,
            "judgement": judgement
        }
