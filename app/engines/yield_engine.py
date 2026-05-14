from typing import Optional


class YieldEngine:
    def calculate_gross_yield(self, gross_income: Optional[int], price: int) -> Optional[float]:
        # gross_income=0 (空地・解体予定等) は有効な「ゼロ収入」として 0.0 を返すべき。
        # `not gross_income` だと 0 も None と同じ扱いになるバグを修正。
        if gross_income is None or not price or price <= 0:
            return None
        return gross_income / price

    def calculate_net_yield(self, noi: Optional[int], price: int) -> Optional[float]:
        # noi=0 も valid データ。`not noi` での falsy 判定は不適切。
        if noi is None or not price or price <= 0:
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
