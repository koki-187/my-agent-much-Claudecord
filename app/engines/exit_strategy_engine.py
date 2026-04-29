from dataclasses import dataclass
from typing import Optional


@dataclass
class ExitScenario:
    """出口シナリオ"""
    name: str                   # シナリオ名
    holding_years: int          # 保有年数
    exit_cap_rate: float        # 売却時想定Cap Rate
    expected_exit_price: int    # 想定売却価格
    total_noi_accumulated: int  # 累積NOI
    total_return: float         # トータルリターン率
    irr_approx: float           # 簡易IRR（近似）
    comment: str                # 評価コメント


@dataclass
class ExitStrategyResult:
    """出口戦略評価結果"""
    scenarios: list[ExitScenario]   # 複数シナリオ
    best_scenario: str              # 推奨シナリオ名
    buyer_type: str                 # 想定買主属性
    liquidity_outlook: str          # 流動性見通し
    risk_factors: list[str]         # 出口リスク要因
    overall_evaluation: str         # 総合評価
    recommendation: str             # 推奨アクション


class ExitStrategyEngine:
    """
    出口戦略評価エンジン
    2024-2025年の不動産市場環境：
    - 低金利環境の終焉でキャップレート上昇圧力
    - インバウンド回復で商業・ホテル需要回復
    - 建築費高騰で新築供給制約 → 中古物件の相対的割安感
    - 外国人投資家の東京・大阪プレミアム付与
    """

    # 物件種別の市場Cap Rate（2025年時点）
    MARKET_CAP_RATES: dict[str, dict[str, Optional[float]]] = {
        "APARTMENT_WHOLE": {"low": 0.045, "mid": 0.060, "high": 0.075},
        "APARTMENT_WOOD": {"low": 0.065, "mid": 0.080, "high": 0.100},
        "UNIT": {"low": 0.040, "mid": 0.055, "high": 0.070},
        "HOUSE": {"low": 0.055, "mid": 0.070, "high": 0.085},
        "LAND": {"low": None, "mid": None, "high": None},
        "COMMERCIAL": {"low": 0.050, "mid": 0.065, "high": 0.080},
        "OFFICE": {"low": 0.045, "mid": 0.060, "high": 0.075},
        "FACTORY": {"low": 0.060, "mid": 0.075, "high": 0.090},
    }

    # 想定買主属性
    BUYER_TYPES: dict[str, str] = {
        "APARTMENT_WHOLE": "国内不動産ファンド・富裕層個人投資家・外国人投資家（東京）",
        "APARTMENT_WOOD": "国内個人投資家・サラリーマン大家・地元投資家",
        "UNIT": "国内個人投資家・海外投資家・自己利用+投資の二次取得者",
        "HOUSE": "実需エンドユーザー・土地値需要家・建売業者",
        "LAND": "デベロッパー・建売業者・実需エンドユーザー",
        "COMMERCIAL": "事業法人・不動産ファンド・テナント企業本体",
        "OFFICE": "事業法人・Jリート・不動産ファンド",
        "FACTORY": "事業法人（製造・物流）・物流ファンド・地元オーナー",
    }

    def evaluate(
        self,
        price: int,
        noi: Optional[float],
        asset_type_key: str = "APARTMENT_WHOLE",
        address: str = "",
        built_year: Optional[int] = None,
        occupancy_rate: Optional[float] = None,
    ) -> ExitStrategyResult:
        """出口戦略を複数シナリオで評価"""

        cap_rates = self.MARKET_CAP_RATES.get(asset_type_key, self.MARKET_CAP_RATES["APARTMENT_WHOLE"])

        # シナリオ作成
        scenarios: list[ExitScenario] = []
        if noi and noi > 0 and cap_rates.get("mid"):
            for years, label in [(3, "短期(3年)"), (5, "中期(5年)"), (10, "長期(10年)")]:
                # 保有年数に応じたCap Rate変動（金利上昇環境でCap Rateは緩やかに上昇）
                cap_rate_drift: float = 0.005 * (years / 5)  # 5年で+0.5%上昇を想定
                exit_cap: float = cap_rates["mid"] + cap_rate_drift  # type: ignore[operator]
                exit_price: int = int(noi / exit_cap)
                cumulative_noi: int = int(noi * years * 0.95)  # 空室考慮5%
                capital_gain: int = exit_price - price
                total_return: float = (cumulative_noi + capital_gain) / price
                irr: float = self._estimate_irr(price, noi, exit_price, years)
                comment: str = self._make_scenario_comment(years, exit_cap, exit_price, price, irr)
                scenarios.append(ExitScenario(
                    name=label,
                    holding_years=years,
                    exit_cap_rate=round(exit_cap, 4),
                    expected_exit_price=exit_price,
                    total_noi_accumulated=cumulative_noi,
                    total_return=round(total_return, 3),
                    irr_approx=round(irr, 3),
                    comment=comment,
                ))

        # 最良シナリオ判定
        best: str = max(scenarios, key=lambda s: s.irr_approx).name if scenarios else "シミュレーション不可"

        # リスク要因
        risks: list[str] = self._detect_exit_risks(asset_type_key, built_year, occupancy_rate, address)

        # 流動性見通し
        liquidity: str = self._assess_liquidity(asset_type_key, address, built_year)

        # 総合評価
        best_irr: float = max(s.irr_approx for s in scenarios) if scenarios else 0.0
        overall: str
        if best_irr >= 0.08:
            overall = "優良（トータルリターン見込み高）"
        elif best_irr >= 0.05:
            overall = "良好（標準的な投資収益）"
        elif best_irr >= 0.02:
            overall = "普通（収益は限定的）"
        else:
            overall = "注意（出口でのキャピタルロスリスクあり）"

        rec: str = self._make_recommendation(scenarios, risks, asset_type_key)

        return ExitStrategyResult(
            scenarios=scenarios,
            best_scenario=best,
            buyer_type=self.BUYER_TYPES.get(asset_type_key, "投資家・事業法人"),
            liquidity_outlook=liquidity,
            risk_factors=risks,
            overall_evaluation=overall,
            recommendation=rec,
        )

    def _estimate_irr(self, price: int, noi: float, exit_price: int, years: int) -> float:
        """簡易IRR近似（自己資金20%前提）"""
        equity: float = price * 0.20
        annual_cf: float = noi * 0.4  # NOIの40%をキャッシュフロー（返済・税後概算）
        total_cf: float = annual_cf * years + exit_price * 0.20  # 残存エクイティ
        if equity <= 0:
            return 0.0
        total_return: float = (total_cf - equity) / equity / years
        return max(total_return, -0.5)

    def _make_scenario_comment(
        self,
        years: int,
        exit_cap: float,
        exit_price: int,
        buy_price: int,
        irr: float,
    ) -> str:
        diff: int = exit_price - buy_price
        sign: str = "+" if diff >= 0 else ""
        return (
            f"{years}年保有後Cap Rate {exit_cap:.1%}で売却想定。"
            f"売却価格{exit_price:,}円（{sign}{diff:,}円）。IRR約{irr:.1%}。"
        )

    def _detect_exit_risks(
        self,
        asset_type_key: str,
        built_year: Optional[int],
        occupancy_rate: Optional[float],
        address: str,
    ) -> list[str]:
        risks: list[str] = []
        if built_year and built_year < 1981:
            risks.append("旧耐震：出口バイヤーが限定される（融資制約）")
        if occupancy_rate is not None and occupancy_rate < 0.85:
            risks.append("低稼働：売却時の収益実績が弱く買主評価が低下")
        if asset_type_key in ("COMMERCIAL", "OFFICE"):
            risks.append("テナント退去リスク：売却前の退去で価値が大幅低下する可能性")
        if asset_type_key == "FACTORY":
            risks.append("工場・倉庫は買主層が限定。立地・アクセスによっては長期化")
        if asset_type_key == "LAND":
            risks.append("建築コスト高騰で開発業者の購入意欲が低下している局面")
        return risks

    def _assess_liquidity(
        self,
        asset_type_key: str,
        address: str,
        built_year: Optional[int],
    ) -> str:
        score_map: dict[str, int] = {
            "UNIT": 90,
            "APARTMENT_WHOLE": 75,
            "APARTMENT_WOOD": 70,
            "HOUSE": 72,
            "LAND": 65,
            "COMMERCIAL": 55,
            "OFFICE": 50,
            "FACTORY": 40,
        }
        base: int = score_map.get(asset_type_key, 60)
        if address and any(a in address for a in ["東京", "大阪", "名古屋", "福岡"]):
            base += 10
        if built_year and built_year < 1981:
            base -= 15
        if base >= 80:
            return "高（3〜6ヶ月での売却が現実的）"
        elif base >= 60:
            return "中（6〜12ヶ月の売却期間を想定）"
        else:
            return "低（12ヶ月以上を覚悟し、条件次第では長期化）"

    def _make_recommendation(
        self,
        scenarios: list[ExitScenario],
        risks: list[str],
        asset_type_key: str,
    ) -> str:
        if not scenarios:
            return "収益データ不足のためシミュレーション不可。NOI・利回りを確認のこと。"
        best = max(scenarios, key=lambda s: s.irr_approx)
        rec: str = f"推奨保有期間：{best.name}。"
        if len(risks) >= 3:
            rec += " リスク要因が多く、出口の選択肢が限定的。指値交渉と事前条件整備を優先。"
        elif len(risks) >= 1:
            rec += " 一部リスクあり。買主候補の事前ヒアリングと出口シミュレーションを実施のこと。"
        else:
            rec += " 出口リスクは限定的。買主候補への早期打診が有効。"
        return rec
