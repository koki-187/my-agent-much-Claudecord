from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PlanType(str, Enum):
    INVESTMENT_1K = "区分1K投資マンション"
    FAMILY_MANSION = "ファミリーマンション"
    MIXED_MANSION = "単身&ファミリーミックス"
    COMMERCIAL = "商業施設"
    OFFICE = "オフィスビル"
    HOTEL = "ホテル"
    FACTORY_WAREHOUSE = "工場・倉庫"


@dataclass
class PlanScenario:
    plan_type: PlanType
    plan_name: str
    is_feasible: bool                      # 実現可能性
    feasibility_reason: str                # 実現可能/不可能の理由

    # 建築計画
    estimated_floor_area_sqm: Optional[float]     # 想定延床面積（㎡）
    estimated_floor_area_tsubo: Optional[float]   # 想定延床面積（坪）
    estimated_units: Optional[int]                 # 想定戸数/室数
    avg_unit_size_sqm: Optional[float]             # 平均専有面積（㎡）
    floors_estimated: Optional[int]                # 想定階数
    structure: str                                 # 構造（RC造/S造/木造等）

    # 収支試算
    total_revenue: Optional[int]           # 総売上 or 想定評価額（円）
    construction_cost: Optional[int]       # 建築費（円）
    soft_cost: Optional[int]               # 諸費用・設計費等（円）
    dev_profit: Optional[int]              # デベ利益（円）
    max_land_price: Optional[int]          # デベ最大買値（円）

    # 単価指標
    sale_price_per_sqm: Optional[int]      # 分譲/賃料換算単価（円/㎡）
    construction_cost_per_sqm: Optional[int]  # 建築費単価（円/㎡）
    price_per_land_sqm: Optional[int]      # 一種単価: 総売上÷土地面積（円/㎡）
    price_per_floor_sqm: Optional[int]     # 二種単価: 総売上÷延床面積（円/㎡）
    land_residual_ratio: Optional[float]   # 残地価率（地価÷総売上）

    # 収益系（賃貸・ホテル等）
    gross_yield_pct: Optional[float]       # 表面利回り
    noi_annual: Optional[int]              # NOI年間（円）

    # 市場比較
    market_price_per_unit: Optional[int]   # 周辺相場単価（円/㎡）
    deviation_from_market: Optional[float] # 周辺相場との乖離率（正=割高、負=割安）
    market_comment: str                    # 相場コメント

    # 評価
    land_price_evaluation: str             # 割安/適正/やや高い/高い/高すぎる
    price_vs_max: Optional[float]          # 売値÷デベ最大買値比率
    recommendation: str                    # 追う/条件次第/捨てる
    score: int                             # 0-100点
    score_breakdown: dict                  # スコア内訳

    # バイヤー5段階評価
    buyer_ratings: list  # [{"buyer_type": str, "rating": int(1-5), "comment": str, "price_threshold_man": Optional[int]}]


@dataclass
class LandPlanAnalysis:
    """用地プラン総合分析結果"""
    address: str
    land_area_sqm: float
    land_area_tsubo: float
    far_pct: float                         # 容積率（%）
    bcr_pct: float                         # 建蔽率（%）
    road_width_m: Optional[float]
    zoning: Optional[str]

    scenarios: list                        # list[PlanScenario]
    best_plan: Optional[str]               # 最適プランタイプ
    top_buyer_recommendation: str          # 最終推奨バイヤー
    overall_summary: str                   # 総合サマリー

    # 土地基本指標
    max_floor_area_sqm: float              # 最大延床面積
    max_footprint_sqm: float               # 最大建築面積
    land_price_asked: int                  # 売出価格
    land_price_per_tsubo: int              # 売出坪単価
    land_price_per_sqm: int               # 売出㎡単価
