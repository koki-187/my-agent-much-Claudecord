from typing import List, Optional
from app.models.property import PropertyData


class ReportGenerator:
    def generate_markdown(
        self,
        property_data: PropertyData,
        price_result: dict,
        score_result: dict,
        offer_result: dict,
        risks: List[dict],
        questions: List[str],
        component_scores: dict,
        target_yield: float = 0.075,
        rosenka_result=None,
        finance_result=None,
        exit_result=None,
        repair_result=None,
        area_trend=None,
    ) -> str:
        risk_lines = "\n".join([
            f"- **{r['type']}**（{r['level']}）：{r['message']}"
            for r in risks
        ]) or "- 現時点で重大なリスクは検出されていません。"

        question_lines = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

        offer_text = "算出不可"
        if offer_result.get("low") and offer_result.get("high"):
            offer_text = f"{offer_result['low']:,}円 〜 {offer_result['high']:,}円"

        income_value_text = "算出不可"
        if price_result.get("income_value"):
            income_value_text = f"{price_result['income_value']:,}円"

        report = f"""# 案件調査レポート：{property_data.property_name or '名称未設定'}

## 1. 総合判定

| 項目 | 内容 |
|---|---|
| ランク | **{score_result['rank']}** |
| 総合スコア | **{score_result['total_score']}点** |
| 判断 | **{score_result['judgement']}** |
| 価格判定 | **{price_result['status']}** |
| 推奨指値レンジ | **{offer_text}** |

---

## 2. 物件概要

| 項目 | 内容 |
|---|---|
| 物件種別 | {property_data.asset_type.value} |
| 所在地 | {property_data.address} |
| 売出価格 | {property_data.price:,}円 |
| 土地面積 | {property_data.land_area_sqm or '未入力'}㎡ |
| 建物面積 | {property_data.building_area_sqm or '未入力'}㎡ |
| 構造 | {property_data.structure or '未入力'} |
| 築年 / 竣工年 | {property_data.built_year or '未入力'} |
| 用途地域 | {property_data.zoning or '未入力'} |
| 接道 | {property_data.road_access or '未入力'} |
| 商流段数 | {property_data.broker_chain_count or '未入力'} |

---

## 3. 収益性・価格妥当性

| 項目 | 内容 |
|---|---|
| 満室想定年収 | {property_data.gross_income or '未入力'} |
| 現況年収 | {property_data.actual_income or '未入力'} |
| NOI | {property_data.noi or '未入力'} |
| 稼働率 | {property_data.occupancy_rate or '未入力'} |
| 表面利回り | {property_data.gross_yield or '未入力'} |
| 実質利回り | {property_data.net_yield or '未入力'} |
| 目標利回り（判定基準） | {target_yield:.1%} |
| 収益還元価格 | {income_value_text} |
| 売出価格 / 収益還元価格 | {price_result.get('ratio') or '算出不可'} |

**価格コメント：**
{price_result.get('comment')}

---
"""

        # セクション3-A: 路線価・土地価格分析
        if rosenka_result is not None:
            actual_sqm_text = (
                f"{rosenka_result.actual_per_sqm:,.0f}円/㎡"
                if rosenka_result.actual_per_sqm is not None
                else "算出不可"
            )
            ratio_text = (
                f"{rosenka_result.ratio_to_rosenka:.2f}倍"
                if rosenka_result.ratio_to_rosenka is not None
                else "算出不可"
            )
            report += f"""
## 3-A. 路線価・土地価格分析

| 項目 | 内容 |
|---|---|
| 参照エリア | {rosenka_result.matched_area} |
| 路線価（㎡単価） | {rosenka_result.rosenka_per_sqm:,}円/㎡ |
| 公示地価（㎡単価） | {rosenka_result.land_price_per_sqm:,}円/㎡ |
| 売出価格の㎡単価 | {actual_sqm_text} |
| 路線価比 | {ratio_text} |
| 土地価格評価 | **{rosenka_result.evaluation}** |
| データ信頼度 | {rosenka_result.confidence} |

> {rosenka_result.comment}

---
"""

        # セクション3-B: エリア市場トレンド
        if area_trend is not None:
            price_change_text = (
                f"{area_trend.price_change_yoy:+.1%}"
                if area_trend.price_change_yoy is not None
                else "データなし"
            )
            vacancy_text = (
                f"{area_trend.vacancy_rate:.1%}"
                if area_trend.vacancy_rate is not None
                else "データなし"
            )
            report += f"""
## 3-B. エリア市場トレンド（2024-2025）

| 項目 | 内容 |
|---|---|
| エリア | {area_trend.matched_area} |
| 市場トレンド | **{area_trend.trend}** |
| 前年比価格変動 | {price_change_text} |
| 賃貸需要 | {area_trend.rental_demand} |
| 推定空室率 | {vacancy_text} |

> {area_trend.comment}

---
"""

        # セクション4: スコア内訳
        report += f"""
## 4. スコア内訳

| 評価項目 | 点数 |
|---|---:|
| 価格妥当性 | {component_scores['price_score']} |
| 収益性 | {component_scores['yield_score']} |
| 流動性 | {component_scores['liquidity_score']} |
| 開発可能性 | {component_scores['development_score']} |
| リスク耐性 | {component_scores['risk_score']} |
| 商流・売主温度感 | {component_scores['broker_score']} |

---
"""

        # セクション4-A: 融資シミュレーション
        if finance_result is not None:
            dscr_base_text = (
                f"{finance_result.dscr_base}"
                if finance_result.dscr_base is not None
                else "算出不可"
            )
            dscr_stress_text = (
                f"{finance_result.dscr_stress}"
                if finance_result.dscr_stress is not None
                else "算出不可"
            )
            report += f"""
## 4-A. 融資シミュレーション（2025年金利環境）

| 項目 | 内容 |
|---|---|
| 想定LTV | {finance_result.ltv:.0%} |
| 想定融資額 | {finance_result.loan_amount:,}円 |
| 必要自己資金 | {finance_result.equity_required:,}円 |
| 使用金利 | {finance_result.interest_rate_used:.1f}% |
| ストレス金利 | {finance_result.stress_rate:.1f}% |
| 月次返済額（通常） | {finance_result.monthly_payment_base:,}円 |
| 月次返済額（ストレス） | {finance_result.monthly_payment_stress:,}円 |
| DSCR（通常） | {dscr_base_text} |
| DSCR（ストレス） | {dscr_stress_text} |
| DSCR評価 | **{finance_result.dscr_evaluation}** |
| 融資実行可能性 | **{finance_result.feasibility}** |

> {finance_result.comment}

---
"""

        # セクション4-B: 修繕費積算
        if repair_result is not None:
            report += f"""
## 4-B. 修繕費積算（2024年建築費水準）

| 区分 | 金額 |
|---|---:|
| 即時対応費用 | {repair_result.immediate_cost:,}円 |
| 5年以内費用 | {repair_result.five_year_cost:,}円 |
| 10年以内費用 | {repair_result.ten_year_cost:,}円 |
| ライフサイクル総計 | {repair_result.total_lifecycle_cost:,}円 |

> {repair_result.comment}

---
"""

        # セクション5: 検出リスク
        report += f"""
## 5. 検出リスク

{risk_lines}

---

## 6. 推奨ヒアリング項目

{question_lines}

---

## 7. 推奨アクション

"""

        if score_result["rank"] in ["S", "A"]:
            report += """- 早急に元付または売主側に条件確認する
- 最新レントロール・修繕履歴・固定資産税資料を取得する
- 買主候補へ初期打診する
- 指値余地がある場合は根拠資料を添えて交渉する
"""
        elif score_result["rank"] == "B":
            report += """- 指値前提で検討する
- 売主の最低売却ラインを確認する
- リスク項目が価格に織り込まれるか確認する
- 買主候補が具体的に出る場合のみ深掘りする
"""
        elif score_result["rank"] == "C":
            report += """- 原則様子見
- 不足資料が揃うまでは買主提案を控える
- 価格改定または売主温度感の変化があれば再検討する
"""
        else:
            report += """- 原則追わない
- 営業リソースを投入しない
- 価格・商流・法的リスクが改善された場合のみ再評価する
"""

        report += """

---

## 8. 最終結論

なぜ？
→ 案件判断で重要なのは、情報量ではなく判断基準だからです。

なぜ？
→ 価格・利回り・商流・リスク・出口を一体で見ないと、営業マンが案件に踊らされるからです。

なぜ？
→ ベテランが無意識に行う判断を、再現可能な形に落とし込む必要があるからです。

**結論：この案件は上記ランクと推奨アクションに従って対応してください。**
"""

        # セクション9: 出口戦略評価
        if exit_result is not None:
            risk_items = "\n".join(f"- {r}" for r in exit_result.risk_factors) or "- 特になし"
            scenario_rows = ""
            for s in exit_result.scenarios:
                scenario_rows += (
                    f"| {s.name} | {s.holding_years}年 | {s.exit_cap_rate:.1%} "
                    f"| {s.expected_exit_price:,}円 | {s.total_noi_accumulated:,}円 "
                    f"| {s.irr_approx:.1%} |\n"
                )
            if not scenario_rows:
                scenario_rows = "| - | - | - | シミュレーション不可 | - | - |\n"

            report += f"""
---

## 9. 出口戦略評価

**想定買主属性：** {exit_result.buyer_type}
**流動性見通し：** {exit_result.liquidity_outlook}

### シナリオ別出口試算

| シナリオ | 保有年数 | 売却時Cap Rate | 想定売却価格 | 累積NOI | IRR（概算） |
|---|---|---|---|---|---|
{scenario_rows}
**出口リスク：**
{risk_items}

**推奨：** {exit_result.recommendation}
"""

        return report
