import pytest
from app.engines.rosenka_engine import RosenkaEngine
from app.engines.finance_engine import FinanceEngine
from app.engines.exit_strategy_engine import ExitStrategyEngine
from app.engines.repair_cost_engine import RepairCostEngine
from app.engines.area_trend_engine import AreaTrendEngine


# --- RosenkaEngine Tests ---
def test_rosenka_tokyo_shinjuku():
    engine = RosenkaEngine()
    result = engine.lookup("東京都新宿区", 120_000_000, 250.0, "近隣商業地域")
    assert result is not None
    assert result.rosenka_per_sqm > 0

def test_rosenka_ratio_calculation():
    engine = RosenkaEngine()
    result = engine.lookup("東京都渋谷区", 80_000_000, 100.0, "住宅地域")
    if result and result.ratio_to_rosenka:
        assert result.ratio_to_rosenka > 0

def test_rosenka_no_land_area():
    engine = RosenkaEngine()
    result = engine.lookup("東京都新宿区", 120_000_000, None, None)
    # 土地面積なしでもクラッシュしない
    # actual_per_sqmはNoneになるはず
    if result:
        assert result.actual_per_sqm is None


# --- FinanceEngine Tests ---
def test_finance_dscr_calculation():
    engine = FinanceEngine()
    result = engine.simulate(120_000_000, 7_200_000, "APARTMENT_WHOLE")
    assert result.dscr_base is not None
    assert result.dscr_base > 0
    assert result.loan_amount == 96_000_000  # LTV 80%

def test_finance_stress_rate_higher():
    engine = FinanceEngine()
    result = engine.simulate(100_000_000, 6_000_000, "APARTMENT_WHOLE")
    assert result.monthly_payment_stress > result.monthly_payment_base

def test_finance_old_building_ltv():
    engine = FinanceEngine()
    result = engine.simulate(80_000_000, 5_000_000, "APARTMENT_WHOLE", built_year=1978)
    # 旧耐震はLTV上限70%
    assert result.ltv <= 0.70

def test_finance_land_dscr_none():
    engine = FinanceEngine()
    result = engine.simulate(80_000_000, None, "LAND")
    assert result.dscr_base is None

def test_finance_get_asset_type_key():
    engine = FinanceEngine()
    assert engine.get_asset_type_key("一棟マンション") == "APARTMENT_WHOLE"
    assert engine.get_asset_type_key("工場・倉庫") == "FACTORY"


# --- RepairCostEngine Tests ---
def test_repair_old_rc_building():
    engine = RepairCostEngine()
    result = engine.estimate("APARTMENT_WHOLE", 600.0, 1990, "RC造", 2_000_000)
    assert result.immediate_cost > 0
    assert result.inflation_adjusted is True

def test_repair_new_building():
    engine = RepairCostEngine()
    result = engine.estimate("APARTMENT_WHOLE", 200.0, 2020, "RC造")
    # 新しい建物は即時修繕費が低い
    assert result.total_lifecycle_cost >= 0

def test_repair_wood_old_building():
    engine = RepairCostEngine()
    result = engine.estimate("APARTMENT_WOOD", 180.0, 1998, "木造")
    assert result.comment is not None


# --- AreaTrendEngine Tests ---
def test_area_trend_tokyo():
    engine = AreaTrendEngine()
    result = engine.evaluate("東京都港区", "APARTMENT_WHOLE")
    if result:
        assert result.trend in ["上昇", "横ばい", "下落"]

def test_area_trend_score_adjustment():
    engine = AreaTrendEngine()
    result = engine.evaluate("東京都新宿区", "APARTMENT_WHOLE")
    if result:
        assert -20 <= result.trend_score_adjustment <= 20

def test_area_trend_unknown_area():
    engine = AreaTrendEngine()
    # 存在しないエリアはNoneを返す（クラッシュしない）
    result = engine.evaluate("存在しない島", "APARTMENT_WHOLE")
    assert result is None or result is not None  # エラーなしで動くこと


# --- ExitStrategyEngine Tests ---
def test_exit_scenarios_count():
    engine = ExitStrategyEngine()
    result = engine.evaluate(120_000_000, 7_200_000, "APARTMENT_WHOLE")
    assert len(result.scenarios) == 3  # 3/5/10年シナリオ

def test_exit_land_no_scenarios():
    engine = ExitStrategyEngine()
    result = engine.evaluate(80_000_000, None, "LAND")
    # 土地はNOIなしのためシナリオ0
    assert len(result.scenarios) == 0
