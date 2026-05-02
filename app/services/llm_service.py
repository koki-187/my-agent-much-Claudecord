import os
import json
import logging
from typing import Optional
from app.models.property import PropertyData, AssetType
from app.engines.bulk_extractor import BulkPropertyItem

logger = logging.getLogger(__name__)

MAX_BULK_ITEMS = 100  # バルク抽出の件数上限


# .envファイルを自動ロード（起動時に1回）
def _load_env_file():
    """案件調査君.envファイルから環境変数を読み込む"""
    env_paths = [
        os.path.join(os.path.dirname(__file__), '..', '..', '..', '案件調査君.env'),
        os.path.join(os.path.dirname(__file__), '..', '..', '案件調査君.env'),
    ]
    for path in env_paths:
        try:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 全角イコール・半角イコール両対応
                    for sep in ['＝', '=']:
                        if sep in line and not line.startswith('#'):
                            key_raw, _, val = line.partition(sep)
                            key_raw = key_raw.strip()
                            val = val.strip()
                            # キー名を正規化
                            if 'Gemini' in key_raw or 'GEMINI' in key_raw or 'gemini' in key_raw:
                                if not os.environ.get('GEMINI_API_KEY'):
                                    os.environ['GEMINI_API_KEY'] = val
                            elif 'Anthropic' in key_raw or 'ANTHROPIC' in key_raw:
                                if not os.environ.get('ANTHROPIC_API_KEY'):
                                    os.environ['ANTHROPIC_API_KEY'] = val
                            break
            break  # 最初に見つかったファイルで終了
        except (FileNotFoundError, PermissionError):
            continue

_load_env_file()  # モジュールロード時に実行


def _load_streamlit_secrets():
    """Streamlit Cloud の st.secrets から API キーを環境変数に反映"""
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            for key in ('ANTHROPIC_API_KEY', 'GEMINI_API_KEY'):
                val = st.secrets.get(key, '')
                if val and not os.environ.get(key):
                    os.environ[key] = val
    except Exception:
        pass  # Streamlit 未起動時（pytest等）は無視


_load_streamlit_secrets()


class _GeminiClientWrapper:
    """Google Gemini APIを Anthropic 互換インターフェースでラップするクラス"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.messages = self  # self.client.messages.create() の形で呼べるように

    def create(self, model: str, max_tokens: int, system, messages: list, **kwargs):
        """Anthropic messages.create() 互換のGemini API呼び出し"""
        import urllib.request

        # system プロンプトを文字列に変換
        if isinstance(system, list):
            system_text = ' '.join(
                item.get('text', '') if isinstance(item, dict) else str(item)
                for item in system
            )
        else:
            system_text = str(system) if system else ''

        # Geminiのモデル名マッピング
        gemini_model = self._map_model(model)

        # リクエストボディ構築
        contents = []
        for msg in messages:
            role = 'user' if msg.get('role') == 'user' else 'model'
            content = msg.get('content', '')
            if isinstance(content, list):
                content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
            contents.append({'role': role, 'parts': [{'text': content}]})

        body = {
            'contents': contents,
            'generationConfig': {
                'maxOutputTokens': max_tokens,
                'temperature': 0.3,
            }
        }
        if system_text:
            body['system_instruction'] = {'parts': [{'text': system_text}]}

        url = f"{self._base_url}/models/{gemini_model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            # URLをマスクしてログ出力（APIキー漏洩防止）
            safe_url = url.split("?")[0] + "?key=***"
            logger.error("Gemini API呼び出し失敗: %s → %s", safe_url, type(e).__name__)
            raise

        # Anthropic形式のレスポンスに変換
        text = result['candidates'][0]['content']['parts'][0]['text']
        return _GeminiResponse(text)

    def _map_model(self, model: str) -> str:
        """AnthropicモデルをGeminiモデルにマッピング"""
        if 'haiku' in model.lower():
            return 'gemini-2.0-flash'   # 軽量・高速
        elif 'sonnet' in model.lower():
            return 'gemini-2.0-flash'   # 標準
        elif 'opus' in model.lower():
            return 'gemini-1.5-pro'     # 高性能
        return 'gemini-2.0-flash'


class _GeminiResponse:
    """Anthropic Response互換のGeminiレスポンスラッパー"""
    def __init__(self, text: str):
        self.content = [_GeminiContent(text)]


class _GeminiContent:
    def __init__(self, text: str):
        self.text = text


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
    # 1. Anthropic優先
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        pass

    # 2. Gemini フォールバック
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        return _GeminiClientWrapper(api_key=gemini_key)

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

## 単位変換ルール（厳守）
- 価格 M表記 → 万円: "550.0M" = 550×100 = 55,000万円 ✅  "550.0M" ≠ 550万円 ❌
- 価格 B表記 → 万円: "1.5B" = 1.5×100,000 = 150,000万円
- 価格「13億3000万円」→ 133,000万円
- 価格「40億円」→ 40×10,000 = 400,000万円 ❌ → 40,000万円 ✅ (1億=10,000万)
- Cap Rate(%) → gross_yield_pct にそのまま入れてよい（日本の表面利回り相当）
- GFA（坪）= 延床面積 → building_area_tsubo
- NLA（坪）= 専有面積合計 → nla_tsubo
- 稼働率 100% → occupancy_pct=100

## 英語フォーマット対応（BXリジBulk等）
英語のポートフォリオシートにはこのような列名がある：
- "Sales Price" → price_man（M単位に注意）
- "Assumed GOR CapRate" / "Cap Rate" → gross_yield_pct
- "Built Year" / "築年" → built_year
- "Walk to Sta." → walk_minutes
- "GFA(tsubo)" → building_area_tsubo
- "NLA(tsubo)" → nla_tsubo
- "# of Units" / "戸数" → units
- "Land Area(tsubo)" → land_area_tsubo
- "Gross Revenue" → annual_rent_man（M単位に注意）

出力はJSON配列のみ。各物件を以下のフィールドで表現してください：
- property_name: 物件名（文字列）
- address: 所在地（都道府県〜番地できる限り詳しく。英語表記は日本語に変換）
- station: 最寄駅名（日本語）
- walk_minutes: 駅徒歩分数（整数、不明はnull）
- price_man: 売出価格（**万円の数値**。例: 13億3000万円→133000、550.0M→55000）
- gross_yield_pct: 表面利回り（%の数値、例: 4.01%→4.01）
- built_year: 築年（西暦整数、未完成・予定の場合は完成予定年）
- structure: 構造（RC造/SRC造/鉄骨造/木造等）
- asset_type: 種別（一棟マンション/一棟アパート/区分マンション/戸建て/土地/商業・店舗/オフィス/工場・倉庫）
- units: 戸数（整数、不明はnull）
- land_area_tsubo: 土地面積（坪の数値、不明はnull）
- building_area_tsubo: 延床面積（坪の数値、不明はnull）
- nla_tsubo: 専有面積合計（坪、不明はnull）
- occupancy_pct: 稼働率（0〜100の数値、不明はnull）
- annual_rent_man: 年間賃料（**万円の数値**。例: 20.3M→2030、53,415,600円→5342）
- rent_per_nla: 坪賃料単価（円/坪、不明はnull）
- broker: 取引態様（売主（S）/代理（W）/仲介等）
- notes: 備考・特記事項（重要な情報のみ200字以内）

**絶対ルール**:
1. 物件が複数ある場合は必ず全て抽出すること（1件も省略しない）
2. JSONのみ出力（説明文不要）
3. 不明なフィールドはnull（空文字""不可）
4. price_manとgross_yield_pctは数値型（文字列不可）"""


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
                system=[{"type": "text", "text": EXTRACT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
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
            logger.error("LLM抽出エラー: %s", e, exc_info=True)
            return None

    def extract_bulk_properties(
        self, text: str, progress_callback=None, chunks: list[str] | None = None
    ) -> list[BulkPropertyItem]:
        """
        テキストから複数の物件を一括抽出して BulkPropertyItem リストを返す。
        テキストが長い場合は自動的にチャンク分割して全件抽出する。
        LLM が使えない場合は空リストを返す（呼び出し側でフォールバック処理）。
        progress_callback: Optional[Callable[[int, int], None]] — (chunk_idx, total_chunks)
        """
        if not self.available:
            return []

        if chunks is None:
            from app.engines.bulk_extractor import get_text_chunks
            chunks = get_text_chunks(text, max_chars=14000)
        total_chunks = len(chunks)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        all_items: list[BulkPropertyItem] = []
        results: dict[int, list[BulkPropertyItem]] = {}
        lock = threading.Lock()
        done_count = [0]

        def _run_chunk(chunk_idx: int, chunk: str) -> tuple[int, list[BulkPropertyItem]]:
            try:
                items = self._extract_chunk(chunk, start_index=chunk_idx * 50)
                return chunk_idx, items
            except Exception as e:
                logger.error("バルク抽出エラー chunk=%d: %s", chunk_idx, e, exc_info=True)
                return chunk_idx, []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_run_chunk, i, c): i for i, c in enumerate(chunks)}
            for future in as_completed(futures):
                chunk_idx, items = future.result()
                with lock:
                    results[chunk_idx] = items
                    done_count[0] += 1
                    if progress_callback:
                        try:
                            progress_callback(done_count[0] - 1, total_chunks)
                        except Exception:
                            pass  # Streamlit widget updates from threads may fail; ignore

        # Reassemble in original order and renumber source_index
        global_idx = 0
        for i in range(total_chunks):
            if i in results:
                for item in results[i]:
                    item.source_index = global_idx + 1
                    global_idx += 1
                all_items.extend(results[i])

        # 件数上限チェック
        if len(all_items) > MAX_BULK_ITEMS:
            logger.warning("バルク抽出: %d件中先頭100件のみ返却", len(all_items))
            all_items = all_items[:MAX_BULK_ITEMS]

        return all_items

    def _extract_chunk(self, text: str, start_index: int = 0) -> list[BulkPropertyItem]:
        """1チャンク分のテキストから物件を抽出する内部メソッド（最大2回リトライ）"""
        last_exc = None
        for attempt in range(2):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8000,
                    system=[{"type": "text", "text": BULK_EXTRACT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    messages=[{
                        "role": "user",
                        "content": f"以下のテキストから全ての物件情報を抽出してください：\n\n{text}"
                    }]
                )
                raw = response.content[0].text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()

                data_list = json.loads(raw)
                if isinstance(data_list, dict):
                    data_list = data_list.get("properties", data_list.get("items", [data_list]))

                items: list[BulkPropertyItem] = []
                for idx, d in enumerate(data_list):
                    if not isinstance(d, dict):
                        continue
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
                        source_index=start_index + idx + 1,
                    )
                    item.compute_quick_score()
                    items.append(item)
                return items  # 成功したら返す
            except json.JSONDecodeError as e:
                logger.warning("JSONパース失敗 (attempt=%d): %s", attempt + 1, e)
                last_exc = e
                continue
            except Exception as e:
                logger.error("チャンク抽出エラー: %s", e, exc_info=True)
                raise
        logger.error("JSONパース最大リトライ超過")
        return []

    def generate_advice(self, report: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=[{"type": "text", "text": ADVICE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": f"以下のレポートにアドバイスをください：\n\n{report[:3000]}"}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error("LLMアドバイスエラー: %s", e, exc_info=True)
            return None

    def is_available(self) -> bool:
        return self.available

    @property
    def provider_name(self) -> str:
        if self.client is None:
            return "未設定"
        if isinstance(self.client, _GeminiClientWrapper):
            return "Gemini (Google AI)"
        return "Claude (Anthropic)"
