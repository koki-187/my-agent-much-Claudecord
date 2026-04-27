from typing import Optional


class OfferEngine:
    def calculate_offer_range(
        self,
        income_value: Optional[int],
        planned_repairs_cost: Optional[int] = 0,
        risk_discount_rate: float = 0.05
    ) -> dict:
        if income_value is None:
            return {
                "low": None,
                "high": None,
                "comment": "収益還元価格が算出できないため指値レンジ算出不可"
            }

        repairs = planned_repairs_cost or 0
        base = income_value - repairs
        low = int(base * (1 - risk_discount_rate))
        high = int(base * 1.02)

        return {
            "low": low,
            "high": high,
            "comment": "NOI還元価格から修繕費とリスクディスカウントを控除して算出"
        }
