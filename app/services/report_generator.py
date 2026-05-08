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
        next_action_result=None,
        dev_land_result=None,
        rent_upside_score=None,
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

        # セクション0: ワンライン判断（next_action_resultがある場合）
        quick_summary = ""
        if next_action_result is not None:
            go_no_go = next_action_result.go_no_go
            go_no_go_emoji = {"追う": "🟢", "条件次第": "🟡", "情報確認が必要": "🔵"}.get(go_no_go, "🔴")
            today_action_text = (
                next_action_result.today_actions[0].action
                if next_action_result.today_actions
                else "紹介元に状況確認の連絡を入れる"
            )
            quick_summary = (
                f"> ## ⚡ ワンライン判断\n"
                f"> **{go_no_go_emoji} {go_no_go}** — {next_action_result.go_no_go_reason}\n"
                f">\n"
                f"> 📍 **今日やること**: {today_action_text}\n\n"
            )

        # Section 1 の「判断」: go_no_go が明確な場合はそちらを優先
        final_judgement = score_result['judgement']
        if next_action_result and next_action_result.go_no_go:
            gng = next_action_result.go_no_go
            go_emoji = {"追う": "🟢", "条件次第": "🟡", "情報確認が必要": "🔵"}.get(gng, "🔴")
            final_judgement = f"{go_emoji} {gng}"

        land_covers_row = ""
        if component_scores.get("land_value_covers_price"):
            land_covers_row = "| 🏆 土地値担保 | **土地値だけで売値をカバー（建物はほぼ無価値で取得可能）** |\n"

        report = f"""# 案件調査レポート：{property_data.property_name or '名称未設定'}

{quick_summary}

## 1. 総合判定

| 項目 | 内容 |
|---|---|
| ランク | **{score_result['rank']}** |
| 総合スコア | **{score_result['total_score']}点** |
| 判断 | **{final_judgement}** |
| 価格判定 | **{price_result['status']}** |
| 推奨指値レンジ | **{offer_text}** |
{land_covers_row}
"""
        # ディールブレーカー警告
        deal_breaker_reasons = score_result.get("deal_breaker_reasons")
        if deal_breaker_reasons:
            reasons_text = "\n".join(f"> - {r}" for r in deal_breaker_reasons)
            report += f"> ⚠️ **ディールブレーカー検出**\n{reasons_text}\n\n"

        report += f"""---

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
| 満室想定年収 | {f"{property_data.gross_income:,}円" if property_data.gross_income else "未入力"} |
| 現況年収 | {f"{property_data.actual_income:,}円" if property_data.actual_income else "未入力"} |
| NOI | {f"{property_data.noi:,}円" if property_data.noi else "未入力"} |
| 稼働率 | {f"{property_data.occupancy_rate:.0%}" if property_data.occupancy_rate else "未入力"} |
| 表面利回り | {f"{property_data.gross_yield:.1%}" if property_data.gross_yield else "未入力"} |
| 実質利回り | {f"{property_data.net_yield:.1%}" if property_data.net_yield else "未入力"} |
| 目標利回り（判定基準） | {target_yield:.1%} |
| 収益還元価格 | {income_value_text} |
| 売出価格 / 収益還元価格 | {price_result.get('ratio') or '算出不可'} |

**価格コメント：**
{price_result.get('comment')}

---
"""

        # 賃料アップサイドセクション（market_annual_income がある場合のみ）
        if property_data.market_annual_income and property_data.actual_income:
            upside_ratio = property_data.actual_income / property_data.market_annual_income
            upside_pct = round((1 - upside_ratio) * 100, 1)
            if upside_pct > 0:
                report += f"""
## 賃料アップサイド分析

| 項目 | 金額 |
|---|---|
| 現況年収 | {property_data.actual_income:,}円 |
| 相場年収（入力値） | {property_data.market_annual_income:,}円 |
| 現況/相場比 | {round(upside_ratio * 100, 1)}%（相場比{upside_pct}%低い） |
| 退去後アップサイド | 年{property_data.market_annual_income - property_data.actual_income:,}円のNOI改善余地 |

> 💡 現況賃料が相場を{upside_pct}%下回っており、退去後の賃料改定によるNOI改善ポテンシャルがあります。

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

        # セクション3-C: デベロッパー用地逆算分析（土地の場合）
        if dev_land_result is not None:
            floor_sqm = dev_land_result.estimated_floor_area_sqm or 0
            floor_tsubo = dev_land_result.estimated_floor_area_tsubo or 0
            total_sales = dev_land_result.total_sales_revenue or 0
            const_cost = dev_land_result.construction_cost or 0
            dev_exp = dev_land_result.dev_expenses or 0
            dev_profit = dev_land_result.dev_profit_target or 0
            dev_max = dev_land_result.dev_max_land_price
            dev_tsubo = dev_land_result.dev_land_price_per_tsubo
            dev_max_text = f"{dev_max:,}円" if dev_max else "算出不可"
            dev_tsubo_text = f"{dev_tsubo:,}円/坪" if dev_tsubo else "算出不可"
            report += f"""
## 3-C. デベロッパー用地逆算分析

| 項目 | 内容 |
|---|---|
| 開発タイプ | {dev_land_result.dev_type} |
| 想定延床面積 | {floor_tsubo:.1f}坪 / {floor_sqm:.0f}㎡ |
| 想定総販売額 | {total_sales:,}円 |
| 建築費 | {const_cost:,}円 |
| デベ費用・利益 | {dev_exp + dev_profit:,}円 |
| **デベ最大買値** | **{dev_max_text}** |
| デベ適正坪単価 | {dev_tsubo_text} |
| 価格評価 | **{dev_land_result.price_evaluation}** |
| 推奨判断 | **{dev_land_result.recommendation}** |

> {dev_land_result.comment}

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

        # セクション8: 最終結論（実データ反映）
        rank = score_result["rank"]
        total_score = score_result["total_score"]
        judgement = score_result["judgement"]
        price_status = price_result.get("status", "判定不可")
        price_ratio = price_result.get("ratio")

        # ランク別アクション強度
        action_intensity = {
            "S": "今すぐ動いてください。このランクの案件は取り逃すと後悔します。",
            "A": "積極的に動く価値があります。条件確認と買主打診を同時進行してください。",
            "B": "指値交渉が決め手です。売主の最低ラインを早急に確認してください。",
            "C": "情報不足または条件不整合があります。追加確認後に再判断してください。",
            "D": "営業リソースを投入すべきではありません。状況変化があれば再評価してください。",
        }.get(rank, "上記判断に従って対応してください。")

        price_ratio_text = f"（売出価格は収益還元価格の{price_ratio}倍）" if price_ratio else ""
        risk_count = len(risks)
        risk_summary = f"リスク検出数：{risk_count}件" if risk_count > 0 else "重大リスクなし"

        land_note = ""
        if component_scores.get("land_value_covers_price"):
            land_note = " 土地値だけで売値をカバーできており、建物価値をゼロと見ても損失リスクが低い点も評価材料です。"

        upside_note = ""
        if (property_data.market_annual_income and property_data.actual_income
                and property_data.actual_income < property_data.market_annual_income):
            upside_diff = property_data.market_annual_income - property_data.actual_income
            upside_note = f" 賃料アップサイドは年{upside_diff:,}円のNOI改善余地があります。"

        report += f"""

---

## 8. 最終結論

**ランク {rank}（{total_score}点）— {judgement}**

本案件の価格判定は「**{price_status}**」{price_ratio_text}。{risk_summary}。{upside_note}{land_note}

{action_intensity}
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

        # セクション10: 次の一手（next_action_resultがある場合）
        if next_action_result is not None:
            report += "\n---\n\n## 10. 次の一手（具体的行動計画）\n\n"

            if next_action_result.today_actions:
                report += "### 今日中にやること\n\n"
                for a in next_action_result.today_actions:
                    report += (
                        f"- **[優先度{a.priority}]** {a.action}\n"
                        f"  - 対象: {a.target}\n"
                        f"  - 期待効果: {a.expected_outcome}\n"
                    )
                report += "\n"

            if next_action_result.week_actions:
                report += "### 今週中にやること\n\n"
                for a in next_action_result.week_actions:
                    report += (
                        f"- **[優先度{a.priority}]** {a.action}\n"
                        f"  - 対象: {a.target}\n"
                        f"  - 期待効果: {a.expected_outcome}\n"
                    )
                report += "\n"

            if next_action_result.month_actions:
                report += "### 今月中・状況次第でやること\n\n"
                for a in next_action_result.month_actions:
                    report += (
                        f"- **[優先度{a.priority}]** {a.action}\n"
                        f"  - 対象: {a.target}\n"
                        f"  - 期待効果: {a.expected_outcome}\n"
                    )
                report += "\n"

            if next_action_result.information_gaps:
                report += "### 情報不足リスト（今すぐ確認）\n\n"
                for gap in next_action_result.information_gaps:
                    report += f"- {gap}\n"
                report += "\n"

            if next_action_result.quick_message:
                report += "### 紹介元への返信テンプレ\n\n"
                report += f"```\n{next_action_result.quick_message}\n```\n"

        report += "\n---\n\n"
        report += "【免責事項】本分析レポートは参考情報であり、投資助言ではありません。投資判断はご自身の責任で行ってください。\n"

        return report
