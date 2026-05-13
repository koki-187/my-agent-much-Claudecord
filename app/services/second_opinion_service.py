"""
F2: AI Second Opinion (Q&A) サービス

分析結果を context として注入したまま、ユーザーが
「この案件、銀行融資通るか不安。どう思う？」のような自由質問を投げられる。
分析結果のすべての PropertyData / 各エンジン出力 / リスクリスト等を
system prompt に注入することで、的確で根拠のあるセカンドオピニオンを返す。
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def _summarize_analysis_context(
    property_data: Any,
    score_result: Optional[dict] = None,
    price_result: Optional[dict] = None,
    finance_result: Optional[Any] = None,
    risks: Optional[list[dict]] = None,
    component_scores: Optional[dict] = None,
    rosenka_result: Optional[Any] = None,
    exit_result: Optional[Any] = None,
    target_yield: Optional[float] = None,
) -> str:
    """分析結果のすべてを LLM 投入用の構造化テキストに変換"""
    lines: list[str] = []

    # PropertyData
    pd = property_data
    asset_type_val = pd.asset_type.value if hasattr(pd.asset_type, "value") else str(pd.asset_type)
    lines.append("## 物件情報")
    lines.append(f"- 物件名: {getattr(pd, 'property_name', '') or '(未設定)'}")
    lines.append(f"- 所在地: {pd.address}")
    lines.append(f"- 種別: {asset_type_val}")
    lines.append(f"- 売出価格: {pd.price:,}円")
    if getattr(pd, "noi", None):
        lines.append(f"- NOI: {pd.noi:,}円")
    if getattr(pd, "gross_yield", None):
        lines.append(f"- 表面利回り: {pd.gross_yield*100:.2f}%")
    if getattr(pd, "actual_income", None):
        lines.append(f"- 現況年収: {pd.actual_income:,}円")
    if getattr(pd, "built_year", None):
        lines.append(f"- 築年: {pd.built_year}年")
    if getattr(pd, "structure", None):
        lines.append(f"- 構造: {pd.structure}")
    if getattr(pd, "land_area_sqm", None):
        lines.append(f"- 土地面積: {pd.land_area_sqm}㎡")
    if getattr(pd, "building_area_sqm", None):
        lines.append(f"- 建物面積: {pd.building_area_sqm}㎡")
    if getattr(pd, "occupancy_rate", None):
        lines.append(f"- 稼働率: {pd.occupancy_rate*100:.1f}%")
    if getattr(pd, "broker_chain_count", None) is not None:
        lines.append(f"- 商流段数: {pd.broker_chain_count}")
    if getattr(pd, "seller_motivation", None):
        lines.append(f"- 売主温度感: {pd.seller_motivation}")
    if getattr(pd, "seller_reason", None):
        lines.append(f"- 売却理由: {pd.seller_reason}")
    if getattr(pd, "road_access", None):
        lines.append(f"- 接道: {pd.road_access}")

    # 総合判定
    if score_result:
        lines.append("\n## 総合判定")
        lines.append(f"- ランク: {score_result.get('rank')}")
        lines.append(f"- 総合スコア: {score_result.get('total_score')}/100")
        lines.append(f"- 判断: {score_result.get('judgement')}")
        if score_result.get("deal_breaker_reasons"):
            lines.append("- ディールブレーカー:")
            for r in score_result["deal_breaker_reasons"]:
                lines.append(f"  - {r}")

    # 内訳スコア
    if component_scores:
        lines.append("\n## スコア内訳 (0-100)")
        for k, v in component_scores.items():
            if isinstance(v, (int, float)):
                lines.append(f"- {k}: {v}")
            elif isinstance(v, bool):
                lines.append(f"- {k}: {'YES' if v else 'NO'}")

    # 価格判定
    if price_result:
        lines.append("\n## 価格妥当性")
        lines.append(f"- 状態: {price_result.get('status')}")
        if price_result.get("ratio") is not None:
            lines.append(f"- 価格÷収益還元価格: {price_result['ratio']:.3f}")
        if price_result.get("income_value"):
            lines.append(f"- 収益還元価格: {price_result['income_value']:,}円")
        if target_yield:
            lines.append(f"- 目標利回り: {target_yield*100:.2f}%")
        if price_result.get("comment"):
            lines.append(f"- コメント: {price_result['comment']}")

    # 融資シミュ
    if finance_result is not None:
        lines.append("\n## 融資シミュレーション")
        for fld in ("loan_amount", "self_funds", "ltv", "monthly_payment",
                    "dscr_base", "dscr_stress", "feasibility", "comment", "evaluation"):
            v = getattr(finance_result, fld, None)
            if v is not None and v != "":
                lines.append(f"- {fld}: {v}")

    # 路線価
    if rosenka_result is not None:
        lines.append("\n## 路線価分析")
        for fld in ("land_price_per_sqm", "estimated_land_value", "matched_area", "comment"):
            v = getattr(rosenka_result, fld, None)
            if v is not None and v != "":
                lines.append(f"- {fld}: {v}")

    # 出口戦略
    if exit_result is not None:
        lines.append("\n## 出口戦略")
        for fld in ("short_term_irr", "mid_term_irr", "long_term_irr",
                    "short_term_sell_price", "mid_term_sell_price", "long_term_sell_price",
                    "recommended_action", "comment"):
            v = getattr(exit_result, fld, None)
            if v is not None and v != "":
                lines.append(f"- {fld}: {v}")

    # リスク
    if risks:
        lines.append("\n## 検出されたリスク")
        for r in risks:
            lvl = r.get("level", "?").upper()
            t = r.get("type", "")
            m = r.get("message", "")
            lines.append(f"- [{lvl}] {t}: {m}")

    return "\n".join(lines)


_SYSTEM_PROMPT_TEMPLATE = """あなたは不動産仲介業者向けの仕入れ判断アシスタントです。
ユーザー（プロの仲介営業）が、ある物件の分析結果について追加の質問を投げてきます。
以下の【分析結果コンテキスト】に基づいて、根拠を示しながら、率直で実務的なセカンドオピニオンを返してください。

回答方針：
- 不動産仲介・投資のプロ語彙で簡潔に。回りくどい説明は不要
- 必ず分析結果に含まれる数値・事実を根拠として引用する（例: "DSCR 0.73 は…"）
- 結論ファースト。最初の1文で「YES/NO/条件次第」を明示
- 分析結果に含まれない情報は推測せず「データ不足のため要確認」と明示
- 日本の金融機関名・実務慣行・最新の市況感を踏まえる
- 必要に応じて 3〜5 の箇条書きで論点整理
- 1回答あたり 400 字以内が目安

【分析結果コンテキスト】
{context}
"""


class SecondOpinionService:
    """分析結果を context として持ったまま自由質問を受け付ける Q&A サービス"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service if llm_service is not None else LLMService()
        self._system_cache: Optional[str] = None
        self._context_cache: Optional[str] = None

    def is_available(self) -> bool:
        return self._llm.is_available()

    def set_context(self, **analysis_results) -> None:
        """分析結果を投入して system prompt を構築・キャッシュ"""
        self._context_cache = _summarize_analysis_context(**analysis_results)
        self._system_cache = _SYSTEM_PROMPT_TEMPLATE.format(context=self._context_cache)

    def get_context_summary(self) -> str:
        """セッションコンテキストの要約 (デバッグ用)"""
        return self._context_cache or "(未設定)"

    def ask(self, question: str, chat_history: list[dict] | None = None) -> str:
        """
        ユーザーの質問に回答を返す。
        chat_history: [{"role": "user"|"assistant", "content": "..."}, ...]
        """
        if not self.is_available():
            return "LLM が利用できないため Second Opinion を生成できません。Streamlit Secrets を確認してください。"
        if not self._system_cache:
            return "分析結果がまだ投入されていません。先に物件分析を実行してください。"

        messages: list[dict] = []
        for h in (chat_history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": question})

        try:
            client = self._llm.client
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                system=[{"type": "text", "text": self._system_cache,
                         "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            )
            return response.content[0].text.strip()
        except RuntimeError as e:
            if "RATE_LIMIT_429" in str(e):
                return ("⏳ APIレート制限中です。1〜2分待ってから再試行してください。")
            logger.error("Second Opinion LLM error: %s", e, exc_info=True)
            return f"LLM呼出エラー: {type(e).__name__}: {e}"
        except Exception as e:
            logger.error("Second Opinion error: %s", e, exc_info=True)
            return f"エラー: {type(e).__name__}: {e}"


# シングルトン
_singleton: Optional[SecondOpinionService] = None


def get_second_opinion_service() -> SecondOpinionService:
    global _singleton
    if _singleton is None:
        _singleton = SecondOpinionService()
    return _singleton
