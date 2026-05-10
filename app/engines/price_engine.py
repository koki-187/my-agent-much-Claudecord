from typing import Optional


class PriceEngine:
    def calculate_income_value(self, noi: Optional[int], target_yield: float) -> Optional[int]:
        if not noi or not target_yield or target_yield <= 0:
            return None
        return int(noi / target_yield)

    def judge_price(self, price: int, income_value: Optional[int]) -> dict:
        if income_value is None or income_value == 0:
            return {
                "status": "判定不可",
                "ratio": None,
                "comment": "NOIまたは目標利回りが不足しているため価格判定不可"
            }

        ratio = price / income_value

        if ratio <= 0.90:
            status = "割安"
            comment = "収益還元価格より低く、検討余地が高い"
        elif ratio <= 1.05:
            status = "適正"
            comment = "収益還元価格と概ね整合している"
        elif ratio <= 1.20:
            status = "やや高い"
            comment = "収益還元価格より高く、指値前提"
        else:
            status = "高すぎる"
            comment = "収益還元価格から大きく乖離。原則深追い注意"

        return {
            "status": status,
            "ratio": round(ratio, 2),
            "comment": comment
        }
