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
        component_scores: dict
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
| 収益還元価格 | {income_value_text} |
| 売出価格 / 収益還元価格 | {price_result.get('ratio') or '算出不可'} |

**価格コメント：**
{price_result.get('comment')}

---

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
        return report
