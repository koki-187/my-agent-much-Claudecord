"""
実案件テスト: PDFから抽出した実データで分析実行
テストケース①: 練馬区中村北一丁目 (競売落札物件)
テストケース②: 東久留米市前沢一丁目 (個人所有クリーン)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService

svc = DealJudgementService()

# ===== テストケース①: 練馬区中村北一丁目 =====
# 合計地積: 287.94㎡(約87坪) 容積率400% 近隣商業 競売落札物件
prop1 = PropertyData(
    property_name="練馬区中村北一丁目 13番（複数筆）",
    asset_type=AssetType.LAND,
    address="東京都練馬区中村北",
    price=600_000_000,          # 売主希望6億（手取り5億）
    land_area_sqm=287.94,       # 実測: 13番9(111.96)+13番10(138.08)+13番12(13.61)+13番3(24.29)
    floor_area_ratio=4.0,       # 容積率400%
    building_coverage_ratio=0.80,
    zoning="近隣商業地域",
    road_access="千川通り（南側大通り）接道",
    seller_motivation=None,     # 競売落札者・温度感不明
    seller_reason="令和7年12月担保不動産競売により取得（大山泰・法子・優香）。前所有者は株式会社マテックマツザキ（債務超過競売）。",
    broker_chain_count=2,
    built_year=1969,            # 旧建物: RC造5階建て昭和44年新築（旧耐震）
    structure="RC",
    legal_notes="旧耐震建物存在（昭和44年RC造5階・木鉄2階）。解体費必要。競売落札者が売主。防火地域・高さ制限35m第3種。",
)

report1 = svc.analyze(prop1)
out1 = "test_case1_nerima_real.md"
with open(out1, "w", encoding="utf-8") as f:
    f.write("# 案件調査レポート：練馬区中村北一丁目（実データ）\n\n")
    f.write(report1)
print(f"[OK] 練馬区レポート出力: {out1}")

# ===== テストケース②: 東久留米市前沢一丁目 =====
# 地積: 505.00㎡(約152.8坪) 容積率200% 第二種中高層 個人所有クリーン
prop2 = PropertyData(
    property_name="東久留米市前沢一丁目 881番7",
    asset_type=AssetType.LAND,
    address="東京都東久留米市前沢",
    price=200_000_000,          # 想定売値: 2億（業者メッセージで2億から検討余地あり）
    land_area_sqm=505.0,        # 実測地積
    floor_area_ratio=2.0,       # 容積率200%
    building_coverage_ratio=0.60,
    zoning="第二種中高層住居専用地域",
    road_access="公道（前沢通り東側接道・幹線道路）",
    seller_reason="令和5年2月27日売買取得（転売目的の可能性）",
    seller_motivation=None,     # 温度感未確認
    broker_chain_count=2,
)

report2 = svc.analyze(prop2)
out2 = "test_case2_higashikurume_real.md"
with open(out2, "w", encoding="utf-8") as f:
    f.write("# 案件調査レポート：東久留米市前沢一丁目（実データ）\n\n")
    f.write(report2)
print(f"[OK] 東久留米レポート出力: {out2}")

print("\n===== 分析サマリー =====")
# サマリー表示用の再実行
for name, prop in [("練馬区", prop1), ("東久留米", prop2)]:
    svc2 = DealJudgementService()
    # devland engineを直接叩いてサマリーを確認
    dl = svc2.developer_land_engine.analyze(
        address=prop.address,
        price=prop.price,
        land_area_sqm=prop.land_area_sqm,
        floor_area_ratio=prop.floor_area_ratio,
        building_coverage_ratio=prop.building_coverage_ratio,
        zoning=prop.zoning,
    )
    tsubo = (prop.land_area_sqm * 0.3025) if prop.land_area_sqm else None
    sale_per_tsubo = int(prop.price / tsubo) if tsubo else None
    print(f"\n[{name}]")
    print(f"  売値: {prop.price:,}円")
    print(f"  地積: {prop.land_area_sqm}㎡ ({tsubo:.1f}坪)" if tsubo else f"  地積: 未入力")
    print(f"  売値坪単価: {sale_per_tsubo:,}円/坪" if sale_per_tsubo else "  売値坪単価: 算出不可")
    print(f"  デベ上限坪単価: {dl.dev_land_price_per_tsubo:,}円/坪" if dl.dev_land_price_per_tsubo else "  デベ上限坪単価: 算出不可")
    print(f"  デベ最大買値: {dl.dev_max_land_price:,}円" if dl.dev_max_land_price else "  デベ最大買値: 算出不可")
    print(f"  価格評価: {dl.price_evaluation}")
    print(f"  推奨判断: {dl.recommendation}")
    if sale_per_tsubo and dl.dev_land_price_per_tsubo:
        ratio = sale_per_tsubo / dl.dev_land_price_per_tsubo
        print(f"  売値/デベ上限比: {ratio:.1f}倍")
