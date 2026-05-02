"""
LandPlanEngine — 用地プラン総合分析エンジン（7プランタイプ対応）

各プランタイプの収支試算・一種/二種単価・バイヤー5段階評価を行う。
"""

import json
import math
from pathlib import Path
from typing import Optional

from app.models.land_plan import (
    LandPlanAnalysis,
    PlanScenario,
    PlanType,
)

# ベンチマークデータのパス
_BENCHMARK_PATH = Path(__file__).parent.parent / "data" / "land_plan_benchmarks.json"

# 坪換算係数
_SQM_TO_TSUBO = 1 / 3.30579

# 共用部控除率
_FLOOR_AREA_EFFICIENCY = 0.93

# 諸費用率（建築費に対する割合）
_SOFT_COST_RATIO = 0.10

# デベ利益率（総売上に対する割合）
_DEV_PROFIT_RATIO = 0.15

# ホテル売上に対する賃料換算係数（利益率ベース）
_HOTEL_REVENUE_TO_RENT_RATIO = 0.35

# 用途地域: 工業系
_INDUSTRIAL_ZONINGS = {"工業地域", "工業専用地域", "準工業地域"}

# 用途地域: 商業系
_COMMERCIAL_ZONINGS = {"商業地域", "近隣商業地域"}

# エリアグレード判定: S区
_S_WARDS = {"千代田区", "中央区", "港区", "新宿区", "渋谷区"}

# エリアグレード判定: A区
_A_WARDS = {
    "文京区", "目黒区", "世田谷区", "品川区",
    "中野区", "杉並区", "豊島区", "台東区",
}

# エリアグレード判定: B区（東京23区の残り）
_B_WARDS = {
    "江東区", "墨田区", "荒川区", "足立区", "葛飾区",
    "江戸川区", "北区", "板橋区", "練馬区", "大田区",
    "新宿区", "渋谷区",  # 重複しても検索対象に含める（S優先のためB判定には届かない）
}

# プラン名 → PlanType マッピング
_PLAN_NAME_MAP = {
    "区分1K投資マンション": PlanType.INVESTMENT_1K,
    "ファミリーマンション": PlanType.FAMILY_MANSION,
    "単身&ファミリーミックス": PlanType.MIXED_MANSION,
    "商業施設": PlanType.COMMERCIAL,
    "オフィスビル": PlanType.OFFICE,
    "ホテル": PlanType.HOTEL,
    "工場・倉庫": PlanType.FACTORY_WAREHOUSE,
}

# 価格評価ラベル
_PRICE_LABELS = [
    (0.85, "割安"),
    (1.00, "適正"),
    (1.15, "やや高い"),
    (1.30, "高い"),
    (float("inf"), "高すぎる"),
]

# 推奨ラベル
_RECOMMEND_LABELS = [
    (1.00, "追う"),
    (1.15, "条件次第"),
    (float("inf"), "捨てる"),
]


def _load_benchmarks() -> dict:
    with open(_BENCHMARK_PATH, encoding="utf-8") as f:
        return json.load(f)


class LandPlanEngine:
    """用地プラン総合分析エンジン"""

    def __init__(self) -> None:
        self._benchmarks = _load_benchmarks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        address: str,
        price: int,
        land_area_sqm: float,
        far: float,
        bcr: float,
        road_width_m: Optional[float] = None,
        zoning: Optional[str] = None,
        walk_minutes: Optional[int] = None,
    ) -> LandPlanAnalysis:
        """全7プランを分析してLandPlanAnalysisを返す"""
        area_grade = self._get_area_grade(address)
        plans_bench = self._benchmarks["area_grades"][area_grade]["plans"]

        land_area_tsubo = land_area_sqm * _SQM_TO_TSUBO
        max_floor_area_sqm = land_area_sqm * (far / 100.0) * _FLOOR_AREA_EFFICIENCY
        max_footprint_sqm = land_area_sqm * (bcr / 100.0)

        land_price_per_sqm = int(price / land_area_sqm) if land_area_sqm > 0 else 0
        land_price_per_tsubo = int(price / land_area_tsubo) if land_area_tsubo > 0 else 0

        scenarios = []
        for plan_name, bench in plans_bench.items():
            plan_type = _PLAN_NAME_MAP.get(plan_name)
            if plan_type is None:
                continue
            scenario = self._calc_plan(
                plan_type=plan_type,
                bench=bench,
                land_area_sqm=land_area_sqm,
                far=far,
                bcr=bcr,
                price=price,
                area_grade=area_grade,
                zoning=zoning or "",
                road_width_m=road_width_m or 0.0,
                walk_minutes=walk_minutes or 10,
            )
            scenarios.append(scenario)

        best_plan = self._find_best_plan(scenarios)
        top_recommendation = self._build_top_recommendation(scenarios, address)
        overall_summary = self._build_overall_summary(
            scenarios, address, price, land_area_sqm, area_grade
        )

        return LandPlanAnalysis(
            address=address,
            land_area_sqm=land_area_sqm,
            land_area_tsubo=round(land_area_tsubo, 2),
            far_pct=far,
            bcr_pct=bcr,
            road_width_m=road_width_m,
            zoning=zoning,
            scenarios=scenarios,
            best_plan=best_plan,
            top_buyer_recommendation=top_recommendation,
            overall_summary=overall_summary,
            max_floor_area_sqm=round(max_floor_area_sqm, 2),
            max_footprint_sqm=round(max_footprint_sqm, 2),
            land_price_asked=price,
            land_price_per_tsubo=land_price_per_tsubo,
            land_price_per_sqm=land_price_per_sqm,
        )

    # ------------------------------------------------------------------
    # Area grade
    # ------------------------------------------------------------------

    def _get_area_grade(self, address: str) -> str:
        """エリアグレード判定（S/A/B/C）"""
        for ward in _S_WARDS:
            if ward in address:
                return "S"
        for ward in _A_WARDS:
            if ward in address:
                return "A"
        # 23区かどうかをキーワード「区」で大雑把に判定
        b_keywords = list(_B_WARDS)
        for ward in b_keywords:
            if ward in address:
                return "B"
        # 「東京都」が含まれ「区」で終わるワードがあれば B
        if "東京都" in address and "区" in address:
            return "B"
        return "C"

    # ------------------------------------------------------------------
    # Plan calculation
    # ------------------------------------------------------------------

    def _calc_plan(
        self,
        plan_type: PlanType,
        bench: dict,
        land_area_sqm: float,
        far: float,
        bcr: float,
        price: int,
        area_grade: str,
        zoning: str,
        road_width_m: float,
        walk_minutes: int,
    ) -> PlanScenario:
        """1プランの収支計算"""
        is_feasible, feasibility_reason = self._check_feasibility(
            plan_type, far, bcr, zoning, road_width_m, land_area_sqm
        )

        # 基本面積計算
        floor_area_sqm = land_area_sqm * (far / 100.0) * _FLOOR_AREA_EFFICIENCY
        floor_area_tsubo = floor_area_sqm * _SQM_TO_TSUBO
        footprint_sqm = land_area_sqm * (bcr / 100.0)

        # 構造・建築費単価
        structure, construction_cost_per_sqm = self._get_structure_and_cost(
            plan_type, bench
        )

        # 総売上（分譲系 or 収益系）
        total_revenue, sale_price_per_sqm, gross_yield_pct, noi_annual = (
            self._calc_revenue(
                plan_type, bench, floor_area_sqm, floor_area_tsubo, land_area_sqm
            )
        )

        # 建築費・諸費用
        construction_cost = int(floor_area_sqm * construction_cost_per_sqm)
        soft_cost = int(construction_cost * _SOFT_COST_RATIO)

        # デベ利益・最大買値
        dev_profit = int(total_revenue * _DEV_PROFIT_RATIO) if total_revenue else None
        residual_ratio = bench.get("land_residual_ratio", 0.25)
        max_land_price = (
            int(total_revenue * residual_ratio) if total_revenue else None
        )

        # 単価指標
        price_per_land_sqm = (
            int(total_revenue / land_area_sqm)
            if total_revenue and land_area_sqm > 0
            else None
        )
        price_per_floor_sqm = (
            int(total_revenue / floor_area_sqm)
            if total_revenue and floor_area_sqm > 0
            else None
        )

        # 想定戸数/室数
        avg_unit_size = bench.get("avg_unit_size_sqm", 30)
        avg_room_size = bench.get("avg_room_size_sqm", avg_unit_size)
        if plan_type == PlanType.HOTEL:
            estimated_units = max(1, int(floor_area_sqm / avg_room_size))
        elif plan_type in (
            PlanType.COMMERCIAL,
            PlanType.OFFICE,
            PlanType.FACTORY_WAREHOUSE,
        ):
            estimated_units = None
        else:
            estimated_units = max(1, int(floor_area_sqm / avg_unit_size))

        # 想定階数（簡易推定: 延床÷建築面積）
        floors_estimated = (
            max(1, math.ceil(floor_area_sqm / footprint_sqm))
            if footprint_sqm > 0
            else None
        )

        # 市場比較
        market_price_per_unit = sale_price_per_sqm
        price_vs_max = (
            price / max_land_price if max_land_price and max_land_price > 0 else None
        )
        deviation_from_market = (
            (price / land_area_sqm - (market_price_per_unit or 0))
            / (market_price_per_unit or 1)
            if market_price_per_unit
            else None
        )
        market_comment = self._build_market_comment(
            plan_type, price_vs_max, area_grade
        )

        # 評価ラベル
        land_price_evaluation = self._get_price_label(price_vs_max)
        recommendation = self._get_recommendation_label(price_vs_max)

        # スコア計算
        score, score_breakdown = self._calc_score(
            price=price,
            max_land_price=max_land_price or 0,
            area_grade=area_grade,
            far=far,
            is_feasible=is_feasible,
            walk_minutes=walk_minutes,
        )

        # バイヤー評価
        buyer_ratings = self._calc_buyer_ratings(
            plan_type=plan_type,
            price=price,
            max_land_price=max_land_price or 0,
            bench=bench,
            area_grade=area_grade,
        )

        return PlanScenario(
            plan_type=plan_type,
            plan_name=plan_type.value,
            is_feasible=is_feasible,
            feasibility_reason=feasibility_reason,
            estimated_floor_area_sqm=round(floor_area_sqm, 1),
            estimated_floor_area_tsubo=round(floor_area_tsubo, 1),
            estimated_units=estimated_units,
            avg_unit_size_sqm=float(avg_unit_size) if plan_type not in (
                PlanType.COMMERCIAL, PlanType.OFFICE, PlanType.FACTORY_WAREHOUSE
            ) else None,
            floors_estimated=floors_estimated,
            structure=structure,
            total_revenue=total_revenue,
            construction_cost=construction_cost,
            soft_cost=soft_cost,
            dev_profit=dev_profit,
            max_land_price=max_land_price,
            sale_price_per_sqm=sale_price_per_sqm,
            construction_cost_per_sqm=construction_cost_per_sqm,
            price_per_land_sqm=price_per_land_sqm,
            price_per_floor_sqm=price_per_floor_sqm,
            land_residual_ratio=residual_ratio,
            gross_yield_pct=gross_yield_pct,
            noi_annual=noi_annual,
            market_price_per_unit=market_price_per_unit,
            deviation_from_market=round(deviation_from_market, 3) if deviation_from_market is not None else None,
            market_comment=market_comment,
            land_price_evaluation=land_price_evaluation,
            price_vs_max=round(price_vs_max, 3) if price_vs_max is not None else None,
            recommendation=recommendation,
            score=score,
            score_breakdown=score_breakdown,
            buyer_ratings=buyer_ratings,
        )

    # ------------------------------------------------------------------
    # Revenue calculation
    # ------------------------------------------------------------------

    def _calc_revenue(
        self,
        plan_type: PlanType,
        bench: dict,
        floor_area_sqm: float,
        floor_area_tsubo: float,
        land_area_sqm: float,
    ) -> tuple:
        """(total_revenue, sale_price_per_sqm, gross_yield_pct, noi_annual)"""
        if plan_type in (
            PlanType.INVESTMENT_1K,
            PlanType.FAMILY_MANSION,
            PlanType.MIXED_MANSION,
        ):
            # 分譲系: 総売上 = 延床面積 × 分譲単価
            sale_price_per_sqm = bench["sale_price_per_sqm"]
            total_revenue = int(floor_area_sqm * sale_price_per_sqm)
            # 分譲利回りは参考値として典型値を返す
            typical_yield = bench.get("typical_yield_pct")
            return total_revenue, sale_price_per_sqm, typical_yield, None

        if plan_type == PlanType.HOTEL:
            # ホテル: RevPAR = ADR × OCC
            adr = bench["adr"]
            occ = bench["occ_rate"]
            avg_room_size = bench.get("avg_room_size_sqm", 22)
            rooms = max(1, int(floor_area_sqm / avg_room_size))
            revpar = adr * occ
            annual_revenue = revpar * rooms * 365
            # 賃料換算（利益率35%相当）
            annual_rent = annual_revenue * _HOTEL_REVENUE_TO_RENT_RATIO
            cap_rate = bench.get("cap_rate_pct", 5.0) / 100.0
            total_revenue = int(annual_rent / cap_rate)
            noi_annual = int(annual_rent)
            # 参考利回り（NOI / 物件評価額）
            gross_yield_pct = bench.get("cap_rate_pct", 5.0)
            # 賃料換算単価（評価額÷延床）
            sale_price_per_sqm = (
                int(total_revenue / floor_area_sqm) if floor_area_sqm > 0 else None
            )
            return total_revenue, sale_price_per_sqm, gross_yield_pct, noi_annual

        # 賃貸系: 商業・オフィス・工場倉庫
        # 評価額 = 年間賃料収入 / Cap Rate
        monthly_rent_per_tsubo = bench["monthly_rent_per_tsubo"]
        cap_rate = bench["cap_rate_pct"] / 100.0
        # 年間賃料収入 = 月坪賃料 × 坪数 × 12 × 稼働率（0.95想定）
        occupancy = 0.95
        annual_rent = monthly_rent_per_tsubo * floor_area_tsubo * 12 * occupancy
        noi_annual = int(annual_rent)
        total_revenue = int(annual_rent / cap_rate)
        gross_yield_pct = bench["cap_rate_pct"]
        sale_price_per_sqm = (
            int(total_revenue / floor_area_sqm) if floor_area_sqm > 0 else None
        )
        return total_revenue, sale_price_per_sqm, gross_yield_pct, noi_annual

    # ------------------------------------------------------------------
    # Structure & cost
    # ------------------------------------------------------------------

    def _get_structure_and_cost(
        self, plan_type: PlanType, bench: dict
    ) -> tuple:
        """(structure_label, cost_per_sqm)"""
        cost = bench["construction_cost_per_sqm"]
        if plan_type in (
            PlanType.INVESTMENT_1K,
            PlanType.FAMILY_MANSION,
            PlanType.MIXED_MANSION,
            PlanType.HOTEL,
        ):
            return "RC造", cost
        if plan_type == PlanType.OFFICE:
            return "S造/RC造", cost
        if plan_type == PlanType.COMMERCIAL:
            return "S造", cost
        # 工場・倉庫
        return "S造（倉庫仕様）", cost

    # ------------------------------------------------------------------
    # Feasibility check
    # ------------------------------------------------------------------

    def _check_feasibility(
        self,
        plan_type: PlanType,
        far: float,
        bcr: float,
        zoning: str,
        road_width_m: float,
        land_area_sqm: float,
    ) -> tuple:
        """実現可能性チェック -> (is_feasible: bool, reason: str)"""
        zoning_set = {z.strip() for z in zoning.split("/")} if zoning else set()

        if plan_type == PlanType.FACTORY_WAREHOUSE:
            required = {"工業地域", "準工業地域"}
            if not (zoning_set & required):
                return False, f"用途地域が工業系でないため建築不可（現在: {zoning or '不明'}）"
            return True, "工業系用途地域のため建築可能"

        if plan_type == PlanType.HOTEL:
            # 旅館業法: 住居専用地域では原則不可
            residential_only = {
                "第一種低層住居専用地域", "第二種低層住居専用地域",
                "第一種中高層住居専用地域", "第二種中高層住居専用地域",
            }
            if zoning_set & residential_only:
                return False, f"住居専用地域ではホテル建築不可（現在: {zoning}）"
            if far < 200:
                return False, f"容積率{far:.0f}%ではホテルの採算が困難（目安200%以上）"
            return True, "旅館業法許可エリアの可能性あり・要確認"

        if plan_type == PlanType.COMMERCIAL:
            if far < 200:
                return False, f"容積率{far:.0f}%では商業施設の採算が困難（目安200%以上）"
            return True, "商業施設の建築は容積率・用途地域とも概ね問題なし"

        if plan_type == PlanType.OFFICE:
            if far < 300:
                return (
                    False,
                    f"容積率{far:.0f}%ではオフィスビルの採算が困難（目安300%以上）",
                )
            return True, "容積率・用途地域とも概ね問題なし"

        # マンション系（1K / ファミリー / ミックス）
        if far < 200:
            return (
                False,
                f"容積率{far:.0f}%ではマンション計画が成立しにくい（最低200%以上推奨）",
            )
        if road_width_m and road_width_m < 4.0:
            return (
                True,
                f"道路幅{road_width_m}mのためセットバック必要・有効宅地面積が減少する点に注意",
            )
        return True, f"容積率{far:.0f}%・建蔽率{bcr:.0f}%とも計画に問題なし"

    # ------------------------------------------------------------------
    # Score calculation
    # ------------------------------------------------------------------

    def _calc_score(
        self,
        price: int,
        max_land_price: int,
        area_grade: str,
        far: float,
        is_feasible: bool,
        walk_minutes: int,
    ) -> tuple:
        """プランスコア計算（0-100）-> (score, breakdown)"""
        breakdown = {}

        # 1. 価格評価 (40点)
        if max_land_price > 0:
            ratio = price / max_land_price
            if ratio <= 0.85:
                price_score = 40
            elif ratio <= 1.00:
                price_score = int(40 * (1.00 - ratio) / 0.15 * 0.3 + 28)
            elif ratio <= 1.15:
                price_score = int(28 * (1.15 - ratio) / 0.15)
            elif ratio <= 1.30:
                price_score = int(15 * (1.30 - ratio) / 0.15)
            else:
                price_score = 0
        else:
            price_score = 20  # データ不足時は中間点
        breakdown["price_score"] = price_score

        # 2. エリア評価 (30点)
        area_map = {"S": 30, "A": 22, "B": 14, "C": 6}
        area_score = area_map.get(area_grade, 10)
        breakdown["area_score"] = area_score

        # 3. 物件要件 (20点)
        req_score = 0
        if is_feasible:
            req_score += 12
        if far >= 300:
            req_score += 8
        elif far >= 200:
            req_score += 5
        elif far >= 150:
            req_score += 2
        breakdown["requirement_score"] = req_score

        # 4. 市場性 (10点)
        walk_score = 0
        if walk_minutes <= 3:
            walk_score = 10
        elif walk_minutes <= 5:
            walk_score = 8
        elif walk_minutes <= 10:
            walk_score = 6
        elif walk_minutes <= 15:
            walk_score = 3
        breakdown["market_score"] = walk_score

        total = price_score + area_score + req_score + walk_score
        total = max(0, min(100, total))
        return total, breakdown

    # ------------------------------------------------------------------
    # Buyer ratings
    # ------------------------------------------------------------------

    def _calc_buyer_ratings(
        self,
        plan_type: PlanType,
        price: int,
        max_land_price: int,
        bench: dict,
        area_grade: str,
    ) -> list:
        """バイヤー5段階評価を計算"""
        buyer_types = bench.get("buyer_types", [])
        ratio = price / max_land_price if max_land_price > 0 else 99.0

        # レーティング基準
        if ratio <= 1.00:
            base_rating = 5
            base_comment = "売値がデベ最大買値以内 → 積極検討圏"
        elif ratio <= 1.15:
            base_rating = 4
            base_comment = "売値がやや高いが指値次第で検討可能"
        elif ratio <= 1.30:
            base_rating = 3
            base_comment = "慎重検討 → 大幅な指値交渉が必要"
        elif ratio <= 1.50:
            base_rating = 2
            base_comment = "現状価格では厳しい → 大幅指値必要"
        else:
            base_rating = 1
            base_comment = "現実的に困難 → 価格が大幅に乖離"

        price_threshold_man = int(max_land_price / 10000) if max_land_price > 0 else None

        ratings = []
        # バイヤータイプごとに微調整（先頭バイヤーを主力として評価）
        for i, buyer_type in enumerate(buyer_types):
            # 2番目以降はやや保守的
            adj = -1 if i >= 2 else 0
            rating = max(1, min(5, base_rating + adj))
            comment = base_comment
            if i == 0:
                comment = f"[主力バイヤー] {base_comment}"
            ratings.append(
                {
                    "buyer_type": buyer_type,
                    "rating": rating,
                    "comment": comment,
                    "price_threshold_man": price_threshold_man,
                }
            )

        # バイヤーが空の場合のデフォルト
        if not ratings:
            ratings.append(
                {
                    "buyer_type": "一般デベロッパー",
                    "rating": base_rating,
                    "comment": base_comment,
                    "price_threshold_man": price_threshold_man,
                }
            )
        return ratings

    # ------------------------------------------------------------------
    # Best plan & summary
    # ------------------------------------------------------------------

    def _find_best_plan(self, scenarios: list) -> Optional[str]:
        """最適プランを選出（スコア最大・実現可能なプランを返す）"""
        feasible = [s for s in scenarios if s.is_feasible]
        if not feasible:
            return None
        best = max(feasible, key=lambda s: s.score)
        return best.plan_name

    def _build_top_recommendation(self, scenarios: list, address: str) -> str:
        """最終推奨メッセージ生成"""
        feasible = [s for s in scenarios if s.is_feasible]
        if not feasible:
            return "実現可能なプランがありません。用途地域・容積率の条件を確認してください。"

        top = max(feasible, key=lambda s: s.score)
        buyers = [r["buyer_type"] for r in top.buyer_ratings[:2]]
        buyer_str = "・".join(buyers)
        return (
            f"最適プラン「{top.plan_name}」({address}) → "
            f"推奨バイヤー: {buyer_str} / スコア{top.score}点 / {top.recommendation}"
        )

    def _build_overall_summary(
        self,
        scenarios: list,
        address: str,
        price: int,
        land_area_sqm: float,
        area_grade: str,
    ) -> str:
        """総合サマリー生成"""
        feasible = [s for s in scenarios if s.is_feasible]
        infeasible_names = [s.plan_name for s in scenarios if not s.is_feasible]

        price_man = price // 10000
        area_str = f"エリアグレード{area_grade}"
        feasible_str = "・".join(s.plan_name for s in feasible) if feasible else "なし"
        infeasible_str = "・".join(infeasible_names) if infeasible_names else "なし"

        best_scenario = max(feasible, key=lambda s: s.score) if feasible else None
        best_info = (
            f"最有力: {best_scenario.plan_name}（スコア{best_scenario.score}点・{best_scenario.recommendation}）"
            if best_scenario
            else "有望プランなし"
        )

        return (
            f"【用地分析サマリー】{address} / {price_man:,}万円 / {land_area_sqm:.1f}㎡ / {area_str}\n"
            f"実現可能プラン: {feasible_str}\n"
            f"実現困難プラン: {infeasible_str}\n"
            f"{best_info}"
        )

    # ------------------------------------------------------------------
    # Helper labels
    # ------------------------------------------------------------------

    @staticmethod
    def _get_price_label(price_vs_max: Optional[float]) -> str:
        if price_vs_max is None:
            return "評価不能"
        for threshold, label in _PRICE_LABELS:
            if price_vs_max < threshold:
                return label
        return "高すぎる"

    @staticmethod
    def _get_recommendation_label(price_vs_max: Optional[float]) -> str:
        if price_vs_max is None:
            return "条件次第"
        for threshold, label in _RECOMMEND_LABELS:
            if price_vs_max <= threshold:
                return label
        return "捨てる"

    @staticmethod
    def _build_market_comment(
        plan_type: PlanType, price_vs_max: Optional[float], area_grade: str
    ) -> str:
        if price_vs_max is None:
            return "相場データ不足のため評価不能"
        if price_vs_max <= 1.00:
            return f"{area_grade}エリア相場内の適正価格水準。デベ目線でも競争力あり。"
        if price_vs_max <= 1.15:
            return f"{area_grade}エリア相場をやや上回る。指値交渉で成立の可能性あり。"
        if price_vs_max <= 1.30:
            return f"{area_grade}エリア相場を大きく上回る。{plan_type.value}プランでは厳しい。"
        return f"相場から大幅に乖離。{plan_type.value}プランでの成立は現実的でない。"
