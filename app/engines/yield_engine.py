from typing import Optional


class YieldEngine:
    def calculate_gross_yield(self, gross_income: Optional[int], price: int) -> Optional[float]:
        if not gross_income or not price:
            return None
        return gross_income / price

    def calculate_net_yield(self, noi: Optional[int], price: int) -> Optional[float]:
        if not noi or not price:
            return None
        return noi / price

    def score_yield(self, net_yield: Optional[float], target_yield: float) -> int:
        if net_yield is None:
            return 40

        diff = net_yield - target_yield

        if diff >= 0.015:
            return 95
        elif diff >= 0:
            return 85
        elif diff >= -0.01:
            return 65
        elif diff >= -0.02:
            return 45
        else:
            return 25
