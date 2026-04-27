from app.engines.price_engine import PriceEngine
from app.engines.yield_engine import YieldEngine
from app.engines.risk_engine import RiskEngine
from app.engines.development_engine import DevelopmentEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.offer_engine import OfferEngine
from app.services.hearing_generator import HearingGenerator
from app.services.report_generator import ReportGenerator
from app.models.property import PropertyData


class DealJudgementService:
    def __init__(self, target_yield: float = 0.075):
        self.target_yield = target_yield
        self.price_engine = PriceEngine()
        self.yield_engine = YieldEngine()
        self.risk_engine = RiskEngine()
        self.development_engine = DevelopmentEngine()
        self.scoring_engine = ScoringEngine()
        self.offer_engine = OfferEngine()
        self.hearing_generator = HearingGenerator()
        self.report_generator = ReportGenerator()

    def analyze(self, property_data: PropertyData) -> str:
        calculated_net_yield = self.yield_engine.calculate_net_yield(
            property_data.noi,
            property_data.price
        )

        if property_data.net_yield is None:
            property_data.net_yield = calculated_net_yield

        income_value = self.price_engine.calculate_income_value(
            property_data.noi,
            self.target_yield
        )

        price_result = self.price_engine.judge_price(
            property_data.price,
            income_value
        )
        price_result["income_value"] = income_value

        risks = self.risk_engine.detect_risks(property_data)

        price_score = self.scoring_engine.price_score(price_result["status"])
        yield_score = self.yield_engine.score_yield(
            property_data.net_yield,
            self.target_yield
        )
        liquidity_score = self.scoring_engine.liquidity_score(property_data)
        development_score = self.development_engine.score_development(property_data)
        risk_score = self.risk_engine.score_risk(risks)
        broker_score = self.scoring_engine.broker_score(
            property_data.broker_chain_count,
            property_data.seller_motivation
        )

        score_result = self.scoring_engine.total_score(
            price_score,
            yield_score,
            liquidity_score,
            development_score,
            risk_score,
            broker_score
        )

        offer_result = self.offer_engine.calculate_offer_range(
            income_value,
            property_data.planned_repairs_cost,
            risk_discount_rate=0.05
        )

        questions = self.hearing_generator.generate_questions(risks)

        component_scores = {
            "price_score": price_score,
            "yield_score": yield_score,
            "liquidity_score": liquidity_score,
            "development_score": development_score,
            "risk_score": risk_score,
            "broker_score": broker_score
        }

        return self.report_generator.generate_markdown(
            property_data=property_data,
            price_result=price_result,
            score_result=score_result,
            offer_result=offer_result,
            risks=risks,
            questions=questions,
            component_scores=component_scores
        )
