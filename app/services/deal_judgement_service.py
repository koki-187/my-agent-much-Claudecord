from app.engines.price_engine import PriceEngine
from app.engines.yield_engine import YieldEngine
from app.engines.risk_engine import RiskEngine
from app.engines.development_engine import DevelopmentEngine
from app.engines.scoring_engine import ScoringEngine
from app.engines.offer_engine import OfferEngine
from app.engines.asset_type_engine import AssetTypeEngine
from app.engines.rosenka_engine import RosenkaEngine
from app.engines.finance_engine import FinanceEngine
from app.engines.exit_strategy_engine import ExitStrategyEngine
from app.engines.repair_cost_engine import RepairCostEngine
from app.engines.area_trend_engine import AreaTrendEngine
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
        self.rosenka_engine = RosenkaEngine()
        self.finance_engine = FinanceEngine()
        self.exit_strategy_engine = ExitStrategyEngine()
        self.repair_cost_engine = RepairCostEngine()
        self.area_trend_engine = AreaTrendEngine()
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

        # エリアトレンドによるスコア調整
        asset_type_key = self.finance_engine.get_asset_type_key(property_data.asset_type.value)
        area_trend = self.area_trend_engine.evaluate(property_data.address, asset_type_key)
        trend_adjustment = area_trend.trend_score_adjustment if area_trend else 0

        score_result = self.scoring_engine.total_score(
            price_score, yield_score, liquidity_score + trend_adjustment,
            development_score, risk_score, broker_score,
            asset_type=property_data.asset_type
        )

        offer_result = self.offer_engine.calculate_offer_range(
            income_value, property_data.planned_repairs_cost, risk_discount_rate=0.05
        )

        # 路線価分析
        rosenka_result = self.rosenka_engine.lookup(
            property_data.address, property_data.price,
            property_data.land_area_sqm, property_data.zoning
        )

        # 融資シミュレーション
        finance_result = self.finance_engine.simulate(
            price=property_data.price,
            noi=property_data.noi,
            asset_type_key=asset_type_key,
            built_year=property_data.built_year,
        )

        # 出口戦略評価
        exit_result = self.exit_strategy_engine.evaluate(
            price=property_data.price,
            noi=property_data.noi,
            asset_type_key=asset_type_key,
            address=property_data.address,
            built_year=property_data.built_year,
            occupancy_rate=property_data.occupancy_rate,
        )

        # 修繕費積算
        repair_result = self.repair_cost_engine.estimate(
            asset_type_key=asset_type_key,
            building_area_sqm=property_data.building_area_sqm,
            built_year=property_data.built_year,
            structure=property_data.structure,
            planned_repairs_cost=property_data.planned_repairs_cost,
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
            target_yield=target_yield, rosenka_result=rosenka_result,
            finance_result=finance_result, exit_result=exit_result,
            repair_result=repair_result, area_trend=area_trend,
        )
