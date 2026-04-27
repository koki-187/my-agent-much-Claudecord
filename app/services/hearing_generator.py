from typing import List, Optional
from app.models.property import AssetType


class HearingGenerator:
    def generate_questions(self, risks: List[dict], asset_type: Optional[AssetType] = None) -> List[str]:
        questions = [
            "売主の売却理由は何ですか？",
            "売主は価格交渉に応じる余地がありますか？",
            "売主の最低売却希望価格は確認済みですか？",
            "現在の申込状況・検討者の有無を教えてください。",
            "レントロールは最新ですか？",
            "現況賃料と相場賃料に乖離はありますか？",
            "修繕履歴と今後の修繕予定はありますか？",
            "固定資産税・管理費・修繕費などの運営費は確認済みですか？",
            "金融機関の評価が出た事例はありますか？",
            "出口として想定できる買主層は誰ですか？"
        ]

        for risk in risks:
            risk_type = risk.get("type")

            if risk_type == "商流リスク":
                questions.append("売主または元付業者まで直接確認できるルートはありますか？")
                questions.append("商流上、価格交渉の決裁者は誰ですか？")

            if risk_type in ["接道リスク", "接道確認不足"]:
                questions.append("建築基準法上の道路種別と接道幅員を確認済みですか？")
                questions.append("再建築の可否について行政確認済みですか？")
                questions.append("セットバックの有無と面積を確認済みですか？")

            if risk_type == "旧耐震リスク":
                questions.append("耐震診断・耐震補強履歴はありますか？")
                questions.append("過去に融資付けできた金融機関はありますか？")
                questions.append("旧耐震を許容する買主候補は想定できますか？")

            if risk_type == "稼働率リスク":
                questions.append("空室の原因は賃料・設備・立地・管理のどれですか？")
                questions.append("募集条件、AD、広告状況を確認済みですか？")

            if risk_type == "修繕リスク":
                questions.append("修繕見積書は取得済みですか？")
                questions.append("修繕費を価格交渉材料にできますか？")

            if risk_type == "売却理由不明":
                questions.append("売主が今売る必要性はどの程度ありますか？")
                questions.append("売却期限や資金需要はありますか？")

        # 物件種別固有の質問
        if asset_type == AssetType.LAND:
            questions.append("路線価・公示地価の確認は取れていますか？")
            questions.append("土壌汚染調査の履歴はありますか？")
            questions.append("埋設物・地中障害の有無は確認済みですか？")
            questions.append("開発行為の許可見込みは確認済みですか？")
        elif asset_type in (AssetType.COMMERCIAL, AssetType.OFFICE):
            questions.append("テナントの業績・財務状況は問題ありませんか？")
            questions.append("賃料改定条項の内容を確認済みですか？")
            questions.append("原状回復義務の範囲は明確ですか？")
        elif asset_type == AssetType.FACTORY:
            questions.append("環境基準・騒音規制の遵守状況は確認済みですか？")
            questions.append("危険物・有害物質の保管履歴はありますか？")
            questions.append("動力電気・ガスの供給容量は十分ですか？")

        return list(dict.fromkeys(questions))
