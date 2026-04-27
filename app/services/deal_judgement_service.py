from app.engines.price_engine import PriceEngine
from app.engines.yield_engine import YieldEngine
from app.engines.risk_engine import RiskEngine
from app.engines.development_engine import DevelopmentEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.offer_engine import OfferEngine
from app.engines.asset_type_engine import AssetTypeEngine
from app.services.hearing_generator import HearingGenerator
from app.services.report_generator import ReportGenerator
from app.models.property import PropertyData, AssetType
from typing import Optional


class DealJudgementService:
    def __init__(self, target_yield: Optional[float] = None):
        self._manual_target_yield = target_yield
        self.price_engine = PriceEngine()
        self.yield_engine = YieldEngine()
        self.risk_engine = RiskEngine()
        self.development_engine = DevelopmentEngine()
        self.scoring_engine = ScoringEngine()
        self.offer_engine = OfferEngine()
        self.asset_type_engine = AssetTypeEngine()
        self.hearing_generator = HearingGenerator()
        self.report_generator = ReportGenerator()

    def _get_target_yield(self, property_data: PropertyData) -> float:
        if self._manual_target_yield is not None:
            return self._manual_target_yield
        return self.asset_type_engine.get_target_yield(property_data.asset_type)

    def analyze(self, property_data: PropertyData) -> str:
        target_yield = self._get_target_yield(property_data)

        calculated_net_yield = self.yield_engine.calculate_net_yield(
            property_data.noi, property_data.price
        )
        if property_data.net_yield is None:
            property_data.net_yield = calculated_net_yield

        # 土地は収益還元価格を算出しない
        if property_data.asset_type == AssetType.LAND:
            income_value = None
            price_result = {"status": "参考値", "ratio": None,
                            "comment": "土地は収益還元価格を使用しません。路線価・開発利益で判断します。",
                            "income_value": None}
        else:
            income_value = self.price_engine.calculate_income_value(property_data.noi, target_yield)
            price_result = self.price_engine.judge_price(property_data.price, income_value)
            price_result["income_value"] = income_value

        risks = self.risk_engine.detect_risks(property_data)

        price_score = self.scoring_engine.price_score(price_result["status"])
        yield_score = self.yield_engine.score_yield(property_data.net_yield, target_yield)
        liquidity_score = self.scoring_engine.liquidity_score(property_data)
        development_score = self.development_engine.score_development(property_data)
        risk_score = self.risk_engine.score_risk(risks)
        broker_score = self.scoring_engine.broker_score(
            property_data.broker_chain_count, property_data.seller_motivation
        )

        score_result = self.scoring_engine.total_score(
            price_score, yield_score, liquidity_score, development_score,
            risk_score, broker_score, asset_type=property_data.asset_type
        )

        offer_result = self.offer_engine.calculate_offer_range(
            income_value, property_data.planned_repairs_cost, risk_discount_rate=0.05
        )

        questions = self.hearing_generator.generate_questions(risks, asset_type=property_data.asset_type)

        component_scores = {
            "price_score": price_score, "yield_score": yield_score,
            "liquidity_score": liquidity_score, "development_score": development_score,
            "risk_score": risk_score, "broker_score": broker_score
        }

        return self.report_generator.generate_markdown(
            property_data=property_data, price_result=price_result,
            score_result=score_result, offer_result=offer_result,
            risks=risks, questions=questions, component_scores=component_scores,
            target_yield=target_yield
        )
