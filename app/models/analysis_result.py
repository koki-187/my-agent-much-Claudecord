from pydantic import BaseModel
from typing import List, Dict, Optional


class AnalysisResult(BaseModel):
    rank: str
    total_score: float
    price_status: str
    income_value: Optional[int]
    recommended_offer_low: Optional[int]
    recommended_offer_high: Optional[int]
    risks: List[Dict]
    hearing_questions: List[str]
    summary: str
    action: str
