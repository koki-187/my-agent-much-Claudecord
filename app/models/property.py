from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AssetType(str, Enum):
    APARTMENT_WHOLE = "一棟マンション"
    APARTMENT_WOOD = "一棟アパート"
    UNIT = "区分マンション"
    HOUSE = "戸建て"
    LAND = "土地"
    COMMERCIAL = "商業・店舗"
    OFFICE = "オフィス"
    FACTORY = "工場・倉庫"


class PropertyData(BaseModel):
    property_name: Optional[str] = Field(default=None, description="物件名")
    asset_type: AssetType = Field(default=AssetType.APARTMENT_WHOLE, description="物件種別")
    address: str = Field(description="所在地")
    price: int = Field(description="売出価格")

    land_area_sqm: Optional[float] = Field(default=None, description="土地面積㎡")
    building_area_sqm: Optional[float] = Field(default=None, description="建物面積㎡")
    structure: Optional[str] = Field(default=None, description="構造")
    built_year: Optional[int] = Field(default=None, description="築年または竣工年")

    gross_income: Optional[int] = Field(default=None, description="満室想定年収")
    actual_income: Optional[int] = Field(default=None, description="現況年収")
    noi: Optional[int] = Field(default=None, description="NOI")
    occupancy_rate: Optional[float] = Field(default=None, description="稼働率 0.95など")
    gross_yield: Optional[float] = Field(default=None, description="表面利回り 0.075など")
    net_yield: Optional[float] = Field(default=None, description="実質利回り 0.06など")

    zoning: Optional[str] = Field(default=None, description="用途地域")
    building_coverage_ratio: Optional[float] = Field(default=None, description="建蔽率")
    floor_area_ratio: Optional[float] = Field(default=None, description="容積率")
    road_access: Optional[str] = Field(default=None, description="接道情報")
    current_status: Optional[str] = Field(default=None, description="現況")

    seller_reason: Optional[str] = Field(default=None, description="売却理由")
    seller_motivation: Optional[str] = Field(default=None, description="売主温度感")
    broker_chain_count: Optional[int] = Field(default=None, description="商流の段数")
    document_freshness_days: Optional[int] = Field(default=None, description="資料更新からの日数")

    repair_history: Optional[str] = Field(default=None, description="修繕履歴")
    planned_repairs_cost: Optional[int] = Field(default=0, description="今後想定修繕費")
    legal_notes: Optional[str] = Field(default=None, description="法的懸念")
    notes: Optional[str] = Field(default=None, description="その他メモ")

    # 物件種別固有フィールド
    management_fee_monthly: Optional[int] = Field(default=None, description="管理費月額（区分用）")
    repair_reserve_monthly: Optional[int] = Field(default=None, description="修繕積立金月額（区分用）")
    land_price_per_sqm: Optional[int] = Field(default=None, description="路線価・坪単価（土地用）")
    buildable_floor_area: Optional[float] = Field(default=None, description="建築可能延床面積（土地用）")
    tenant_name: Optional[str] = Field(default=None, description="テナント名（商業・オフィス用）")
    lease_expiry: Optional[str] = Field(default=None, description="契約満了日（商業・オフィス用）")
    lease_type: Optional[str] = Field(default=None, description="賃貸借種類（定期/普通）")
    ceiling_height_m: Optional[float] = Field(default=None, description="天井高（工場・倉庫用）")
    truck_access: Optional[str] = Field(default=None, description="トラック接車可否（工場・倉庫用）")
