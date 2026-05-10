from dataclasses import dataclass
from typing import Optional


@dataclass
class FinanceResult:
    """融資シミュレーション結果"""
    ltv: float                      # LTV（Loan to Value）= 融資額/物件価格
    loan_amount: int                 # 想定融資額（円）
    equity_required: int             # 必要自己資金（円）
    monthly_payment_base: int        # 月次返済額（基本金利）
    monthly_payment_stress: int      # 月次返済額（ストレス金利+1%）
    annual_debt_service: int         # 年間返済額（基本金利）
    dscr_base: Optional[float]       # DSCR（基本金利）= NOI/年間返済額
    dscr_stress: Optional[float]     # DSCR（ストレス金利）
    dscr_evaluation: str             # DSCR評価（優良/良好/注意/危険）
    interest_rate_used: float        # 使用金利
    stress_rate: float               # ストレス金利
    loan_term_years: int             # ローン期間（年）
    comment: str                     # コメント
    feasibility: str                 # 融資実行可能性（高/中/低/困難）


class FinanceEngine:
    """
    2024-2025年金利環境対応融資シミュレーション
    - 日銀利上げ（2024年3月ゼロ金利解除、7月0.25%、2025年1月0.5%）を反映
    - 不動産投資ローン金利水準：変動型2.0-2.5%、固定型2.5-3.5%が目安
    """

    # 2025年時点の標準融資金利（物件種別別）
    BASE_RATES: dict[str, float] = {
        "APARTMENT_WHOLE": 2.2,   # 一棟マンション
        "APARTMENT_WOOD": 2.5,    # 木造アパート
        "UNIT": 2.0,              # 区分マンション（最も融資つきやすい）
        "HOUSE": 2.3,             # 戸建て
        "LAND": 3.5,              # 土地（最も厳しい）
        "COMMERCIAL": 2.8,        # 商業
        "OFFICE": 2.8,            # オフィス
        "FACTORY": 3.0,           # 工場・倉庫
    }

    # 物件種別別の標準LTV上限（融資割合）
    MAX_LTV: dict[str, float] = {
        "APARTMENT_WHOLE": 0.80,
        "APARTMENT_WOOD": 0.80,
        "UNIT": 0.90,
        "HOUSE": 0.85,
        "LAND": 0.70,
        "COMMERCIAL": 0.75,
        "OFFICE": 0.75,
        "FACTORY": 0.70,
    }

    def simulate(
        self,
        price: int,
        noi: Optional[float],
        asset_type_key: str = "APARTMENT_WHOLE",
        loan_term_years: int = 25,
        custom_rate: Optional[float] = None,
        custom_ltv: Optional[float] = None,
        built_year: Optional[int] = None,
    ) -> FinanceResult:
        """融資シミュレーションを実行"""
        # 金利決定
        base_rate: float = custom_rate or self.BASE_RATES.get(asset_type_key, 2.5)
        stress_rate: float = base_rate + 1.0  # ストレス金利（+1%）

        # 旧耐震は融資LTV制限
        ltv_limit: float = custom_ltv or self.MAX_LTV.get(asset_type_key, 0.80)
        if built_year and built_year < 1981:
            ltv_limit = min(ltv_limit, 0.70)  # 旧耐震は最大70%

        if price <= 0:
            raise ValueError(f"物件価格は1以上である必要があります: {price}")
        loan_amount: int = int(price * ltv_limit)
        equity_required: int = price - loan_amount
        ltv: float = loan_amount / price

        # 月次返済額（元利均等返済）
        monthly_payment_base: int = self._calc_monthly_payment(loan_amount, base_rate, loan_term_years)
        monthly_payment_stress: int = self._calc_monthly_payment(loan_amount, stress_rate, loan_term_years)
        annual_debt_service: int = monthly_payment_base * 12

        # DSCR計算
        dscr_base: Optional[float]
        dscr_stress: Optional[float]
        if noi and noi > 0 and annual_debt_service > 0:
            dscr_base = noi / annual_debt_service
            dscr_stress = noi / (monthly_payment_stress * 12)
        else:
            dscr_base = None
            dscr_stress = None

        # DSCR評価
        dscr_evaluation, feasibility, comment = self._evaluate_dscr(
            dscr_base, dscr_stress, ltv, asset_type_key, built_year
        )

        return FinanceResult(
            ltv=ltv,
            loan_amount=loan_amount,
            equity_required=equity_required,
            monthly_payment_base=monthly_payment_base,
            monthly_payment_stress=monthly_payment_stress,
            annual_debt_service=annual_debt_service,
            dscr_base=round(dscr_base, 2) if dscr_base else None,
            dscr_stress=round(dscr_stress, 2) if dscr_stress else None,
            dscr_evaluation=dscr_evaluation,
            interest_rate_used=base_rate,
            stress_rate=stress_rate,
            loan_term_years=loan_term_years,
            comment=comment,
            feasibility=feasibility,
        )

    def _calc_monthly_payment(self, loan_amount: int, annual_rate_pct: float, years: int) -> int:
        """元利均等返済の月次返済額を計算"""
        monthly_rate: float = annual_rate_pct / 100 / 12
        n: int = years * 12
        if monthly_rate == 0:
            return int(loan_amount / n)
        payment: float = loan_amount * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
        return int(payment)

    def _evaluate_dscr(
        self,
        dscr_base: Optional[float],
        dscr_stress: Optional[float],
        ltv: float,
        asset_type_key: str,
        built_year: Optional[int],
    ) -> tuple[str, str, str]:
        """DSCRを評価してコメントを生成"""
        # DSCRがない場合（土地など）
        if dscr_base is None:
            return "算出不可", "中", "土地等のため収益DSCR算出不可。自己資金・返済能力で個別判断。"

        evaluation: str
        feasibility: str
        comment: str

        if dscr_base >= 1.4:
            evaluation = "優良"
            feasibility = "高"
            stress_note = f"ストレス時({dscr_stress:.2f})でも安全。" if dscr_stress is not None else ""
            comment = (
                f"DSCR {dscr_base:.2f}は優良水準。金融機関の融資評価は高い。{stress_note}"
            )
        elif dscr_base >= 1.2:
            evaluation = "良好"
            feasibility = "高"
            comment = f"DSCR {dscr_base:.2f}は良好。標準的な融資条件で実行可能性が高い。"
        elif dscr_base >= 1.0:
            evaluation = "注意"
            feasibility = "中"
            comment = (
                f"DSCR {dscr_base:.2f}はギリギリ。金利上昇・空室時にキャッシュフローが悪化するリスクあり。"
            )
        else:
            evaluation = "危険"
            feasibility = "低"
            comment = (
                f"DSCR {dscr_base:.2f}は基準割れ。金融機関融資が困難。"
                "自己資金増額または価格引き下げが必要。"
            )

        if built_year and built_year < 1981:
            comment += " ※旧耐震のため融資銀行が限られる点も考慮が必要。"

        return evaluation, feasibility, comment

    def get_asset_type_key(self, asset_type_value: str) -> str:
        """AssetType.valueからキーへ変換"""
        mapping: dict[str, str] = {
            "一棟マンション": "APARTMENT_WHOLE",
            "一棟アパート": "APARTMENT_WOOD",
            "区分マンション": "UNIT",
            "戸建て": "HOUSE",
            "土地": "LAND",
            "商業・店舗": "COMMERCIAL",
            "オフィス": "OFFICE",
            "工場・倉庫": "FACTORY",
        }
        return mapping.get(asset_type_value, "APARTMENT_WHOLE")
