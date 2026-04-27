import pytest
from app.engines.scoring_engine import ScoringEngine
from app.models.property import PropertyData


@pytest.fixture
def engine() -> ScoringEngine:
    return ScoringEngine()


def _make_property(**kwargs) -> PropertyData:
    defaults = {"address": "東京都新宿区", "price": 100_000_000}
    defaults.update(kwargs)
    return PropertyData(**defaults)


def test_price_score_waribiki(engine: ScoringEngine) -> None:
    assert engine.price_score("割安") == 95


def test_price_score_takai(engine: ScoringEngine) -> None:
    assert engine.price_score("高すぎる") == 25


def test_price_score_unknown(engine: ScoringEngine) -> None:
    assert engine.price_score("不明なステータス") == 40


def test_broker_score_long_chain(engine: ScoringEngine) -> None:
    score = engine.broker_score(broker_chain_count=4, seller_motivation=None)
    assert score <= 45


def test_broker_score_high_motivation(engine: ScoringEngine) -> None:
    score = engine.broker_score(broker_chain_count=1, seller_motivation="売主温度感が高い")
    assert score >= 80


def test_liquidity_score_tokyo(engine: ScoringEngine) -> None:
    prop = _make_property(address="東京都渋谷区", occupancy_rate=0.95, built_year=2010)
    assert engine.liquidity_score(prop) >= 80


def test_liquidity_score_old_building(engine: ScoringEngine) -> None:
    prop = _make_property(address="地方都市", built_year=1970)
    assert engine.liquidity_score(prop) < 70


def test_total_score_rank_s(engine: ScoringEngine) -> None:
    result = engine.total_score(95, 95, 90, 90, 90, 90)
    assert result["rank"] == "S"
    assert result["total_score"] >= 85


def test_total_score_rank_d(engine: ScoringEngine) -> None:
    result = engine.total_score(25, 25, 25, 10, 0, 0)
    assert result["rank"] == "D"


def test_total_score_rank_b(engine: ScoringEngine) -> None:
    result = engine.total_score(55, 65, 70, 70, 50, 55)
    assert result["rank"] in ["A", "B"]
