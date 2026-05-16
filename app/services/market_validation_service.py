"""market_validation_service.py — 入力値の市場相場検証サービス"""
import csv
import os
from functools import lru_cache
from typing import Optional

from app.models.property import AssetType, PropertyData

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "rent_market.csv")

# asset_type別の1戸あたり延床面積の合理的範囲 (min_sqm, max_sqm)
_AREA_RANGES: dict[str, tuple[float, float]] = {
    # 1戸あたり延床(共用部込)の現実的範囲
    # 注: 共用部15-20%考慮 → 専有15㎡確保するには延床18㎡以上が必要
    AssetType.APARTMENT_WHOLE.value: (18.0, 80.0),
    AssetType.APARTMENT_WOOD.value: (18.0, 50.0),
    AssetType.UNIT.value: (18.0, 200.0),
    AssetType.HOUSE.value: (50.0, 200.0),
}

# CSV asset_type列とのマッピング
_ASSET_TYPE_TO_CSV: dict[str, Optional[str]] = {
    AssetType.APARTMENT_WHOLE.value: "マンション",
    AssetType.APARTMENT_WOOD.value: "マンション",
    AssetType.UNIT.value: "マンション",
    AssetType.HOUSE.value: "マンション",
    AssetType.COMMERCIAL.value: "商業",
    AssetType.OFFICE.value: "オフィス",
    AssetType.FACTORY.value: None,
    AssetType.LAND.value: None,
}


@lru_cache(maxsize=1)
def _load_rent_data() -> tuple[dict, ...]:
    """rent_market.csv を 1 回だけロード → tuple でキャッシュ
    (lru_cache は hashable 戻り値が必要なので tuple of dict にする)"""
    try:
        with open(_CSV_PATH, encoding="utf-8") as f:
            return tuple(csv.DictReader(f))
    except FileNotFoundError:
        return tuple()


def validate_building_area(
    units: Optional[int],
    floors: Optional[int],
    building_area_sqm: Optional[float],
    asset_type: Optional[str] = None,
) -> dict:
    """延床面積の異常検知。1戸あたり面積を算出し、asset_type別の合理的範囲と比較する。"""
    base: dict = {
        "status": "insufficient_data",
        "area_per_unit_sqm": None,
        "expected_min_sqm": None,
        "expected_max_sqm": None,
        "warning_message": None,
        "suggested_action": None,
    }

    # 商業・オフィス・土地・工場はスキップ
    skip_types = {AssetType.COMMERCIAL.value, AssetType.OFFICE.value,
                  AssetType.FACTORY.value, AssetType.LAND.value}
    if asset_type in skip_types:
        base["status"] = "ok"
        return base

    if not units or units <= 0 or not building_area_sqm or building_area_sqm <= 0:
        return base

    area_per_unit = building_area_sqm / units
    base["area_per_unit_sqm"] = round(area_per_unit, 2)

    # asset_typeが不明な場合はデータ不足扱い
    if asset_type not in _AREA_RANGES:
        return base

    min_sqm, max_sqm = _AREA_RANGES[asset_type]
    base["expected_min_sqm"] = min_sqm
    base["expected_max_sqm"] = max_sqm

    floors_info = f"{floors}階建" if floors else ""
    units_info = f"{units}戸"
    area_info = f"延床{building_area_sqm:,.0f}㎡"
    per_unit_info = f"1戸あたり{area_per_unit:.1f}㎡"

    if area_per_unit < min_sqm:
        base["status"] = "suspicious_too_small"
        base["warning_message"] = (
            f"{units_info}×{floors_info}ですが{area_info}={per_unit_info}。"
            f"OCR誤読の可能性大。紹介元に正確な延床面積を要確認。"
        )
        base["suggested_action"] = "売主・仲介業者に正確な延床面積・登記簿謄本を確認する"
    elif area_per_unit > max_sqm:
        base["status"] = "suspicious_too_large"
        base["warning_message"] = (
            f"{units_info}×{floors_info}で{area_info}={per_unit_info}。"
            f"ファミリー向け高級物件か、戸数情報が誤っている可能性。"
        )
        base["suggested_action"] = "戸数・間取り情報を再確認する"
    else:
        base["status"] = "ok"

    return base


def compare_rent_with_market(
    actual_rent_per_month_per_unit: Optional[float],
    address: Optional[str],
    asset_type: Optional[str] = None,
    unit_area_sqm: Optional[float] = None,
) -> dict:
    """現況賃料（戸あたり月額）と相場を比較する。

    None / 0 / 空文字 等の入力に対しては `insufficient_data` を返し、
    例外を投げない (堅牢性重視)。
    """
    base: dict = {
        "status": "insufficient_data",
        "actual_rent_per_sqm": None,
        "market_rent_per_sqm": None,
        "ratio_to_market": None,
        "matched_area": None,
        "warning_message": None,
        "downside_risk_pct": None,
    }

    # None ガード: 一切のエラーを出さずに insufficient_data
    if actual_rent_per_month_per_unit is None:
        return base
    if actual_rent_per_month_per_unit <= 0 or not address:
        return base

    csv_type = _ASSET_TYPE_TO_CSV.get(asset_type or "") if asset_type else None
    if not csv_type:
        return base

    rent_data = _load_rent_data()
    if not rent_data:
        return base

    # 最長一致でエリアを検索
    market_rent_per_sqm: Optional[float] = None
    matched_area: Optional[str] = None
    best_len = 0
    for row in rent_data:
        if row.get("asset_type") != csv_type:
            continue
        area = row.get("area", "")
        if area and area in address and len(area) > best_len:
            try:
                market_rent_per_sqm = float(row["avg_rent_per_sqm"])
                matched_area = area
                best_len = len(area)
            except (ValueError, KeyError):
                pass

    if not market_rent_per_sqm or market_rent_per_sqm <= 0:
        return base

    base["market_rent_per_sqm"] = market_rent_per_sqm
    base["matched_area"] = matched_area

    if unit_area_sqm and unit_area_sqm > 0:
        # ㎡単価で比較
        actual_per_sqm = actual_rent_per_month_per_unit / unit_area_sqm
        base["actual_rent_per_sqm"] = round(actual_per_sqm, 1)
        ratio = actual_per_sqm / market_rent_per_sqm
    else:
        # 面積不明のため比較不能
        return base

    base["ratio_to_market"] = round(ratio, 4)

    if ratio >= 1.20:
        downside = round((1 - 1 / ratio) * 100, 1)
        base["status"] = "above_market"
        base["downside_risk_pct"] = downside
        base["warning_message"] = (
            f"現況賃料が相場の{ratio:.0%}（参照: {matched_area}、相場: {market_rent_per_sqm:,.0f}円/㎡）。"
            f"退去後に賃料が約{downside:.0f}%下落するリスクあり。"
        )
    elif ratio <= 0.85:
        base["status"] = "below_market"
        base["warning_message"] = (
            f"現況賃料が相場の{ratio:.0%}（参照: {matched_area}、相場: {market_rent_per_sqm:,.0f}円/㎡）。"
            f"相場より割安で賃料引上げのアップサイドが期待できる。"
        )
    else:
        base["status"] = "ok"

    return base


def validate_property(
    property_data: PropertyData,
    *,
    current_unit_rent: Optional[float] = None,
) -> dict:
    """PropertyDataを総合的に検証し、警告リストを返す。"""
    warnings: list[dict] = []
    checks_performed: list[str] = []

    # A. 延床面積の異常検知
    # 戸数はgross_income / actual_incomeから推定するか、PropertyDataに直接ない場合はスキップ
    # PropertyDataにunitsフィールドはないため、building_area_sqmと簡易チェックのみ
    # PropertyDataにfloors/unitsは持っていないが、notesやcurrent_statusから取得困難なため、
    # 呼び出し側が引数で渡すことを前提とした設計。validate_building_areaは独立関数として公開済み。
    # ここでは面積の最低限チェック（1棟系で極端に小さい場合）を実施する。
    checks_performed.append("building_area_basic")
    asset_val = property_data.asset_type.value if property_data.asset_type else None
    if property_data.building_area_sqm and asset_val in _AREA_RANGES:
        min_sqm, _ = _AREA_RANGES[asset_val]
        if property_data.building_area_sqm < min_sqm:
            warnings.append({
                "category": "building_area",
                "level": "medium",
                "message": f"建物面積{property_data.building_area_sqm}㎡は最低基準{min_sqm}㎡未満。データ確認を推奨。",
                "action": "売主・仲介に正確な建物面積を確認する",
            })

    # B. 賃料水準の相場比較
    checks_performed.append("rent_market")
    rent_month_per_unit: Optional[float] = current_unit_rent
    unit_area: Optional[float] = None

    # 単位面積は rentable_area or building_area を利用
    area_sqm = property_data.rentable_area_sqm or property_data.building_area_sqm

    if rent_month_per_unit and area_sqm and area_sqm > 0 and property_data.address:
        result = compare_rent_with_market(
            actual_rent_per_month_per_unit=rent_month_per_unit,
            address=property_data.address,
            asset_type=asset_val,
            unit_area_sqm=area_sqm,
        )
        if result["status"] == "above_market":
            warnings.append({
                "category": "rent_market",
                "level": "high",
                "message": result["warning_message"],
                "action": "レントロールと市場賃料の乖離を確認し、退去後のNOI再試算を行う",
            })
        elif result["status"] == "below_market":
            warnings.append({
                "category": "rent_market",
                "level": "low",
                "message": result["warning_message"],
                "action": "賃料引上げ交渉のタイミングと入居者属性を確認する",
            })

    return {"warnings": warnings, "checks_performed": checks_performed}
