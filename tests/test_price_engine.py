import pytest
from app.engines.price_engine import PriceEngine


@pytest.fixture
def engine() -> PriceEngine:
    return PriceEngine()


def test_calculate_income_value_normal(engine: PriceEngine) -> None:
    result = engine.calculate_income_value(noi=7_200_000, target_yield=0.075)
    assert result == 96_000_000


def test_calculate_income_value_none_noi(engine: PriceEngine) -> None:
    assert engine.calculate_income_value(noi=None, target_yield=0.075) is None


def test_calculate_income_value_zero_yield(engine: PriceEngine) -> None:
    assert engine.calculate_income_value(noi=7_200_000, target_yield=0.0) is None


def test_judge_price_waribiki(engine: PriceEngine) -> None:
    result = engine.judge_price(price=85_000_000, income_value=100_000_000)
    assert result["status"] == "割安"
    assert result["ratio"] == 0.85


def test_judge_price_tekisei(engine: PriceEngine) -> None:
    result = engine.judge_price(price=100_000_000, income_value=100_000_000)
    assert result["status"] == "適正"


def test_judge_price_yaya_takai(engine: PriceEngine) -> None:
    result = engine.judge_price(price=110_000_000, income_value=100_000_000)
    assert result["status"] == "やや高い"


def test_judge_price_taka_sugiru(engine: PriceEngine) -> None:
    result = engine.judge_price(price=130_000_000, income_value=100_000_000)
    assert result["status"] == "高すぎる"


def test_judge_price_no_income_value(engine: PriceEngine) -> None:
    result = engine.judge_price(price=100_000_000, income_value=None)
    assert result["status"] == "判定不可"
    assert result["ratio"] is None
