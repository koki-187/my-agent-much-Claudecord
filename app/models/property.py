from pydantic import BaseModel, Field
from typing import Optional


class PropertyData(BaseModel):
    property_name: Optional[str] = Field(default=None, description="物件名")
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
