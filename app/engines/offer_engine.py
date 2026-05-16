"""
OfferEngine — 推奨指値レンジの算出

複数視点を統合した実務的な指値推奨を返す:
1. 収益還元視点 (NOI / target_yield - 修繕費 - リスクディスカウント)
2. 土地値視点 (路線価ベース)
3. デベ仕入れ視点 (霞が関キャピタル指標 = 路線価×4倍 - 解体費 - 立退費 - 金利)

最終的な「推奨指値レンジ」は3視点の整合性を取った保守的な範囲を返す。
"""
from typing import Optional


class OfferEngine:
    def calculate_offer_range(
        self,
        income_value: Optional[int],
        planned_repairs_cost: Optional[int] = 0,
        risk_discount_rate: float = 0.05,
        *,
        # 複数視点用 (任意・None なら従来通り収益還元ベースのみ)
        land_value_rosenka: Optional[int] = None,        # 路線価×面積
        kasumigaseki_upper: Optional[int] = None,        # 路線価×4×面積 (デベ仕入れ上限)
        demolition_cost: Optional[int] = None,           # 既存建物の解体費 (デベ視点)
        eviction_cost: Optional[int] = None,             # 立退費用合計
        interest_cost: Optional[int] = None,             # 立退期間中の金利コスト
    ) -> dict:
        """
        指値レンジを算出。複数視点で評価し統合する。

        Args:
            income_value:        収益還元価格 (NOI ÷ target_yield)
            planned_repairs_cost: 予定修繕費
            risk_discount_rate:  リスクディスカウント率 (デフォルト5%)
            land_value_rosenka:  路線価×面積 (土地値)
            kasumigaseki_upper:  路線価×4×面積 (デベ仕入れ上限の業界経験則)
            demolition_cost:     解体費 (デベ用地として購入する場合)
            eviction_cost:       立退費用合計
            interest_cost:       立退期間中の金利コスト

        Returns:
            {
              "low":  最低指値 (円, 統合後),
              "high": 最高指値 (円, 統合後),
              "comment": 説明文,
              "perspectives": {  # 各視点の単独評価
                "income": {"price": int, "label": "収益還元"},
                "land": {"price": int, "label": "土地値"},
                "developer": {"price": int, "label": "デベ仕入れ上限"},
              },
              "primary_basis": "income"|"land"|"developer"|"insufficient",
            }
        """
        if income_value is None and not (kasumigaseki_upper or land_value_rosenka):
            return {
                "low": None, "high": None,
                "comment": "収益還元価格・土地値ともに算出不可のため指値レンジ算出不可",
                "perspectives": {},
                "primary_basis": "insufficient",
            }

        perspectives: dict = {}

        # ── 視点1: 収益還元 ──
        income_price: Optional[int] = None
        if income_value is not None and income_value > 0:
            repairs = planned_repairs_cost or 0
            base = income_value - repairs
            if base > 0:
                income_price = int(base * (1 - risk_discount_rate))
                perspectives["income"] = {
                    "price": income_price,
                    "label": "収益還元 −修繕 −5%リスク",
                }

        # ── 視点2: 土地値 (路線価ベース) ──
        if land_value_rosenka is not None and land_value_rosenka > 0:
            perspectives["land"] = {
                "price": int(land_value_rosenka),
                "label": "路線価評価額",
            }

        # ── 視点3: デベ仕入れ上限 (霞が関指標) ──
        if kasumigaseki_upper is not None and kasumigaseki_upper > 0:
            # 解体費・立退費・金利を差し引いた実質的なデベ提示価格
            deductions = (demolition_cost or 0) + (eviction_cost or 0) + (interest_cost or 0)
            dev_offer = max(0, kasumigaseki_upper - deductions)
            perspectives["developer"] = {
                "price": dev_offer,
                "label": ("路線価×4倍" +
                          (f" −解体{demolition_cost//10000:,}万" if demolition_cost else "") +
                          (f" −立退{eviction_cost//10000:,}万" if eviction_cost else "") +
                          (f" −金利{interest_cost//10000:,}万" if interest_cost else "")),
            }

        # ── 統合: 「buyer タイプ」ごとに低・高を決定 ──
        # 低 (堅実派): 全視点の最小値 ÷ 1.05 安全マージン
        # 高 (積極派): 収益還元 × 1.02 か デベ視点の最大値
        prices = [p["price"] for p in perspectives.values() if p.get("price")]
        if not prices:
            return {
                "low": None, "high": None,
                "comment": "全視点の評価額が0以下のため指値レンジ算出不可",
                "perspectives": perspectives,
                "primary_basis": "insufficient",
            }

        # 統合低値: 最小視点を採用 (買主が安全側)
        integrated_low = int(min(prices))
        # 統合高値: 収益還元優先 (なければデベ視点上限)
        if income_price:
            integrated_high = int(income_price * 1.02)
            primary_basis = "income"
        else:
            integrated_high = int(max(prices) * 1.02)
            primary_basis = "developer" if "developer" in perspectives else "land"

        # 高 < 低 になるのを防止
        if integrated_high < integrated_low:
            integrated_high = integrated_low

        # 説明文構築
        if len(perspectives) == 1:
            comment = next(iter(perspectives.values()))["label"] + " ベース"
        else:
            labels = " / ".join(f"{k}={v['price']/1e8:.2f}億" for k, v in perspectives.items())
            comment = f"複数視点統合 ({labels})"

        return {
            "low": integrated_low,
            "high": integrated_high,
            "comment": comment,
            "perspectives": perspectives,
            "primary_basis": primary_basis,
        }
