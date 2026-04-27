from app.models.property import PropertyData
from app.services.deal_judgement_service import DealJudgementService


def main() -> None:
    sample_property = PropertyData(
        property_name="サンプル収益マンション",
        address="東京都新宿区",
        price=120_000_000,
        land_area_sqm=250.0,
        building_area_sqm=600.0,
        structure="RC造",
        built_year=1995,
        gross_income=10_000_000,
        actual_income=9_200_000,
        noi=7_200_000,
        occupancy_rate=0.92,
        gross_yield=0.083,
        zoning="近隣商業地域",
        building_coverage_ratio=0.80,
        floor_area_ratio=3.00,
        road_access="公道 接道あり",
        current_status="賃貸中",
        seller_reason=None,
        seller_motivation="不明",
        broker_chain_count=3,
        document_freshness_days=75,
        planned_repairs_cost=2_000_000,
        notes="商流が長く、売主温度感は未確認"
    )

    service = DealJudgementService(target_yield=0.075)
    report = service.analyze(sample_property)

    print(report)

    with open("anken_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n[OK] anken_report.md を出力しました。")


if __name__ == "__main__":
    main()
