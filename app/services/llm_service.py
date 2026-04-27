import os
import json
from typing import Optional
from app.models.property import PropertyData, AssetType


def _get_client():
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return None


EXTRACT_SYSTEM_PROMPT = """あなたは不動産仲介営業の専門家です。
与えられた物件情報テキストから、構造化されたJSONデータを抽出してください。

出力はJSON形式のみ。以下のフィールドを可能な限り抽出してください：
- property_name: 物件名
- asset_type: 物件種別（"一棟マンション", "一棟アパート", "区分マンション", "戸建て", "土地", "商業・店舗", "オフィス", "工場・倉庫" のいずれか）
- address: 所在地
- price: 売出価格（円、数値のみ）
- land_area_sqm: 土地面積（数値）
- building_area_sqm: 建物面積（数値）
- structure: 構造
- built_year: 築年（西暦数値）
- gross_income: 満室想定年収（円）
- actual_income: 現況年収（円）
- noi: NOI（円）
- occupancy_rate: 稼働率（0.0〜1.0）
- gross_yield: 表面利回り（0.0〜1.0）
- zoning: 用途地域
- building_coverage_ratio: 建蔽率（0.0〜1.0）
- floor_area_ratio: 容積率（0.0〜10.0）
- road_access: 接道情報
- current_status: 現況
- seller_reason: 売却理由
- seller_motivation: 売主温度感
- broker_chain_count: 商流段数（整数）
- planned_repairs_cost: 想定修繕費（円）
- legal_notes: 法的懸念

不明なフィールドはnullにしてください。JSONのみ出力してください。"""


ADVICE_SYSTEM_PROMPT = """あなたは経験豊富な不動産仲介ベテラン営業マンです。
提供された案件調査レポートを読み、以下の観点から実践的なアドバイスを日本語で提供してください：

1. **この案件の最大のチャンスポイント**（1〜2点）
2. **この案件の最大の落とし穴**（1〜2点）
3. **次に取るべき具体的なアクション**（3ステップ）
4. **指値交渉の具体的な根拠と切り口**

簡潔かつ実践的に、200字以内で各項目を答えてください。"""


class LLMService:
    def __init__(self):
        self.client = _get_client()
        self.available = self.client is not None

    def extract_property_from_text(self, text: str) -> Optional[PropertyData]:
        if not self.available:
            return None
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=EXTRACT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"以下の物件情報からデータを抽出してください：\n\n{text}"}]
            )
            raw = response.content[0].text.strip()
            # JSONブロックを取り出す
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw)
            # asset_typeの正規化
            if "asset_type" in data and data["asset_type"]:
                try:
                    data["asset_type"] = AssetType(data["asset_type"])
                except ValueError:
                    data["asset_type"] = AssetType.APARTMENT_WHOLE

            # addressとpriceが必須
            if not data.get("address"):
                data["address"] = "不明"
            if not data.get("price"):
                data["price"] = 0

            return PropertyData(**{k: v for k, v in data.items() if v is not None})
        except Exception as e:
            print(f"[LLM抽出エラー] {e}")
            return None

    def generate_advice(self, report: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=ADVICE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"以下のレポートにアドバイスをください：\n\n{report[:3000]}"}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"[LLMアドバイスエラー] {e}")
            return None

    def is_available(self) -> bool:
        return self.available
