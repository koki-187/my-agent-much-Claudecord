from pydantic import BaseModel, Field
from typing import Optional, List


class ClientData(BaseModel):
    client_name: str
    target_areas: List[str] = Field(default_factory=list)
    min_yield: Optional[float] = None
    max_price: Optional[int] = None
    preferred_asset_types: List[str] = Field(default_factory=list)
    risk_tolerance: str = "medium"
