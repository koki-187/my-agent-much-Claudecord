import pytest
from app.engines.risk_engine import RiskEngine
from app.models.property import PropertyData


@pytest.fixture
def engine() -> RiskEngine:
    return RiskEngine()


def _make_property(**kwargs) -> PropertyData:
    defaults = {"address": "東京都新宿区", "price": 100_000_000}
    defaults.update(kwargs)
    return PropertyData(**defaults)


def test_no_risks_clean_property(engine: RiskEngine) -> None:
    prop = _make_property(
        seller_reason="相続",
        broker_chain_count=1,
        road_access="公道",
        occupancy_rate=0.95,
        built_year=2000,
        document_freshness_days=10,
    )
    risks = engine.detect_risks(prop)
    assert len(risks) == 0


def test_broker_chain_risk(engine: RiskEngine) -> None:
    prop = _make_property(broker_chain_count=3, seller_reason="相続")
    risks = engine.detect_risks(prop)
    types = [r["type"] for r in risks]
    assert "商流リスク" in types


def test_road_access_critical(engine: RiskEngine) -> None:
    prop = _make_property(road_access="再建築不可", seller_reason="相続")
    risks = engine.detect_risks(prop)
    types = [r["type"] for r in risks]
    assert "接道リスク" in types
    critical = next(r for r in risks if r["type"] == "接道リスク")
    assert critical["level"] == "critical"


def test_old_seismic_risk(engine: RiskEngine) -> None:
    prop = _make_property(built_year=1975, seller_reason="相続")
    risks = engine.detect_risks(prop)
    types = [r["type"] for r in risks]
    assert "旧耐震リスク" in types


def test_seller_reason_unknown(engine: RiskEngine) -> None:
    prop = _make_property(seller_reason=None)
    risks = engine.detect_risks(prop)
    types = [r["type"] for r in risks]
    assert "売却理由不明" in types


def test_score_risk_no_risks(engine: RiskEngine) -> None:
    assert engine.score_risk([]) == 90


def test_score_risk_critical(engine: RiskEngine) -> None:
    risks = [{"type": "接道リスク", "level": "critical", "message": "test"}]
    assert engine.score_risk(risks) == 55


def test_score_risk_floor_at_zero(engine: RiskEngine) -> None:
    risks = [{"type": f"risk{i}", "level": "critical", "message": "x"} for i in range(10)]
    assert engine.score_risk(risks) == 0
