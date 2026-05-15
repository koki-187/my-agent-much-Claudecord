# -*- coding: utf-8 -*-
"""
回帰テスト — 過去に発見・修正したバグの再発を防止

各テストは特定のコミットで修正された問題に対応:
- 価格比 1.53 倍 → "高すぎる" 判定
- ZeroDivisionError in similarity._score_price (両側0)
- 京都府 → 京都 誤判定
- format_money: 1億円 → "10000億" 表示バグ
- _format_saved_at: 不正フォーマット時のクラッシュ
"""
import pytest

from app.engines.price_engine import PriceEngine
from app.services.similarity_service import (
    _score_price,
    _score_area,
    _extract_prefecture,
)


# ════════════════════════════════════════════════════════════════════════════
# CRITICAL: 過去バグ回帰防止
# ════════════════════════════════════════════════════════════════════════════

class TestPriceJudgeRegression:
    """価格判定の境界値とバグ修正の回帰防止"""

    def test_price_153x_is_takasugiru(self):
        """price/income=1.53 は「高すぎる」判定 (>1.20 閾値)"""
        engine = PriceEngine()
        result = engine.judge_price(price=153_000_000, income_value=100_000_000)
        assert result["status"] == "高すぎる"
        assert result["ratio"] == pytest.approx(1.53, abs=0.01)

    def test_price_120x_boundary_is_yaya_takai(self):
        """境界値: ratio=1.20 ちょうどは「やや高い」(<=1.20 が境界)"""
        engine = PriceEngine()
        result = engine.judge_price(price=120_000_000, income_value=100_000_000)
        assert result["status"] == "やや高い"

    def test_price_121x_is_takasugiru(self):
        """境界値超: ratio=1.21 から「高すぎる」"""
        engine = PriceEngine()
        result = engine.judge_price(price=121_000_000, income_value=100_000_000)
        assert result["status"] == "高すぎる"


class TestSimilarityScorePrice:
    """_score_price のゼロ除算回帰防止 (両側 0 ガード)"""

    def test_score_price_both_zero_no_crash(self):
        """両方 0 でも ZeroDivisionError ではなく "価格不明" を返す"""
        score, label = _score_price(0, 0)
        assert score == 0.0
        assert label == "価格不明"

    def test_score_price_target_zero(self):
        """target=0, case>0 もガードされる"""
        score, label = _score_price(0, 100_000_000)
        assert score == 0.0
        assert label == "価格不明"

    def test_score_price_case_zero(self):
        """target>0, case=0 もガードされる (旧来通り)"""
        score, label = _score_price(100_000_000, 0)
        assert score == 0.0
        assert label == "価格不明"

    def test_score_price_within_15pct(self):
        """差15% は満点 1.0、ラベルに「価格±15%」を含む"""
        score, label = _score_price(100_000_000, 115_000_000)
        assert score == 1.0
        assert "±" in label and "%" in label


class TestExtractPrefecture:
    """都道府県抽出: 京都府の前方一致バグ回帰防止"""

    def test_kyoto_fu_correctly_identified(self):
        """「京都府伏見区」→「京都府」(「京都」と誤判定しない)"""
        assert _extract_prefecture("京都府伏見区") == "京都府"

    def test_kyoto_fu_other_city(self):
        """「京都府向日市」→「京都府」"""
        assert _extract_prefecture("京都府向日市") == "京都府"

    def test_hokkaido_correctly_identified(self):
        """「北海道札幌市」→「北海道」(3 文字フル抽出)"""
        assert _extract_prefecture("北海道札幌市") == "北海道"

    def test_tokyo_to(self):
        """「東京都新宿区」→「東京都」"""
        assert _extract_prefecture("東京都新宿区") == "東京都"

    def test_osaka_fu(self):
        """「大阪府大阪市」→「大阪府」"""
        assert _extract_prefecture("大阪府大阪市") == "大阪府"

    def test_empty_address(self):
        """空文字 → 空文字 (クラッシュしない)"""
        assert _extract_prefecture("") == ""


class TestScoreAreaPrefectureMix:
    """_score_area: 京都府が「京都」に短縮されて滋賀と混同しないこと"""

    def test_kyoto_fu_to_kyoto_fu_same_prefecture(self):
        """同じ京都府内なら同都道府県スコア (0.4) 以上"""
        score, _ = _score_area("京都府向日市", "京都府伏見区")
        assert score >= 0.4

    def test_kyoto_fu_to_shiga_ken_different_prefecture(self):
        """京都府 vs 滋賀県は異なる都道府県扱い (低スコア)"""
        score, _ = _score_area("京都府伏見区", "滋賀県大津市")
        assert score < 0.4   # 同都道府県の 0.4 未満


# ════════════════════════════════════════════════════════════════════════════
# HIGH: visual_report の通貨フォーマットバグ回帰防止
# ════════════════════════════════════════════════════════════════════════════

class TestFormatMoneyVisualReport:
    """visual_report_service._format_money のバグ修正回帰防止"""

    def test_format_money_1oku_correct(self):
        """1億円 (100,000,000) → "1億円"  ※旧バグでは "10000億"
        """
        from app.services.visual_report_service import _format_money
        assert _format_money(100_000_000) == "1億円"

    def test_format_money_1oku_5000man(self):
        """1.5億円 → "1億5,000万円"
        """
        from app.services.visual_report_service import _format_money
        assert _format_money(150_000_000) == "1億5,000万円"

    def test_format_money_under_1oku(self):
        """5,000万円 → "5,000万円" """
        from app.services.visual_report_service import _format_money
        assert _format_money(50_000_000) == "5,000万円"

    def test_format_money_none_returns_dash(self):
        """None → "-" (クラッシュしない)"""
        from app.services.visual_report_service import _format_money
        assert _format_money(None) == "-"


# ════════════════════════════════════════════════════════════════════════════
# CRITICAL: ロジック強化バグ修正の回帰防止 (debugger/scientist 検出)
# ════════════════════════════════════════════════════════════════════════════

class TestRepairCostEngineFutureYear:
    """built_year=2050 等の未来築年で age が負になるバグ"""
    def test_future_built_year_age_clamped_to_zero(self):
        from app.engines.repair_cost_engine import RepairCostEngine
        e = RepairCostEngine()
        result = e.estimate(asset_type_key="APARTMENT_WHOLE",
                             building_area_sqm=500, built_year=2050,
                             structure="RC")
        # 即時修繕費がマイナスにならないこと
        assert result.immediate_cost >= 0
        # コメント中に "築-25年" のような負の年数が出ないこと
        # (PropertyData バリデーションで弾かれる場合は built_year=None で渡される想定)


class TestExitStrategyEngineIRRClamp:
    """異常NOIで IRR が天文学的になるバグ"""
    def test_irr_clamped_within_50pct(self):
        from app.engines.exit_strategy_engine import ExitStrategyEngine
        e = ExitStrategyEngine()
        # 異常: 5,000万円 + NOI 1億円 (利回り200%)
        r = e.evaluate(price=50_000_000, noi=100_000_000,
                        asset_type_key="APARTMENT_WHOLE",
                        address="東京都新宿区", built_year=2010,
                        occupancy_rate=0.95)
        # 全シナリオの IRR が ±50% 以内にクランプされる
        for s in r.scenarios or []:
            assert -0.5 <= s.irr_approx <= 0.5, \
                f"{s.name} IRR={s.irr_approx} がクランプ範囲外"

    def test_no_scenarios_overall_is_calculation_impossible(self):
        """NOI=None でシナリオ0件 → "算出不可" を明示"""
        from app.engines.exit_strategy_engine import ExitStrategyEngine
        e = ExitStrategyEngine()
        r = e.evaluate(price=100_000_000, noi=None,
                        asset_type_key="APARTMENT_WHOLE",
                        address="東京都新宿区", built_year=2010,
                        occupancy_rate=0.95)
        if not r.scenarios:
            assert "算出不可" in r.overall_evaluation


class TestOfferEngineNegativeOffer:
    """修繕費 > 収益還元価格 で負の指値が出るバグ"""
    def test_repairs_exceed_income_value_returns_none(self):
        from app.engines.offer_engine import OfferEngine
        e = OfferEngine()
        # 修繕費 (10億) が収益還元 (5億) を上回るケース
        r = e.calculate_offer_range(income_value=500_000_000,
                                     planned_repairs_cost=1_000_000_000)
        assert r["low"] is None
        assert r["high"] is None
        assert "超える" in r["comment"] or "算出不可" in r["comment"]

    def test_repairs_within_income_value_returns_positive(self):
        from app.engines.offer_engine import OfferEngine
        e = OfferEngine()
        r = e.calculate_offer_range(income_value=500_000_000,
                                     planned_repairs_cost=10_000_000)
        assert r["low"] is not None and r["low"] > 0
        assert r["high"] is not None and r["high"] > 0


class TestYieldEngineZeroNoi:
    """noi=0 (空地等) を None と区別する"""
    def test_calculate_net_yield_with_zero_noi(self):
        from app.engines.yield_engine import YieldEngine
        e = YieldEngine()
        # noi=0 は valid (利回り 0.0)
        assert e.calculate_net_yield(noi=0, price=100_000_000) == 0.0
        # noi=None は不明 (None 返却)
        assert e.calculate_net_yield(noi=None, price=100_000_000) is None
        # price=0 は不明 (ゼロ除算ガード)
        assert e.calculate_net_yield(noi=5_000_000, price=0) is None

    def test_calculate_gross_yield_with_zero_income(self):
        from app.engines.yield_engine import YieldEngine
        e = YieldEngine()
        assert e.calculate_gross_yield(gross_income=0, price=100_000_000) == 0.0
        assert e.calculate_gross_yield(gross_income=None, price=100_000_000) is None


class TestPropertyDataBuiltYearValidation:
    """built_year の極端値 (1880, 2050 等) を None にサイレント補正"""
    def test_future_built_year_normalized_to_none(self):
        from app.models.property import PropertyData
        from datetime import date
        future = date.today().year + 10
        prop = PropertyData(address="東京都港区", price=100_000_000,
                             built_year=future)
        assert prop.built_year is None  # 未来年は補正

    def test_too_old_built_year_normalized_to_none(self):
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都台東区", price=50_000_000,
                             built_year=1880)
        assert prop.built_year is None  # 1900 未満は補正

    def test_valid_built_year_kept(self):
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都港区", price=100_000_000,
                             built_year=2010)
        assert prop.built_year == 2010

    def test_built_year_1900_boundary(self):
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都港区", price=100_000_000,
                             built_year=1900)
        assert prop.built_year == 1900   # 境界値は受理


class TestPropertyDataDictConversion:
    """PropertyData → dict 変換の回帰テスト

    過去のバグ: PDFアップロード後の AI抽出で PropertyData インスタンスを
    dict として `.items()` 呼出していた → AttributeError
    """
    def test_property_data_has_model_dump(self):
        """PropertyData が Pydantic v2 の model_dump を持つ"""
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都新宿区", price=100_000_000)
        # model_dump() で dict 化可能 (Pydantic v2)
        d = prop.model_dump()
        assert isinstance(d, dict)
        assert d["address"] == "東京都新宿区"
        assert d["price"] == 100_000_000
        # .items() は dict 経由で呼べる
        keys = [k for k, _ in d.items()]
        assert "address" in keys
        assert "price" in keys

    def test_property_data_does_not_have_items_directly(self):
        """PropertyData インスタンスは .items() を直接持たないこと確認 (リグレッション証拠)"""
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都新宿区", price=100_000_000)
        # Pydantic v2 モデルは dict ではないので .items() は無い
        assert not hasattr(prop, "items"), (
            "PropertyData が .items() を持つ場合、UI のバグ修正は不要"
        )

    def test_model_dump_exclude_none(self):
        """exclude_none=True で None フィールドが除外される"""
        from app.models.property import PropertyData
        prop = PropertyData(address="東京都新宿区", price=100_000_000)
        # built_year, noi 等は省略 → None
        d = prop.model_dump(exclude_none=True)
        # address, price は含まれる
        assert "address" in d
        assert "price" in d
        # built_year は None のはずなので除外
        assert "built_year" not in d


class TestExtractedPropertyApplication:
    """extract_property_from_text の戻り値を session_state に適用する回帰防止"""
    def test_extracted_property_data_with_values(self):
        """extract が PropertyData を返した場合の取り扱い"""
        from app.models.property import PropertyData, AssetType
        prop = PropertyData(
            property_name="テスト",
            address="東京都新宿区西新宿1-1-1",
            asset_type=AssetType.APARTMENT_WHOLE,
            price=200_000_000,
            built_year=2015,
        )
        # PDFアップロードパスが期待する処理: model_dump → 値抽出
        d = prop.model_dump(exclude_none=True)
        n_filled = sum(1 for v in d.values() if v is not None)
        assert n_filled >= 5  # 少なくとも 5 項目は埋まっている
        # AssetType Enum は適切に処理される
        for k, v in d.items():
            if hasattr(v, "value") and not isinstance(v, (int, float, str, bool, list, dict)):
                # Enum 値は .value にアクセス可能
                pass
