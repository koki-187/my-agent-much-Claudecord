# test_pro_buyers.py
# 不動産プロ仕入れ担当5名テスト
import sys, os
sys.path.insert(0, '.')

from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService
from app.engines.finance_engine import FinanceEngine
from app.engines.exit_strategy_engine import ExitStrategyEngine
from app.engines.buyer_matching_engine import BuyerMatchingEngine
from app.engines.land_plan_engine import LandPlanEngine
from app.engines.repair_cost_engine import RepairCostEngine

svc = DealJudgementService()
fe = FinanceEngine()
ee = ExitStrategyEngine()
bm = BuyerMatchingEngine()
lpe = LandPlanEngine()
re_eng = RepairCostEngine()

results = {}

print("=" * 70)
print("My Agent Much (MAM) プロ仕入れ担当 5名テスト")
print("=" * 70)

# ===========================================================================
# テスター1: デベロッパー用地仕入れ担当（マンション用地）
# ===========================================================================
print("\n【テスター1: デベロッパー用地仕入れ (鈴木部長)】")
print("案件: 渋谷区松濤・開発用地・50坪・容積率400%・5億円")

prop1 = PropertyData(
    address="東京都渋谷区松濤1-20-1",
    price=500_000_000,
    asset_type=AssetType.LAND,
    land_area_sqm=165.0,
    floor_area_ratio=4.0,
    building_coverage_ratio=0.6,
    road_frontage_m=6.0,
    walk_minutes_to_station=8,
    zoning="第一種住居地域",
)

risks1 = svc.risk_engine.detect_risks(prop1)
score1 = svc.scoring_engine.total_score(60, 40, 80, 100, svc.risk_engine.score_risk(risks1), 60, asset_type=prop1.asset_type)

lpa1 = lpe.analyze(
    address=prop1.address, price=prop1.price,
    land_area_sqm=prop1.land_area_sqm, far=prop1.floor_area_ratio*100,
    bcr=prop1.building_coverage_ratio*100, road_width_m=prop1.road_frontage_m,
    zoning=prop1.zoning, walk_minutes=prop1.walk_minutes_to_station
)
bm1 = bm.match(
    address=prop1.address, price=prop1.price,
    land_area_sqm=prop1.land_area_sqm, walk_minutes=prop1.walk_minutes_to_station,
    floor_area_ratio=prop1.floor_area_ratio, building_coverage_ratio=prop1.building_coverage_ratio,
    road_frontage_m=prop1.road_frontage_m, zoning=prop1.zoning, asset_type_str="土地"
)

t1 = {
    "name": "デベ用地仕入れ",
    "score": score1["total_score"],
    "rank": score1["rank"],
    "judgement": score1["judgement"],
    "risks": len(risks1),
    "best_plan": lpa1.best_plan,
    "top_scenarios": [(s.plan_name, s.score, s.total_revenue//10000, s.max_land_price//10000) for s in sorted(lpa1.scenarios, key=lambda x: x.score, reverse=True)[:3] if s.is_feasible],
    "matched_buyers": [(r.buyer_short, r.match_score, r.verdict) for r in bm1 if r.match_score >= 50],
}
print(f"  スコア: {t1['score']} / ランク: {t1['rank']} / {t1['judgement']}")
print(f"  リスク: {t1['risks']}件")
print(f"  ベストプラン: {t1['best_plan']}")
for pname, pscore, rev, maxp in t1['top_scenarios']:
    print(f"    [{pname}] score={pscore} 売上{rev:,}万 デベ買値{maxp:,}万")
print(f"  マッチバイヤー: {t1['matched_buyers']}")
results["tester1"] = t1

# ===========================================================================
# テスター2: ホテル用地仕入れ担当
# ===========================================================================
print("\n【テスター2: ホテル用地仕入れ担当 (田中主任)】")
print("案件: 台東区浅草・80坪・容積率500%商業地域・8億円")

prop2 = PropertyData(
    address="東京都台東区浅草1-30-1",
    price=800_000_000,
    asset_type=AssetType.LAND,
    land_area_sqm=264.0,
    floor_area_ratio=5.0,
    building_coverage_ratio=0.8,
    road_frontage_m=8.0,
    walk_minutes_to_station=5,
    zoning="商業地域",
)

risks2 = svc.risk_engine.detect_risks(prop2)
score2 = svc.scoring_engine.total_score(55, 40, 60, 80, svc.risk_engine.score_risk(risks2), 70, asset_type=prop2.asset_type)

lpa2 = lpe.analyze(
    address=prop2.address, price=prop2.price,
    land_area_sqm=prop2.land_area_sqm, far=prop2.floor_area_ratio*100,
    bcr=prop2.building_coverage_ratio*100, road_width_m=prop2.road_frontage_m,
    zoning=prop2.zoning, walk_minutes=prop2.walk_minutes_to_station
)

hotel_s = next((s for s in lpa2.scenarios if "ホテル" in s.plan_name), None)
price_ratio = prop2.price / hotel_s.max_land_price if hotel_s and hotel_s.max_land_price > 0 else 99

bm2 = bm.match(
    address=prop2.address, price=prop2.price,
    land_area_sqm=prop2.land_area_sqm, walk_minutes=prop2.walk_minutes_to_station,
    floor_area_ratio=prop2.floor_area_ratio, building_coverage_ratio=prop2.building_coverage_ratio,
    road_frontage_m=prop2.road_frontage_m, zoning=prop2.zoning, asset_type_str="土地"
)

t2 = {
    "name": "ホテル用地仕入れ",
    "score": score2["total_score"],
    "rank": score2["rank"],
    "judgement": score2["judgement"],
    "risks": len(risks2),
    "best_plan": lpa2.best_plan,
    "hotel_score": hotel_s.score if hotel_s else 0,
    "hotel_revenue": hotel_s.total_revenue//10000 if hotel_s else 0,
    "hotel_max_price": hotel_s.max_land_price//10000 if hotel_s else 0,
    "price_ratio": price_ratio,
    "matched_buyers": [(r.buyer_short, r.match_score) for r in bm2 if r.match_score >= 50],
}
print(f"  スコア: {t2['score']} / ランク: {t2['rank']} / {t2['judgement']}")
print(f"  ベストプラン: {t2['best_plan']}")
print(f"  [ホテルプラン] score={t2['hotel_score']} 売上{t2['hotel_revenue']:,}万 デベ買値{t2['hotel_max_price']:,}万")
print(f"  価格乖離: 売値{prop2.price//10000:,}万 / デベ買値{t2['hotel_max_price']:,}万 = {price_ratio:.2f}倍")
verdict2 = "成立可能" if price_ratio <= 1.1 else "指値交渉余地あり" if price_ratio <= 1.3 else "現状では厳しい"
print(f"  仕入れ判断: {verdict2}")
print(f"  マッチバイヤー: {t2['matched_buyers']}")
results["tester2"] = t2

# ===========================================================================
# テスター3: アパート（木造）仕入れ担当
# ===========================================================================
print("\n【テスター3: アパート仕入れ担当 (佐藤係長)】")
print("案件: 世田谷区経堂・木造アパート一棟・利回り7%・1.5億円")

prop3 = PropertyData(
    address="東京都世田谷区経堂3-5-10",
    price=150_000_000,
    asset_type=AssetType.APARTMENT_WOOD,
    noi=10_500_000,
    gross_yield=0.07,
    land_area_sqm=180.0,
    building_area_sqm=240.0,
    built_year=2005,
    walk_minutes_to_station=7,
    floor_area_ratio=0.6,
    building_coverage_ratio=0.4,
    broker_chain_count=2,
    occupancy_rate=0.95,
    seller_motivation="転勤",
)

ak3 = fe.get_asset_type_key(prop3.asset_type.value)
fr3 = fe.simulate(prop3.price, prop3.noi, ak3)
er3 = ee.evaluate(prop3.price, prop3.noi, ak3, prop3.address, prop3.built_year)
rr3 = re_eng.estimate(ak3, prop3.building_area_sqm, prop3.built_year, None, 0)
risks3 = svc.risk_engine.detect_risks(prop3)

income3 = svc.price_engine.calculate_income_value(prop3.noi, 0.055)
price_r3 = svc.price_engine.judge_price(prop3.price, income3)
score3 = svc.scoring_engine.total_score(
    svc.scoring_engine.price_score(price_r3["status"]),
    svc.yield_engine.score_yield(prop3.gross_yield, 0.055),
    svc.scoring_engine.liquidity_score(prop3), 50,
    svc.risk_engine.score_risk(risks3),
    svc.scoring_engine.broker_score(prop3.broker_chain_count, prop3.seller_motivation),
    asset_type=prop3.asset_type
)
bm3 = bm.match(
    address=prop3.address, price=prop3.price,
    land_area_sqm=prop3.land_area_sqm, walk_minutes=prop3.walk_minutes_to_station,
    gross_yield=prop3.gross_yield, asset_type_str="一棟アパート（木造）"
)

t3 = {
    "name": "アパート仕入れ",
    "score": score3["total_score"],
    "rank": score3["rank"],
    "judgement": score3["judgement"],
    "dscr_base": fr3.dscr_base,
    "dscr_stress": fr3.dscr_stress,
    "feasibility": fr3.feasibility,
    "exit_best": er3.best_scenario,
    "irr_10yr": next((s.irr_approx for s in er3.scenarios if "10" in s.name), None),
    "repair_5yr": rr3.five_year_cost,
    "risks": [(r["type"], r["level"]) for r in risks3[:3]],
    "price_status": price_r3["status"],
    "matched_buyers": [(r.buyer_short, r.match_score, r.verdict) for r in bm3 if r.match_score >= 50],
}
print(f"  スコア: {t3['score']} / ランク: {t3['rank']} / {t3['judgement']}")
print(f"  DSCR: {t3['dscr_base']:.2f}(通常) / {t3['dscr_stress']:.2f}(ストレス) → {t3['feasibility']}")
print(f"  価格評価: {t3['price_status']}")
print(f"  出口: {t3['exit_best']}, 10年IRR: {t3['irr_10yr']:.1%}" if t3['irr_10yr'] else f"  出口: {t3['exit_best']}")
print(f"  5年修繕費積算: {t3['repair_5yr']:,}円")
print(f"  リスク: {t3['risks']}")
print(f"  マッチバイヤー: {t3['matched_buyers']}")
results["tester3"] = t3

# ===========================================================================
# テスター4: 一棟RCマンション仕入れ担当
# ===========================================================================
print("\n【テスター4: 一棟RCマンション仕入れ担当 (中村課長)】")
print("案件: 目黒区中目黒・RC一棟マンション・利回り4.2%・3億円")

prop4 = PropertyData(
    address="東京都目黒区中目黒4-1-5",
    price=300_000_000,
    asset_type=AssetType.APARTMENT_WHOLE,
    noi=12_600_000,
    gross_yield=0.042,
    land_area_sqm=250.0,
    building_area_sqm=600.0,
    built_year=2015,
    walk_minutes_to_station=4,
    floor_area_ratio=2.4,
    building_coverage_ratio=0.6,
    broker_chain_count=1,
    occupancy_rate=0.98,
    seller_motivation="相続",
)

ak4 = fe.get_asset_type_key(prop4.asset_type.value)
fr4 = fe.simulate(prop4.price, prop4.noi, ak4)
er4 = ee.evaluate(prop4.price, prop4.noi, ak4, prop4.address, prop4.built_year)
rr4 = re_eng.estimate(ak4, prop4.building_area_sqm, prop4.built_year, None, 0)
risks4 = svc.risk_engine.detect_risks(prop4)

income4 = svc.price_engine.calculate_income_value(prop4.noi, 0.035)
price_r4 = svc.price_engine.judge_price(prop4.price, income4)
score4 = svc.scoring_engine.total_score(
    svc.scoring_engine.price_score(price_r4["status"]),
    svc.yield_engine.score_yield(prop4.gross_yield, 0.035),
    svc.scoring_engine.liquidity_score(prop4), 40,
    svc.risk_engine.score_risk(risks4),
    svc.scoring_engine.broker_score(prop4.broker_chain_count, prop4.seller_motivation),
    asset_type=prop4.asset_type
)
bm4 = bm.match(
    address=prop4.address, price=prop4.price,
    land_area_sqm=prop4.land_area_sqm, walk_minutes=prop4.walk_minutes_to_station,
    gross_yield=prop4.gross_yield, asset_type_str="一棟マンション（RC）"
)

irr_10yr4 = next((s.irr_approx for s in er4.scenarios if "10" in s.name), None)
t4 = {
    "name": "一棟RC仕入れ",
    "score": score4["total_score"],
    "rank": score4["rank"],
    "judgement": score4["judgement"],
    "dscr_base": fr4.dscr_base,
    "dscr_stress": fr4.dscr_stress,
    "feasibility": fr4.feasibility,
    "price_status": price_r4["status"],
    "irr_10yr": irr_10yr4,
    "repair_total": rr4.total_lifecycle_cost,
    "risks": [(r["type"], r["level"]) for r in risks4[:3]],
    "matched_buyers": [(r.buyer_short, r.match_score, r.verdict) for r in bm4 if r.match_score >= 50],
}
print(f"  スコア: {t4['score']} / ランク: {t4['rank']} / {t4['judgement']}")
print(f"  DSCR: {t4['dscr_base']:.2f}(通常) / {t4['dscr_stress']:.2f}(ストレス) → {t4['feasibility']}")
print(f"  価格評価: {t4['price_status']}")
if t4['irr_10yr']:
    print(f"  10年保有IRR: {t4['irr_10yr']:.1%}")
print(f"  ライフサイクル修繕費: {t4['repair_total']:,}円")
print(f"  リスク: {t4['risks']}")
print(f"  マッチバイヤー: {t4['matched_buyers']}")
results["tester4"] = t4

# ===========================================================================
# テスター5: 区分マンション仕入れ担当
# ===========================================================================
print("\n【テスター5: 区分マンション仕入れ担当 (高橋担当)】")
print("案件: 新宿区西新宿・区分1R・利回り5.8%・3,800万円")

prop5 = PropertyData(
    address="東京都新宿区西新宿6-5-1",
    price=38_000_000,
    asset_type=AssetType.UNIT,
    noi=2_204_000,
    gross_yield=0.058,
    building_area_sqm=22.5,
    built_year=2018,
    walk_minutes_to_station=6,
    broker_chain_count=1,
    occupancy_rate=1.0,
)

ak5 = fe.get_asset_type_key(prop5.asset_type.value)
fr5 = fe.simulate(prop5.price, prop5.noi, ak5)
er5 = ee.evaluate(prop5.price, prop5.noi, ak5, prop5.address, prop5.built_year)
risks5 = svc.risk_engine.detect_risks(prop5)

income5 = svc.price_engine.calculate_income_value(prop5.noi, 0.045)
price_r5 = svc.price_engine.judge_price(prop5.price, income5)
score5 = svc.scoring_engine.total_score(
    svc.scoring_engine.price_score(price_r5["status"]),
    svc.yield_engine.score_yield(prop5.gross_yield, 0.045),
    svc.scoring_engine.liquidity_score(prop5), 20,
    svc.risk_engine.score_risk(risks5),
    svc.scoring_engine.broker_score(prop5.broker_chain_count, None),
    asset_type=prop5.asset_type
)

irr_vals5 = [f"{s.name}: {s.irr_approx:.1%}" for s in er5.scenarios]
t5 = {
    "name": "区分マンション仕入れ",
    "score": score5["total_score"],
    "rank": score5["rank"],
    "judgement": score5["judgement"],
    "dscr_base": fr5.dscr_base,
    "dscr_stress": fr5.dscr_stress,
    "feasibility": fr5.feasibility,
    "price_status": price_r5["status"],
    "irr_scenarios": irr_vals5,
    "risks": len(risks5),
}
print(f"  スコア: {t5['score']} / ランク: {t5['rank']} / {t5['judgement']}")
print(f"  DSCR: {t5['dscr_base']:.2f}(通常) / {t5['dscr_stress']:.2f}(ストレス) → {t5['feasibility']}")
print(f"  価格評価: {t5['price_status']}")
print(f"  IRRシミュレーション: {t5['irr_scenarios']}")
print(f"  リスク件数: {t5['risks']}")
results["tester5"] = t5

# ===========================================================================
# サマリー
# ===========================================================================
print("\n" + "=" * 70)
print("テスト結果サマリー")
print("=" * 70)
testers = [
    ("テスター1 デベ用地", results["tester1"]),
    ("テスター2 ホテル用地", results["tester2"]),
    ("テスター3 木造アパート", results["tester3"]),
    ("テスター4 一棟RC", results["tester4"]),
    ("テスター5 区分1R", results["tester5"]),
]
for label, r in testers:
    dscr = f"DSCR={r.get('dscr_base','N/A')}" if 'dscr_base' in r else "用地案件"
    print(f"  {label}: score={r['score']} rank={r['rank']} {r['judgement']} | {dscr}")

# エラー・異常値チェック
print("\nエラー・異常値チェック:")
error_count = 0
for label, r in testers:
    if r["score"] < 0 or r["score"] > 100:
        print(f"  ERROR: {label} score={r['score']} out of range")
        error_count += 1
    if r["rank"] not in ["S", "A", "B", "C", "D"]:
        print(f"  ERROR: {label} rank={r['rank']} invalid")
        error_count += 1
    if 'dscr_base' in r and r['dscr_base'] is not None:
        if r['dscr_base'] < 0 or r['dscr_base'] > 5:
            print(f"  WARN: {label} dscr_base={r['dscr_base']} seems unusual")
            error_count += 1

if error_count == 0:
    print("  全項目正常 - エラーなし")

print("\n全テスト完了")
