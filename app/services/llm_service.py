import os
import json
from typing import Optional
from app.models.property import PropertyData, AssetType
from app.engines.bulk_extractor import BulkPropertyItem


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


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


BULK_EXTRACT_SYSTEM_PROMPT = """あなたは不動産仲介営業の専門家です。
与えられたテキストから**全ての不動産物件情報**を抽出してください。
1つのリストに複数物件が含まれている場合は全て個別に抽出してください。

出力はJSON配列のみ。各物件を以下のフィールドで表現してください：
- property_name: 物件名（文字列）
- address: 所在地（都道府県〜番地できる限り詳しく）
- station: 最寄駅名
- walk_minutes: 駅徒歩分数（整数、不明はnull）
- price_man: 売出価格（万円の数値、例: 13億3000万円→133000）
- gross_yield_pct: 表面利回り（%の数値、例: 4.01%→4.01）
- built_year: 築年（西暦整数、未完成・予定の場合は完成予定年）
- structure: 構造（RC造/SRC造/鉄骨造/木造等）
- asset_type: 種別（一棟マンション/一棟アパート/区分マンション/戸建て/土地/商業・店舗/オフィス/工場・倉庫）
- units: 戸数（整数、不明はnull）
- land_area_tsubo: 土地面積（坪の数値、不明はnull）
- building_area_tsubo: 延床面積（坪の数値、不明はnull）
- nla_tsubo: 専有面積合計（坪、不明はnull）
- occupancy_pct: 稼働率（0〜100の数値、不明はnull）
- annual_rent_man: 年間賃料（万円、不明はnull）
- rent_per_nla: 坪賃料単価（円/坪、不明はnull）
- broker: 取引態様（売主（S）/代理（W）/仲介等）
- notes: 備考・特記事項

**重要**: 物件が複数ある場合は必ず全て抽出すること。英語表記も日本語に変換して抽出すること。
JSONのみ出力してください。"""


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

    def extract_bulk_properties(self, text: str) -> list[BulkPropertyItem]:
        """
        テキストから複数の物件を一括抽出して BulkPropertyItem リストを返す。
        LLM が使えない場合は空リストを返す（呼び出し側でフォールバック処理）。
        """
        if not self.available:
            return []
        try:
            # テキストが長すぎる場合は先頭15000文字に絞る
            truncated = text[:15000]
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8000,
                system=BULK_EXTRACT_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"以下のテキストから全ての物件情報を抽出してください：\n\n{truncated}"
                }]
            )
            raw = response.content[0].text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data_list = json.loads(raw)
            if isinstance(data_list, dict) and "properties" in data_list:
                data_list = data_list["properties"]

            items: list[BulkPropertyItem] = []
            for idx, d in enumerate(data_list):
                item = BulkPropertyItem(
                    property_name=str(d.get("property_name") or ""),
                    address=str(d.get("address") or ""),
                    station=str(d.get("station") or ""),
                    walk_minutes=_safe_int(d.get("walk_minutes")),
                    price_man=_safe_float(d.get("price_man")),
                    gross_yield_pct=_safe_float(d.get("gross_yield_pct")),
                    built_year=_safe_int(d.get("built_year")),
                    structure=str(d.get("structure") or ""),
                    asset_type=str(d.get("asset_type") or ""),
                    units=_safe_int(d.get("units")),
                    land_area_tsubo=_safe_float(d.get("land_area_tsubo")),
                    building_area_tsubo=_safe_float(d.get("building_area_tsubo")),
                    nla_tsubo=_safe_float(d.get("nla_tsubo")),
                    occupancy_pct=_safe_float(d.get("occupancy_pct")),
                    annual_rent_man=_safe_float(d.get("annual_rent_man")),
                    rent_per_nla=_safe_float(d.get("rent_per_nla")),
                    broker=str(d.get("broker") or ""),
                    notes=str(d.get("notes") or ""),
                    source_index=idx + 1,
                )
                item.compute_quick_score()
                items.append(item)
            return items
        except Exception as e:
            print(f"[バルク抽出エラー] {e}")
            return []

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
