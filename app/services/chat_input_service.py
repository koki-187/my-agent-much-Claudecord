"""
chat_input_service.py
────────────────────
ステートレスな会話型物件入力サービス。
ユーザー発話 + チャット履歴 + 現在の部分データを受け取り、
Gemini（フォールバック付きLLMService経由）で次のアクションを返す。

API: ChatInputService.next_turn(user_message, chat_history, partial_data) -> dict
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# 必須フィールド定義（label: fieldキー）
# ────────────────────────────────────────────────────────────────────────────
CRITICAL_FIELDS = {
    "所在地": "address",
    "売出価格": "price",
    "物件種別": "asset_type",
    "NOI（実質収益）": "noi",
    "表面利回り": "gross_yield",
    "築年": "built_year",
    "商流段数": "broker_chain_count",
    "売主温度感": "seller_motivation",
}

RECOMMENDED_FIELDS = {
    "建物面積": "building_area_sqm",
    "土地面積": "land_area_sqm",
    "構造": "structure",
    "接道情報": "road_access",
    "稼働率": "occupancy_rate",
    "想定修繕費": "planned_repairs_cost",
}

SYSTEM_PROMPT = """あなたは不動産仲介営業の専門家アシスタントです。
ユーザーが貼り付けるPDF内容・メール本文・URL情報などから物件情報を会話形式で収集します。

## あなたの役割
1. ユーザーの発話から物件情報を自動抽出する
2. 不足している重要項目があれば、1〜2項目だけ丁寧に聞く
3. 7往復以内に入力を完成させる
4. 「不明」「わからない」という回答も許容して先に進む

## 優先度（必須項目）
- 所在地（address）
- 売出価格（price、円）
- 物件種別（asset_type）: 一棟マンション/一棟アパート/区分マンション/戸建て/土地/商業・店舗/オフィス/工場・倉庫
- NOI（noi、円）または表面利回り（gross_yield、0.0〜1.0）
- 築年（built_year、西暦）
- 商流段数（broker_chain_count、整数）
- 売主温度感（seller_motivation）

## 推奨項目（あれば良い）
- 建物面積（building_area_sqm、㎡）
- 土地面積（land_area_sqm、㎡）
- 構造（structure）
- 接道情報（road_access）
- 稼働率（occupancy_rate、0.0〜1.0）
- 想定修繕費（planned_repairs_cost、円）

## 応答ルール
- 情報を貼られたらまず自動抽出を試みる
- 不足があれば「〜はいかがですか？」と1〜2項目だけ質問する
- 必須項目がすべて揃ったら「全項目確認完了です！」と宣言する
- JSON抽出は返答内に含めない（バックエンドで処理する）
- 簡潔・親切・プロフェッショナルな口調で
- 日本語で返答する

## 重要
- partial_dataに既に値があるフィールドは再度聞かない
- 一度に複数の質問を並べない（最大2項目）
- 必須項目が5項目以上揃ったら積極的に完成宣言を検討する
"""

EXTRACT_PROMPT_TEMPLATE = """以下の会話と現在の部分データから、新たに抽出できる物件情報フィールドをJSON形式で返してください。

## 現在の部分データ（既確定）
{partial_json}

## 最新のユーザー発話
{user_message}

## 抽出ルール
- 既にpartial_dataにある値は含めない（上書きしない）
- 今回の発話から新たに読み取れる値のみ返す
- 不明な場合はフィールドを含めない（nullにしない）
- 数値は適切な型で返す（価格は円、利回りは0.0〜1.0、稼働率は0.0〜1.0）

## 抽出可能フィールド一覧
- property_name: 物件名（文字列）
- asset_type: 物件種別（"一棟マンション"/"一棟アパート"/"区分マンション"/"戸建て"/"土地"/"商業・店舗"/"オフィス"/"工場・倉庫"）
- address: 所在地（文字列）
- price: 売出価格（円、整数）
- land_area_sqm: 土地面積（㎡、浮動小数）
- building_area_sqm: 建物面積（㎡、浮動小数）
- structure: 構造（文字列）
- built_year: 築年（西暦整数）
- gross_income: 満室想定年収（円、整数）
- actual_income: 現況年収（円、整数）
- noi: NOI（円、整数）
- occupancy_rate: 稼働率（0.0〜1.0）
- gross_yield: 表面利回り（0.0〜1.0）
- net_yield: 実質利回り（0.0〜1.0）
- zoning: 用途地域（文字列）
- road_access: 接道情報（文字列）
- walk_minutes_to_station: 最寄駅徒歩分（整数）
- current_status: 現況（文字列）
- seller_reason: 売却理由（文字列）
- seller_motivation: 売主温度感（文字列）
- broker_chain_count: 商流段数（整数）
- planned_repairs_cost: 想定修繕費（円、整数）
- legal_notes: 法的懸念（文字列）
- notes: その他メモ（文字列）

JSONのみ出力してください。抽出できる情報がない場合は {{}} を返してください。"""

COMPLETION_CHECK_PROMPT = """以下の物件データで必須項目がどれだけ揃っているか判定してください。

## 現在のデータ
{partial_json}

## 必須項目
- address（所在地）
- price（売出価格）
- asset_type（物件種別）
- noi または gross_yield（収益指標）
- built_year（築年）
- broker_chain_count（商流段数）
- seller_motivation（売主温度感）

## 返答形式（JSONのみ）
{{
  "completion_confidence": 0.0〜1.0の数値（0.85以上で完成推奨）,
  "missing_critical": ["不足している必須項目のラベル名の配列"],
  "is_complete": true/false,
  "ai_status_line": "現在のAI判断を1行で（例: 住所と価格は確認できました。次にNOIを聞きます。）"
}}"""


class ChatInputService:
    """
    ステートレスな会話型物件入力サービス。
    セッション状態の管理は呼び出し側（Streamlit）が行う。
    """

    def __init__(self, llm_service=None):
        """
        llm_service: LLMService インスタンス（省略時は内部で生成）
        """
        if llm_service is not None:
            self._llm = llm_service
        else:
            from app.services.llm_service import LLMService
            self._llm = LLMService()

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def next_turn(
        self,
        user_message: str,
        chat_history: list[dict],
        partial_data: dict,
    ) -> dict:
        """
        会話の次のターンを処理する。

        Parameters
        ----------
        user_message : str
            ユーザーの最新発話
        chat_history : list[dict]
            過去の会話履歴 [{"role": "user"|"assistant", "content": "..."}, ...]
        partial_data : dict
            現時点で確定している PropertyData フィールド

        Returns
        -------
        dict:
            {
                "assistant_message": str,        # AIの返答
                "extracted_fields": dict,        # 今回新たに抽出されたフィールド
                "completion_confidence": float,  # 0.0〜1.0
                "is_complete": bool,
                "missing_critical": list[str],   # 不足している重要フィールドのlabel
                "ai_status_line": str,           # 現在のAI判断を1行で
            }
        """
        if not self._llm.is_available():
            return self._no_llm_response()

        # Step 1: 発話からフィールド抽出
        extracted_fields = self._extract_fields(user_message, partial_data)

        # Step 2: 新しいpartial_dataをマージ
        merged_data = {**partial_data, **extracted_fields}

        # Step 3: 完成度チェック
        completion_info = self._check_completion(merged_data)

        # Step 4: AI返答を生成（会話継続 or 完成宣言）
        assistant_message = self._generate_response(
            user_message=user_message,
            chat_history=chat_history,
            partial_data=merged_data,
            completion_info=completion_info,
        )

        return {
            "assistant_message": assistant_message,
            "extracted_fields": extracted_fields,
            "completion_confidence": completion_info.get("completion_confidence", 0.0),
            "is_complete": completion_info.get("is_complete", False),
            "missing_critical": completion_info.get("missing_critical", []),
            "ai_status_line": completion_info.get("ai_status_line", "情報を収集しています..."),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    def _extract_fields(self, user_message: str, partial_data: dict) -> dict:
        """ユーザー発話から新規フィールドを抽出する"""
        partial_json = json.dumps(partial_data, ensure_ascii=False, indent=2)
        prompt = EXTRACT_PROMPT_TEMPLATE.format(
            partial_json=partial_json,
            user_message=user_message,
        )
        try:
            response = self._llm.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=[{
                    "type": "text",
                    "text": "あなたは不動産物件情報の抽出専門家です。JSONのみ返してください。",
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = self._clean_json(raw)
            extracted = json.loads(raw)
            if not isinstance(extracted, dict):
                return {}
            # 既存フィールドは上書きしない
            return {k: v for k, v in extracted.items() if k not in partial_data and v is not None}
        except Exception as e:
            logger.warning("フィールド抽出エラー: %s", e)
            return {}

    def _check_completion(self, partial_data: dict) -> dict:
        """現在のデータで完成度を判定する"""
        # ルールベースでまず判定
        filled_critical = []
        missing_critical = []

        for label, field_key in CRITICAL_FIELDS.items():
            val = partial_data.get(field_key)
            # noi と gross_yield はどちらか一方でOK
            if label == "NOI（実質収益）":
                has_noi = bool(partial_data.get("noi"))
                has_yield = bool(partial_data.get("gross_yield"))
                if has_noi or has_yield:
                    filled_critical.append(label)
                else:
                    missing_critical.append(label)
                continue
            if val is not None and val != "" and val != 0:
                filled_critical.append(label)
            else:
                missing_critical.append(label)

        total = len(CRITICAL_FIELDS)
        filled = len(filled_critical)
        confidence = filled / total

        # 0.85以上で完成とみなす（7項目中6項目でOK）
        is_complete = confidence >= 0.85

        # AI状態ライン生成（ルールベース）
        if is_complete:
            status_line = "全必須項目を確認しました。分析実行の準備が整いました。"
        elif filled >= 4:
            next_missing = missing_critical[0] if missing_critical else "追加情報"
            status_line = f"{filled}項目を確認済みです。次に{next_missing}を確認します。"
        elif filled >= 2:
            confirmed = "・".join(filled_critical[:2])
            status_line = f"{confirmed}を確認しました。引き続き情報を収集しています。"
        else:
            status_line = "物件情報を収集しています。詳細をお聞かせください。"

        return {
            "completion_confidence": confidence,
            "is_complete": is_complete,
            "missing_critical": missing_critical,
            "ai_status_line": status_line,
        }

    def _generate_response(
        self,
        user_message: str,
        chat_history: list[dict],
        partial_data: dict,
        completion_info: dict,
    ) -> str:
        """LLMで会話の返答を生成する"""
        partial_json = json.dumps(partial_data, ensure_ascii=False)
        missing = completion_info.get("missing_critical", [])
        is_complete = completion_info.get("is_complete", False)

        # システムプロンプトに現在の状況を付加
        context_addendum = f"""
## 現在の確定データ（JSON）
{partial_json}

## 不足している必須項目
{', '.join(missing) if missing else 'なし（全て揃っています）'}

## 完成度
{completion_info.get('completion_confidence', 0.0):.0%}

{'## 指示: 全項目が揃いました。「全項目確認完了です！分析実行をお待ちください。」と伝えてください。' if is_complete else '## 指示: 不足項目を1〜2項目だけ質問してください。'}
"""
        system_content = SYSTEM_PROMPT + context_addendum

        # 会話履歴をLLM用に変換（最新10往復まで）
        messages = []
        for msg in chat_history[-20:]:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": msg.get("content", "")})

        # 最新のユーザー発話を追加
        messages.append({"role": "user", "content": user_message})

        try:
            response = self._llm.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                system=[{
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
            )
            return response.content[0].text.strip()
        except RuntimeError as e:
            if "RATE_LIMIT_429" in str(e):
                raise
            logger.error("AI返答生成エラー: %s", e)
            return "申し訳ありません、一時的にエラーが発生しました。もう一度お試しください。"
        except Exception as e:
            logger.error("AI返答生成エラー: %s", e)
            return "申し訳ありません、一時的にエラーが発生しました。もう一度お試しください。"

    @staticmethod
    def _clean_json(raw: str) -> str:
        """JSONブロックからコードフェンスを除去する"""
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return raw

    @staticmethod
    def _no_llm_response() -> dict:
        return {
            "assistant_message": "LLMサービスが設定されていません。GEMINI_API_KEY または ANTHROPIC_API_KEY を設定してください。",
            "extracted_fields": {},
            "completion_confidence": 0.0,
            "is_complete": False,
            "missing_critical": list(CRITICAL_FIELDS.keys()),
            "ai_status_line": "LLMサービス未設定",
        }
