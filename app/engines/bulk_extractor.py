"""
BulkExtractor — バルク物件リストの一括抽出・クイックスコアリング

対応入力フォーマット:
  - テキスト貼り付け（PDF コピペ）
  - PDF ファイルアップロード (PyMuPDF / pdfplumber)
  - URL（requests + BeautifulSoup）
  - 英語ポートフォリオシート（BX Resi Bulk 等、M=百万円 / CapRate 表記）

クイックスコア算出（100点満点）:
  市場相対利回り(40) + エリア(30) + 築年(20) + 商流(10)
  ※利回りはエリア別期待Cap Rateとの差分で評価（東京4%=普通、地方4%=低い）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── エリア分類定数 ────────────────────────────────────────────────────────────
_TOKYO_23KU_PRIME = [          # 都心6区：流動性・需要ともに最高
    "千代田区", "中央区", "港区", "新宿区", "渋谷区", "文京区",
]
_TOKYO_23KU = [
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
    "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
    "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
    "葛飾区", "江戸川区",
]
_MAJOR_CITIES = [
    "大阪市", "神戸市", "京都市", "横浜市", "川崎市", "さいたま市",
    "千葉市", "名古屋市", "福岡市", "札幌市", "仙台市", "広島市",
]

# ── エリア別期待利回り（市場 Cap Rate 参照値）────────────────────────────────
# 同じ利回りでもエリアの期待値に対して高いか低いかで評価する
AREA_EXPECTED_YIELD: dict[str, float] = {
    "23ku_prime":    3.5,   # 都心6区（千代田・中央・港・新宿・渋谷・文京）
    "23ku_standard": 4.0,   # その他23区
    "tokyo_other":   5.0,   # 東京都下（立川・八王子等）
    "major_city":    5.5,   # 横浜・川崎・大阪市・名古屋市等
    "regional":      7.0,   # 地方都市・その他
}

_VERDICT_MAP = {
    "即対応": "🟢",
    "要検討": "🟡",
    "条件次第": "🟠",
    "後回し": "🔴",
}

# 判断記録の選択肢
DECISION_OPTIONS = ["未決定", "🟢 追う", "🟡 様子見", "🔴 見送り"]

# ── 事前コンパイル済み正規表現 ────────────────────────────────────────────────
# _parse_price_man() で使用
_RE_ENG_M    = re.compile(r'^(\d+(?:\.\d+)?)M$', re.I)
_RE_ENG_B    = re.compile(r'^(\d+(?:\.\d+)?)B$', re.I)
_RE_OKU_MAN  = re.compile(r'(\d+)億(\d+)万')
_RE_OKU_ONLY = re.compile(r'(\d+)億')
_RE_MAN_ONLY = re.compile(r'(\d+)万')
_RE_NUM      = re.compile(r'(\d+(?:\.\d+)?)')

# extract_from_text_simple() で使用
_RE_PRICE = re.compile(
    r'(?P<price>'
    r'\d+億\d*(?:\,?\d+)?万円'     # 13億3000万円
    r'|\d[\d,]+万円'               # 13,300万円
    r'|\d+億円'                    # 40億円
    r'|\d+\.\d+M\b'               # 550.0M（英語）
    r'|\d+M\b'                    # 550M（英語）
    r')'
)
_RE_YIELD   = re.compile(r'(\d+\.\d+)[\s　]*[%％]')
_RE_WALK    = re.compile(r'(?:徒歩|歩|Walk to Sta[.\s]*)[\s　]*(\d+)[\s　]*(?:分|min)', re.I)
_RE_YEAR    = re.compile(r'((?:19|20)\d{2})[\s/年][\d月]*(?:予定|完成)?')
_RE_STRUCT  = re.compile(r'(RC造|SRC造|鉄骨造|木造|軽量鉄骨造|S造)')
_RE_STATION = re.compile(r'「([^」]+)」')
_RE_UNITS   = re.compile(r'(\d+)[\s　]*(?:戸|Units?)', re.I)


def _classify_area(address: str, walk_minutes: Optional[int]) -> tuple[str, str]:
    """
    住所と徒歩分からエリアタイプを返す。
    戻り値: (area_type, area_label)
    """
    w = walk_minutes or 99
    if any(k in address for k in _TOKYO_23KU_PRIME):
        if w <= 5:
            return "23ku_prime", f"都心6区 駅{w}分"
        return "23ku_standard", f"都心6区 駅{w}分"
    if any(k in address for k in _TOKYO_23KU):
        return "23ku_standard", f"東京23区 駅{w}分"
    if "東京都" in address or "東京" in address:
        return "tokyo_other", f"東京都下 駅{w}分"
    if any(c in address for c in _MAJOR_CITIES):
        return "major_city", f"主要都市 駅{w}分"
    return "regional", "地方・その他"


@dataclass
class BulkPropertyItem:
    """バルク抽出時の簡易物件データ（1物件分）"""
    property_name: str = ""
    address: str = ""
    station: str = ""
    walk_minutes: Optional[int] = None
    price_man: Optional[float] = None           # 万円
    gross_yield_pct: Optional[float] = None     # %
    built_year: Optional[int] = None
    structure: str = ""
    asset_type: str = ""                        # 日本語種別
    units: Optional[int] = None
    land_area_tsubo: Optional[float] = None
    building_area_tsubo: Optional[float] = None
    occupancy_pct: Optional[float] = None       # 0〜100
    annual_rent_man: Optional[float] = None     # 万円
    nla_tsubo: Optional[float] = None           # 専有面積（坪）英語資料用
    rent_per_nla: Optional[float] = None        # 坪単価（円）
    broker: str = ""
    notes: str = ""
    source_index: int = 0                       # 原文中の物件番号

    # スコアリング結果（compute_quick_score() で算出）
    area_type: str = ""
    area_label: str = ""
    expected_yield: float = 0.0                 # エリアの期待利回り（%）
    yield_vs_market: float = 0.0                # 実利回り − 期待利回り（+がよい）

    score_yield: int = 0
    score_area: int = 0
    score_age: int = 0
    score_broker: int = 0
    quick_score: int = 0
    quick_verdict: str = ""
    quick_emoji: str = ""
    quick_reason: str = ""

    # 判断記録（ユーザーが選択）
    decision: str = "未決定"

    def compute_quick_score(self) -> "BulkPropertyItem":
        """クイックスコアを算出してフィールドに書き込む"""
        reasons: list[str] = []

        # ── エリア分類 ──────────────────────────────────────────────────────────
        self.area_type, self.area_label = _classify_area(self.address, self.walk_minutes)
        self.expected_yield = AREA_EXPECTED_YIELD.get(self.area_type, 7.0)

        # ── 1. 市場相対利回りスコア（40点）──────────────────────────────────────
        y = self.gross_yield_pct or 0.0
        self.yield_vs_market = round(y - self.expected_yield, 2) if y > 0 else -99.0

        if y == 0:
            sy = 0
            yr = "利回り未入力"
        else:
            diff = y - self.expected_yield
            if diff >= 2.5:
                sy, yr = 40, f"利回り{y:.1f}%（市場期待比 +{diff:.1f}%）"
            elif diff >= 1.5:
                sy, yr = 35, f"利回り{y:.1f}%（市場期待比 +{diff:.1f}%）"
            elif diff >= 0.5:
                sy, yr = 30, f"利回り{y:.1f}%（市場期待比 +{diff:.1f}%）"
            elif diff >= 0.0:
                sy, yr = 22, f"利回り{y:.1f}%（市場期待比 ±{diff:.1f}%）"
            elif diff >= -0.5:
                sy, yr = 15, f"利回り{y:.1f}%（市場期待比 {diff:.1f}%）"
            elif diff >= -1.0:
                sy, yr = 8,  f"利回り{y:.1f}%（市場期待比 {diff:.1f}%）"
            else:
                sy, yr = 0,  f"利回り{y:.1f}%（市場期待比 {diff:.1f}%、低すぎ）"
        self.score_yield = sy
        reasons.append(yr)

        # ── 2. エリアスコア（30点）────────────────────────────────────────────
        w = self.walk_minutes or 99
        at = self.area_type

        if at == "23ku_prime" and w <= 5:
            sa, ar = 30, f"都心6区 駅{w}分"
        elif at == "23ku_prime" and w <= 10:
            sa, ar = 27, f"都心6区 駅{w}分"
        elif at == "23ku_prime":
            sa, ar = 23, f"都心6区 駅{w}分（遠め）"
        elif at == "23ku_standard" and w <= 5:
            sa, ar = 27, f"23区 駅{w}分"
        elif at == "23ku_standard" and w <= 8:
            sa, ar = 24, f"23区 駅{w}分"
        elif at == "23ku_standard" and w <= 12:
            sa, ar = 20, f"23区 駅{w}分"
        elif at == "23ku_standard":
            sa, ar = 15, f"23区 駅{w}分（遠め）"
        elif at == "tokyo_other" and w <= 10:
            sa, ar = 18, f"東京都下 駅{w}分"
        elif at == "tokyo_other":
            sa, ar = 13, f"東京都下 駅{w}分（遠め）"
        elif at == "major_city" and w <= 10:
            sa, ar = 16, f"主要都市 駅{w}分"
        elif at == "major_city":
            sa, ar = 11, f"主要都市 駅{w}分（遠め）"
        else:
            sa, ar = 8, self.area_label
        self.score_area = sa
        reasons.append(ar)

        # ── 3. 築年スコア（20点）────────────────────────────────────────────
        by = self.built_year or 0
        if by >= 2020:
            sb, br = 20, "築5年以内（新築同等）"
        elif by >= 2015:
            sb, br = 18, "築10年以内"
        elif by >= 2010:
            sb, br = 15, "築15年以内"
        elif by >= 2000:
            sb, br = 11, "築25年以内"
        elif by >= 1990:
            sb, br = 7,  "築35年以内"
        elif by >= 1981:
            sb, br = 4,  "新耐震（築古）"
        elif by > 0:
            sb, br = 0,  "⚠️ 旧耐震（1981年以前）"
        else:
            sb, br = 8,  "築年未入力"
        self.score_age = sb
        reasons.append(br)

        # ── 4. 商流スコア（10点）────────────────────────────────────────────
        b = self.broker.lower()
        if "売主" in b or "(s)" in b or "（s）" in b:
            sc, bcr = 10, "売主直接"
        elif "代理" in b or "(w)" in b or "（w）" in b:
            sc, bcr = 8,  "代理"
        elif b:
            sc, bcr = 5,  "仲介あり"
        else:
            sc, bcr = 7,  "商流未入力"
        self.score_broker = sc
        reasons.append(bcr)

        # ── 総合 ──────────────────────────────────────────────────────────────
        total = sy + sa + sb + sc
        self.quick_score = total

        if total >= 75:
            self.quick_verdict = "即対応"
        elif total >= 55:
            self.quick_verdict = "要検討"
        elif total >= 35:
            self.quick_verdict = "条件次第"
        else:
            self.quick_verdict = "後回し"

        self.quick_emoji = _VERDICT_MAP.get(self.quick_verdict, "⬜")
        self.quick_reason = " ／ ".join(reasons)
        return self


# ── テキストからの物件抽出（LLM 非使用の軽量版） ─────────────────────────────
def extract_from_text_simple(text: str) -> list[BulkPropertyItem]:
    """
    LLM なしの正規表現ベース抽出（翔栄フォーマット等の定型リスト向け）。
    LLM が使えない場合のフォールバック。
    """
    items: list[BulkPropertyItem] = []

    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        pm = _RE_PRICE.search(line)
        if not pm:
            i += 1
            continue

        context_lines = lines[max(0, i - 5): min(len(lines), i + 15)]
        context = "\n".join(context_lines)

        item = BulkPropertyItem(source_index=len(items) + 1)

        # 価格変換（英語M 対応）
        item.price_man = _parse_price_man(pm.group("price"))

        # 利回り
        ym = _RE_YIELD.search(context)
        if ym:
            item.gross_yield_pct = float(ym.group(1))

        # 住所
        for cl in context_lines:
            if any(p in cl for p in [
                "東京都", "神奈川県", "大阪府", "愛知県", "埼玉県",
                "千葉県", "福岡県", "京都府", "兵庫県", "名古屋市",
            ]):
                item.address = cl.strip()
                break

        # 駅徒歩
        wm = _RE_WALK.search(context)
        if wm:
            item.walk_minutes = int(wm.group(1))

        # 駅名
        station_m = _RE_STATION.search(context)
        if station_m:
            item.station = station_m.group(1)

        # 築年
        ym2 = _RE_YEAR.search(context)
        if ym2:
            item.built_year = int(ym2.group(1))

        # 構造
        sm = _RE_STRUCT.search(context)
        if sm:
            item.structure = sm.group(1)

        # 取引態様
        if "売主（S）" in context or "売主(S)" in context:
            item.broker = "売主（S）"
        elif "代理（W）" in context or "代理(W)" in context:
            item.broker = "代理（W）"

        # 戸数
        unit_m = _RE_UNITS.search(context)
        if unit_m:
            item.units = int(unit_m.group(1))

        # 物件名
        for cl in context_lines[:6]:
            cl = cl.strip()
            if cl and len(cl) >= 4 and not any(c.isdigit() for c in cl[:2]):
                item.property_name = cl
                break

        item.asset_type = _guess_asset_type(context)
        item.compute_quick_score()
        items.append(item)
        i += 8  # 次の物件へ

    return items


def extract_from_url(url: str, timeout: int = 12) -> tuple[str, str]:
    """
    URL からページテキストを取得する。
    戻り値: (text, error_message)
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text, ""
    except Exception as e:
        return "", str(e)


def extract_from_pdf_bytes(pdf_bytes: bytes) -> tuple[str, str]:
    """
    PDF バイト列からテキストを抽出する。
    戻り値: (text, error_message)
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        for page in doc:
            t = page.get_text()
            if t.strip():
                texts.append(t)
        return "\n".join(texts), ""
    except Exception as e:
        return "", str(e)


def get_text_chunks(text: str, max_chars: int = 14000) -> list[str]:
    """
    長いテキストをmax_chars 以下のチャンクに分割する（物件境界を考慮）。
    バルク抽出でLLMに渡す前の前処理。
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.splitlines(keepends=True)
    current = ""
    for line in lines:
        if len(current) + len(line) > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


# ── ヘルパー関数 ──────────────────────────────────────────────────────────────
def _parse_price_man(s: str) -> Optional[float]:
    """
    「3億5000万円」「134,000万円」「550.0M」「1.5B」等を万円（float）に変換。
    英語のM（百万円）、B（十億円）にも対応。
    """
    if not s:
        return None
    s_clean = s.replace(",", "").replace("，", "").replace(" ", "").strip()

    # 英語: 550.0M → 55,000万円（M = 100万円 = 100万 → 100万円）
    # 注: 不動産文書での M は million円 = 100万円
    m_eng = _RE_ENG_M.match(s_clean)
    if m_eng:
        return float(m_eng.group(1)) * 100  # M = 100万円

    b_eng = _RE_ENG_B.match(s_clean)
    if b_eng:
        return float(b_eng.group(1)) * 100_000  # B = 10億円 = 10万万円

    # 日本語: 13億3000万円
    oku_m = _RE_OKU_MAN.search(s_clean)
    if oku_m:
        return float(oku_m.group(1)) * 10000 + float(oku_m.group(2))

    oku_only = _RE_OKU_ONLY.search(s_clean)
    if oku_only:
        return float(oku_only.group(1)) * 10000

    man_m = _RE_MAN_ONLY.search(s_clean)
    if man_m:
        return float(man_m.group(1))

    # 純粋な数字
    num_m = _RE_NUM.search(s_clean)
    if num_m:
        v = float(num_m.group(1))
        if v >= 1_000_000:
            return v / 10_000   # 円→万円
        return v
    return None


def _guess_asset_type(text: str) -> str:
    """テキストから物件種別を推定（日英両対応）"""
    t = text.lower()
    if any(w in text for w in ["共同住宅", "一棟マンション"]) or "residential" in t:
        return "一棟マンション"
    if any(w in text for w in ["アパート", "木造"]):
        return "一棟アパート"
    if any(w in text for w in ["区分", "専有"]):
        return "区分マンション"
    if any(w in text for w in ["土地", "用地", "更地"]):
        return "土地"
    if any(w in text for w in ["店舗", "商業", "テナント", "retail"]):
        return "商業・店舗"
    if any(w in text for w in ["事務所", "オフィス", "ビル", "office"]):
        return "オフィス"
    if any(w in text for w in ["工場", "倉庫", "物流", "warehouse"]):
        return "工場・倉庫"
    return "一棟マンション"
