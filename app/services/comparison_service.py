from typing import List
from app.models.property import PropertyData
from app.services.deal_judgement_service import DealJudgementService


class ComparisonService:
    def __init__(self):
        self.service = DealJudgementService()

    def compare(self, properties: List[PropertyData]) -> str:
        results = []
        for prop in properties:
            target_yield = self.service._get_target_yield(prop)
            income_value = self.service.price_engine.calculate_income_value(prop.noi, target_yield)
            price_result = self.service.price_engine.judge_price(prop.price, income_value)
            risks = self.service.risk_engine.detect_risks(prop)
            price_score = self.service.scoring_engine.price_score(price_result["status"])
            yield_score = self.service.yield_engine.score_yield(prop.net_yield, target_yield)
            liquidity_score = self.service.scoring_engine.liquidity_score(prop)
            development_score = self.service.development_engine.score_development(prop)
            risk_score = self.service.risk_engine.score_risk(risks)
            broker_score = self.service.scoring_engine.broker_score(prop.broker_chain_count, prop.seller_motivation)
            score_result = self.service.scoring_engine.total_score(
                price_score, yield_score, liquidity_score, development_score,
                risk_score, broker_score, asset_type=prop.asset_type
            )
            results.append({
                "name": prop.property_name or prop.address,
                "asset_type": prop.asset_type.value,
                "price": prop.price,
                "rank": score_result["rank"],
                "score": score_result["total_score"],
                "judgement": score_result["judgement"],
                "risk_count": len(risks),
                "price_status": price_result["status"],
            })

        # Markdownテーブル生成
        lines = ["# 案件比較レポート", "", "| 物件名 | 種別 | 価格 | ランク | スコア | 判断 | リスク数 | 価格判定 |",
                 "|---|---|---:|:---:|---:|---|---:|---|"]
        for r in results:
            lines.append(
                f"| {r['name']} | {r['asset_type']} | {r['price']:,}円 | "
                f"**{r['rank']}** | {r['score']} | {r['judgement']} | {r['risk_count']} | {r['price_status']} |"
            )
        lines.append("")
        lines.append(f"*比較対象: {len(properties)}件*")
        return "\n".join(lines)
