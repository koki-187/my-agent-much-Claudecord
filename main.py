import argparse
import json
import sys
import os
from app.models.property import PropertyData, AssetType
from app.services.deal_judgement_service import DealJudgementService
from app.services.storage_service import StorageService
from app.services.comparison_service import ComparisonService


SAMPLE_PROPERTIES = {
    "マンション": PropertyData(
        property_name="サンプル収益マンション（東京）",
        asset_type=AssetType.APARTMENT_WHOLE,
        address="東京都新宿区",
        price=120_000_000,
        land_area_sqm=250.0, building_area_sqm=600.0,
        structure="RC造", built_year=1995,
        gross_income=10_000_000, actual_income=9_200_000, noi=7_200_000,
        occupancy_rate=0.92, gross_yield=0.083,
        zoning="近隣商業地域", building_coverage_ratio=0.80, floor_area_ratio=3.00,
        road_access="公道 接道あり", current_status="賃貸中",
        seller_motivation="不明", broker_chain_count=3, document_freshness_days=75,
        planned_repairs_cost=2_000_000, notes="商流が長く、売主温度感は未確認"
    ),
    "アパート": PropertyData(
        property_name="木造アパート（大阪）",
        asset_type=AssetType.APARTMENT_WOOD,
        address="大阪府大阪市",
        price=50_000_000,
        land_area_sqm=100.0, building_area_sqm=180.0,
        structure="木造", built_year=2005,
        gross_income=4_800_000, actual_income=4_800_000, noi=3_800_000,
        occupancy_rate=1.0, gross_yield=0.096,
        zoning="第一種住居地域", road_access="公道 4m",
        current_status="賃貸中", seller_reason="相続",
        seller_motivation="高い", broker_chain_count=1, document_freshness_days=15,
        planned_repairs_cost=500_000
    ),
    "区分": PropertyData(
        property_name="区分マンション（渋谷）",
        asset_type=AssetType.UNIT,
        address="東京都渋谷区",
        price=25_000_000,
        building_area_sqm=35.0, structure="RC造", built_year=2010,
        gross_income=1_440_000, noi=1_080_000,
        occupancy_rate=1.0, gross_yield=0.0576,
        zoning="第一種住居地域", road_access="公道",
        current_status="賃貸中", seller_reason="転勤",
        seller_motivation="高い", broker_chain_count=1,
        management_fee_monthly=18000, repair_reserve_monthly=8000,
    ),
    "土地": PropertyData(
        property_name="更地（横浜）",
        asset_type=AssetType.LAND,
        address="神奈川県横浜市",
        price=80_000_000,
        land_area_sqm=200.0,
        zoning="第一種住居地域", building_coverage_ratio=0.60, floor_area_ratio=2.00,
        road_access="公道 6m",
        seller_reason="相続", seller_motivation="高い",
        broker_chain_count=1, document_freshness_days=30,
    ),
    "商業": PropertyData(
        property_name="路面店舗（名古屋）",
        asset_type=AssetType.COMMERCIAL,
        address="愛知県名古屋市",
        price=90_000_000,
        land_area_sqm=150.0, building_area_sqm=200.0,
        structure="鉄骨造", built_year=2000,
        gross_income=6_000_000, noi=4_800_000,
        occupancy_rate=1.0, gross_yield=0.0667,
        zoning="近隣商業地域", road_access="幹線道路沿い",
        current_status="賃貸中", tenant_name="チェーン飲食店A",
        lease_expiry="2026-03-31", lease_type="普通借家",
        seller_motivation="不明", broker_chain_count=2,
    ),
    "工場": PropertyData(
        property_name="倉庫兼工場（埼玉）",
        asset_type=AssetType.FACTORY,
        address="埼玉県川口市",
        price=60_000_000,
        land_area_sqm=500.0, building_area_sqm=400.0,
        structure="鉄骨造", built_year=1990,
        gross_income=4_200_000, noi=3_500_000,
        occupancy_rate=1.0,
        zoning="工業地域", road_access="公道 8m",
        current_status="賃貸中", truck_access="大型トラック可",
        seller_reason="事業縮小", seller_motivation="高い",
        broker_chain_count=1, planned_repairs_cost=3_000_000,
    ),
}


def cmd_analyze(args):
    if args.json:
        with open(args.json, encoding="utf-8") as f:
            data = json.load(f)
        prop = PropertyData(**data)
    elif args.sample:
        prop = SAMPLE_PROPERTIES.get(args.sample)
        if not prop:
            print(f"サンプル不明: {args.sample}. 選択肢: {list(SAMPLE_PROPERTIES.keys())}")
            sys.exit(1)
    else:
        prop = SAMPLE_PROPERTIES["マンション"]

    service = DealJudgementService()
    report = service.analyze(prop)

    output_file = args.output or "anken_report.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    if args.save:
        import re
        m = re.search(r"総合スコア.*\*\*(\d+\.\d+)点\*\*", report)
        score = float(m.group(1)) if m else 0.0
        m2 = re.search(r"ランク.*\*\*([SABCD])\*\*", report)
        rank = m2.group(1) if m2 else "?"
        storage = StorageService()
        path = storage.save_deal(prop, report, score, rank)
        print(f"[保存] {path}")

    print(report)
    print(f"\n[OK] {output_file} を出力しました。")

    if getattr(args, 'pdf', False):
        from app.services.pdf_service import PDFService
        pdf_service = PDFService()
        pdf_file = output_file.replace(".md", ".pdf")
        result_path = pdf_service.generate(report, pdf_file, prop.property_name or "案件")
        print(f"[PDF] {result_path}")


def cmd_extract(args):
    from app.services.llm_service import LLMService
    llm = LLMService()
    if not llm.is_available():
        print("[エラー] ANTHROPIC_API_KEY が設定されていません。")
        print("  export ANTHROPIC_API_KEY=your-key")
        sys.exit(1)

    text = args.text
    if os.path.exists(text):
        with open(text, encoding="utf-8") as f:
            text = f.read()

    print("AIが物件情報を解析中...")
    prop = llm.extract_property_from_text(text)
    if not prop:
        print("[エラー] テキストからの抽出に失敗しました。")
        sys.exit(1)

    print(f"[抽出成功] {prop.asset_type.value}: {prop.property_name or prop.address}")

    service = DealJudgementService()
    report = service.analyze(prop)

    output_file = args.output or "extracted_report.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] {output_file} を出力しました。")

    if getattr(args, 'pdf', False):
        from app.services.pdf_service import PDFService
        pdf_path = PDFService().generate(report, output_file.replace(".md", ".pdf"), prop.property_name or "案件")
        print(f"[PDF] {pdf_path}")


def cmd_batch(args):
    with open(args.json, encoding="utf-8") as f:
        items = json.load(f)
    service = DealJudgementService()
    for i, data in enumerate(items):
        prop = PropertyData(**data)
        report = service.analyze(prop)
        name = prop.property_name or f"deal_{i+1}"
        outfile = f"{name}_report.md"
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[{i+1}/{len(items)}] {name} → {outfile}")
    print(f"\n[OK] {len(items)}件のレポートを生成しました。")


def cmd_compare(args):
    service = ComparisonService()
    if args.samples:
        props = [SAMPLE_PROPERTIES[k] for k in args.samples if k in SAMPLE_PROPERTIES]
    elif args.json:
        with open(args.json, encoding="utf-8") as f:
            items = json.load(f)
        props = [PropertyData(**d) for d in items]
    else:
        props = list(SAMPLE_PROPERTIES.values())

    report = service.compare(props)
    outfile = args.output or "comparison_report.md"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\n[OK] {outfile} を出力しました。")


def cmd_list(args):
    storage = StorageService()
    deals = storage.list_deals()
    if not deals:
        print("保存済み案件はありません。")
        return
    print(f"\n{'保存日時':<20} {'物件名':<25} {'種別':<12} {'価格':>15} {'ランク':>5} {'スコア':>7}")
    print("-" * 90)
    for d in deals:
        print(f"{d['saved_at']:<20} {d['property_name']:<25} {d['asset_type']:<12} "
              f"{int(d['price']):>15,} {d['rank']:>5} {d['score']:>7}")


def main():
    parser = argparse.ArgumentParser(description="My Agent Match (MAM) - 不動産仲介営業支援システム")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="案件を分析してレポート生成")
    p_analyze.add_argument("--json", help="物件データJSONファイルパス")
    p_analyze.add_argument("--sample", help=f"サンプル使用 ({'/'.join(SAMPLE_PROPERTIES.keys())})")
    p_analyze.add_argument("--output", help="出力ファイル名 (default: anken_report.md)")
    p_analyze.add_argument("--save", action="store_true", help="分析結果を履歴に保存")
    p_analyze.add_argument("--pdf", action="store_true", help="PDFレポートも生成する")

    p_extract = sub.add_parser("extract", help="テキストからAIで物件情報を抽出して分析")
    p_extract.add_argument("text", help="物件情報テキストまたはテキストファイルパス")
    p_extract.add_argument("--output", help="出力ファイル名")
    p_extract.add_argument("--pdf", action="store_true", help="PDFも生成する")

    p_batch = sub.add_parser("batch", help="複数案件を一括分析")
    p_batch.add_argument("json", help="物件データの配列JSON")
    p_batch.add_argument("--output-dir", default=".", help="出力ディレクトリ")

    p_compare = sub.add_parser("compare", help="複数案件を比較")
    p_compare.add_argument("--samples", nargs="+", help="比較するサンプル名")
    p_compare.add_argument("--json", help="比較する物件JSONファイル")
    p_compare.add_argument("--output", help="出力ファイル名")

    sub.add_parser("list", help="保存済み案件一覧を表示")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        # デフォルト: マンションサンプルで analyze
        args.json = None
        args.sample = "マンション"
        args.output = "anken_report.md"
        args.save = False
        cmd_analyze(args)


if __name__ == "__main__":
    main()
