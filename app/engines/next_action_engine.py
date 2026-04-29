from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NextAction:
    """具体的なアクション1件"""
    timing: str         # 今日中/今週中/今月中/保留
    action: str         # 具体的なアクション内容
    target: str         # 誰に/何に対して
    expected_outcome: str  # なぜやるか・何がわかるか
    priority: int       # 1=最重要, 2=重要, 3=参考


@dataclass
class NextActionResult:
    """次の一手生成結果"""
    go_no_go: str                      # 追う/条件次第/捨てる
    go_no_go_reason: str               # 判断理由（1文）
    information_gaps: List[str]        # 今すぐ確認すべき不足情報
    today_actions: List[NextAction]    # 今日中にやること
    week_actions: List[NextAction]     # 今週中にやること
    month_actions: List[NextAction]    # 今月中・状況次第でやること
    deal_breaker_check: List[str]      # これがあれば即捨て条件チェック
    quick_message: str                 # 紹介元に送る想定返信文（テンプレ）


class NextActionEngine:
    """
    「次の一手」生成エンジン

    スコア・リスク・物件種別・情報の欠落から
    「今日何をすべきか」を具体的なアクションで出力する。
    """

    def generate(
        self,
        property_data,           # PropertyData
        score_result: dict,
        risks: List[dict],
        price_result: dict,
        finance_result=None,
        rosenka_result=None,
        dev_land_result=None,    # DeveloperLandEngine の結果（土地の場合）
        offer_result: dict = None,
    ) -> NextActionResult:
        from app.models.property import AssetType

        rank = score_result.get("rank", "C")
        asset_type = property_data.asset_type
        address = property_data.address or ""
        price = property_data.price

        # ディールブレーカーチェック
        deal_breakers = score_result.get("deal_breaker_reasons", [])
        critical_risks = [r for r in risks if r.get("level") == "critical"]

        # 情報不足リスト
        gaps = self._identify_gaps(property_data)

        # Go/No-Go判断
        go_no_go, reason = self._determine_go_no_go(
            rank, deal_breakers, critical_risks, price_result, finance_result, dev_land_result
        )

        # アクション生成
        today = self._generate_today_actions(property_data, rank, gaps, risks, go_no_go, dev_land_result)
        week = self._generate_week_actions(property_data, rank, risks, go_no_go, price_result, offer_result)
        month = self._generate_month_actions(property_data, rank, go_no_go)

        # 紹介元への返信テンプレ
        quick_msg = self._generate_quick_message(
            property_data, go_no_go, offer_result, dev_land_result, gaps
        )

        return NextActionResult(
            go_no_go=go_no_go,
            go_no_go_reason=reason,
            information_gaps=gaps,
            today_actions=today,
            week_actions=week,
            month_actions=month,
            deal_breaker_check=deal_breakers,
            quick_message=quick_msg,
        )

    def _identify_gaps(self, property_data) -> List[str]:
        """不足している重要情報を列挙"""
        from app.models.property import AssetType
        gaps = []

        if not property_data.land_area_sqm:
            gaps.append("土地面積（㎡・坪）→ 指値計算・デベ打診に必須")
        if not property_data.floor_area_ratio:
            gaps.append("容積率 → 開発規模・収益性の根拠")
        if not property_data.road_access:
            gaps.append("接道状況（道路種別・幅員・接道長さ）→ 建築可否・融資可否に直結")
        if not property_data.seller_reason:
            gaps.append("売却理由 → 価格交渉余地・売主温度感の判断根拠")
        if not property_data.seller_motivation:
            gaps.append("売主温度感（急いでいるか？）→ 指値交渉の可否")
        if not property_data.broker_chain_count:
            gaps.append("商流段数（直接か？間に何社いるか？）→ 交渉経路の確認")
        if property_data.asset_type != property_data.asset_type.LAND:
            if not property_data.noi:
                gaps.append("NOI（実質収益）→ 収益還元価格の計算に必須")
            if not property_data.built_year:
                gaps.append("築年数 → 旧耐震・修繕・融資可否の判断")
        if property_data.asset_type in (property_data.asset_type.COMMERCIAL, property_data.asset_type.OFFICE):
            if not property_data.lease_expiry:
                gaps.append("賃貸借契約満了日 → テナントリスクの最重要情報")

        return gaps

    def _determine_go_no_go(self, rank, deal_breakers, critical_risks,
                             price_result, finance_result, dev_land_result) -> tuple:
        """Go/No-Go判断と理由"""

        # 開発用地の場合はdev_land_resultを優先
        if dev_land_result:
            rec = dev_land_result.recommendation
            if rec == "追う":
                return "追う", f"デベ適正価格内（{dev_land_result.price_evaluation}）で出口が見える"
            elif rec == "条件次第":
                pct = int((dev_land_result.price_vs_dev_max - 1) * 100) if dev_land_result.price_vs_dev_max else "?"
                return "条件次第", f"デベ最大買値を{pct}%超過。指値交渉次第"
            elif "情報確認" in rec:
                tsubo = dev_land_result.dev_land_price_per_tsubo
                tsubo_str = f"デベ上限坪単価: {tsubo // 10000}万円/坪" if tsubo else "坪単価確認中"
                return "情報確認が必要", f"土地面積未確認のため正確な判断不可。{tsubo_str}。まず面積を確認"
            else:
                return "捨てる（現時点）", f"デベ最大買値を大きく超過。現時点では出口なし"

        if deal_breakers:
            return "条件次第", f"要注意: {deal_breakers[0]}"

        if critical_risks:
            return "条件次第", f"重大リスク検出: {critical_risks[0].get('type', '')}"

        if rank in ("S", "A"):
            return "追う", f"総合{rank}ランク。積極的に動く価値あり"
        elif rank == "B":
            price_status = price_result.get("status", "")
            if price_status in ("やや高い", "高すぎる"):
                return "条件次第", f"指値前提。{price_status}水準のため値下げ交渉が必須"
            return "追う", f"Bランクだが条件整備次第で成立の可能性"
        elif rank == "C":
            return "条件次第", f"現時点では様子見。価格改定または追加情報収集後に再評価"
        else:
            return "捨てる（現時点）", f"Dランク。営業リソースを投入すべき案件でない"

    def _generate_today_actions(self, property_data, rank, gaps, risks, go_no_go, dev_land_result) -> List[NextAction]:
        """今日中にやること"""
        actions = []

        # 情報不足の最重要確認
        if gaps:
            for gap in gaps[:2]:  # 上位2件
                actions.append(NextAction(
                    timing="今日中",
                    action=f"紹介元に確認: {gap.split('→')[0].strip()}",
                    target="紹介元担当者",
                    expected_outcome=gap.split('→')[1].strip() if '→' in gap else "判断精度向上",
                    priority=1
                ))

        # 売主温度感・売却理由の確認
        if not property_data.seller_reason or not property_data.seller_motivation:
            actions.append(NextAction(
                timing="今日中",
                action="売主の売却理由と期限を確認（「今すぐ売りたいのか・じっくり待てるのか」）",
                target="紹介元担当者",
                expected_outcome="価格交渉余地と指値幅の把握",
                priority=1
            ))

        # 開発用地の場合
        if dev_land_result:
            if dev_land_result.dev_max_land_price:
                actions.append(NextAction(
                    timing="今日中",
                    action=f"デベロッパーに非公式ヒアリング（「{property_data.address}で坪約{dev_land_result.dev_land_price_per_tsubo // 10000}万円の用地、検討できますか？」）",
                    target="取引先デベロッパー2〜3社",
                    expected_outcome="買える価格帯の感触確認（回答は今週中）",
                    priority=2
                ))

        # 重大リスクがある場合の確認
        critical = [r for r in risks if r.get("level") == "critical"]
        for r in critical[:1]:
            actions.append(NextAction(
                timing="今日中",
                action=f"【重要】{r.get('type', '')}の内容を詳細確認",
                target="紹介元担当者",
                expected_outcome="案件継続可否の判断材料",
                priority=1
            ))

        if not actions:
            actions.append(NextAction(
                timing="今日中",
                action="紹介元に「確認します」と一報を入れ、資料一式を依頼",
                target="紹介元担当者",
                expected_outcome="関係維持・資料収集",
                priority=2
            ))

        return actions

    def _generate_week_actions(self, property_data, rank, risks, go_no_go, price_result, offer_result) -> List[NextAction]:
        """今週中にやること"""
        actions = []
        from app.models.property import AssetType

        if go_no_go in ("追う", "条件次第"):
            # 指値計算・提示
            if offer_result and offer_result.get("low"):
                low = offer_result["low"]
                high = offer_result["high"]
                actions.append(NextAction(
                    timing="今週中",
                    action=f"売主へ指値提示: {low:,}〜{high:,}円の根拠資料を作成し紹介元経由で打診",
                    target="紹介元 → 売主",
                    expected_outcome="売主の最低売却ラインを把握",
                    priority=1
                ))

            # 買主候補へのヒアリング
            actions.append(NextAction(
                timing="今週中",
                action=f"買主候補3社に「{property_data.address}で{property_data.asset_type.value}案件あり。{property_data.price // 10000:,}万円、検討可能か？」と非公式打診",
                target="既存買主候補リスト",
                expected_outcome="出口の具体化（買主がいれば追う価値が上がる）",
                priority=2
            ))

            # 修繕・旧耐震リスクへの対応
            old_seismic = any(r.get("type") == "旧耐震リスク" for r in risks)
            if old_seismic:
                actions.append(NextAction(
                    timing="今週中",
                    action="旧耐震でも融資実績のある金融機関（ノンバンク・地方銀行）に打診",
                    target="取引金融機関",
                    expected_outcome="融資可能性の確認",
                    priority=1
                ))
        else:
            actions.append(NextAction(
                timing="今週中（条件変化待ち）",
                action="案件情報をファイリングし、価格改定の連絡を紹介元に依頼",
                target="紹介元担当者",
                expected_outcome="価格下落時の優先情報入手",
                priority=3
            ))

        return actions

    def _generate_month_actions(self, property_data, rank, go_no_go) -> List[NextAction]:
        """今月中・状況次第"""
        actions = []

        if go_no_go == "追う":
            actions.append(NextAction(
                timing="今月中",
                action="現地調査・建物確認・レントロール確認・固定資産税資料取得",
                target="紹介元 or 直接",
                expected_outcome="デューデリジェンスの開始",
                priority=2
            ))
        elif go_no_go == "条件次第":
            actions.append(NextAction(
                timing="今月中（条件次第）",
                action="価格が指値水準まで下落した場合の即動き体制を整備（買主候補リスト準備）",
                target="社内・買主候補",
                expected_outcome="価格改定時の迅速対応",
                priority=3
            ))

        return actions

    def _generate_quick_message(self, property_data, go_no_go, offer_result, dev_land_result, gaps) -> str:
        """紹介元への想定返信メッセージテンプレ"""
        address = property_data.address or "（所在地）"
        price_man = property_data.price // 10000

        if gaps:
            gap_questions = "\n".join([f"・{g.split('→')[0].strip()}" for g in gaps[:3]])
            return (
                f"【{address}の件】\n"
                f"ご紹介ありがとうございます。早速確認させてください。\n\n"
                f"以下の情報を教えていただけますか？\n{gap_questions}\n\n"
                f"確認でき次第、出口を含めて具体的にご回答します。"
            )

        if go_no_go == "追う":
            offer_str = ""
            if offer_result and offer_result.get("low"):
                offer_str = f"\n指値目安は{offer_result['low'] // 10000:,}万〜{offer_result['high'] // 10000:,}万円で考えています。"
            elif dev_land_result and dev_land_result.dev_max_land_price:
                offer_str = f"\nデベへの打診ベースで{dev_land_result.dev_max_land_price // 10000:,}万円前後が目線です。"
            return (
                f"【{address}の件】\n"
                f"確認しました。積極的に動きます。{offer_str}\n"
                f"まず売主の最低売却ラインを確認させてください。よろしくお願いします。"
            )
        elif go_no_go == "条件次第":
            return (
                f"【{address}の件】\n"
                f"確認しました。現状の{price_man:,}万円は少し厳しい水準です。\n"
                f"売主が価格に柔軟性があれば動ける可能性があります。\n"
                f"売主の最低売却希望を確認いただけますか？"
            )
        else:
            return (
                f"【{address}の件】\n"
                f"確認しました。現時点では出口が見えづらく、難しい状況です。\n"
                f"価格が改定された際には優先的にご連絡ください。引き続きよろしくお願いします。"
            )
