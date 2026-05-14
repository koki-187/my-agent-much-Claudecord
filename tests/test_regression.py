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
