"""
BulkExtractor — バルク物件リストの一括抽出・クイックスコアリング

対応入力フォーマット:
  - テキスト貼り付け（PDF コピペ）
  - PDF ファイルアップロード (PyMuPDF / pdfplumber)
  - URL（requests + BeautifulSoup）

クイックスコア算出:
  利回り(40) + エリア(30) + 築年(20) + 商流(10) = 100点満点
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── クイックスコア定数 ─────────────────────────────────────────────────────────
_TOKYO_23KU = [
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
    "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
    "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
    "葛飾区", "江戸川区",
]
_MAJOR_CITIES = [
    "大阪市", "神戸市", "京都市", "横浜市", "川崎市", "さいたま市",
    "千葉市", "名古屋市", "福岡市", "札幌市", "仙台市",
]

_VERDICT_MAP = {
    "即対応": "🟢",
    "要検討": "🟡",
    "条件次第": "🟠",
    "後回し": "🔴",
}


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

    # スコアリング結果（auto-computed）
    score_yield: int = 0
    score_area: int = 0
    score_age: int = 0
    score_broker: int = 0
    quick_score: int = 0
    quick_verdict: str = ""
    quick_emoji: str = ""
    quick_reason: str = ""

    def compute_quick_score(self) -> "BulkPropertyItem":
        """クイックスコアを算出してフィールドに書き込む"""
        reasons: list[str] = []

        # ── 利回りスコア（40点）────────────────────────────────────────────────
        y = self.gross_yield_pct or 0.0
        if y >= 8:
            sy, yr = 40, f"高利回り{y:.1f}%"
        elif y >= 7:
            sy, yr = 35, f"利回り{y:.1f}%"
        elif y >= 6:
            sy, yr = 30, f"利回り{y:.1f}%"
        elif y >= 5:
            sy, yr = 22, f"利回り{y:.1f}%"
        elif y >= 4.5:
            sy, yr = 15, f"利回り{y:.1f}%（やや低め）"
        elif y >= 4:
            sy, yr = 8, f"利回り{y:.1f}%（低め）"
        elif y > 0:
            sy, yr = 0, f"利回り{y:.1f}%（要再検討）"
        else:
            sy, yr = 0, "利回り未入力"
        self.score_yield = sy
        reasons.append(yr)

        # ── エリアスコア（30点）────────────────────────────────────────────────
        addr = self.address or ""
        walk = self.walk_minutes or 99
        in_23ku = any(k in addr for k in _TOKYO_23KU)
        in_tokyo = "東京都" in addr or "東京" in addr
        in_major = any(c in addr for c in _MAJOR_CITIES)

        if in_23ku and walk <= 5:
            sa, ar = 30, "23区駅5分圏内"
        elif in_23ku and walk <= 8:
            sa, ar = 27, "23区駅8分圏内"
        elif in_23ku and walk <= 10:
            sa, ar = 24, "23区駅10分圏内"
        elif in_23ku:
            sa, ar = 20, "23区内（駅距離未確認）"
        elif in_tokyo and walk <= 10:
            sa, ar = 18, "東京都（都下）駅10分圏内"
        elif in_tokyo:
            sa, ar = 14, "東京都（都下）"
        elif in_major and walk <= 10:
            sa, ar = 15, "主要都市駅10分圏内"
        elif in_major:
            sa, ar = 12, "主要都市"
        else:
            sa, ar = 8, "地方・その他エリア"
        self.score_area = sa
        reasons.append(ar)

        # ── 築年スコア（20点）────────────────────────────────────────────────
        by = self.built_year or 0
        if by >= 2020:
            sb, br = 20, "築5年以内"
        elif by >= 2015:
            sb, br = 18, "築10年以内"
        elif by >= 2010:
            sb, br = 15, "築15年以内"
        elif by >= 2000:
            sb, br = 11, "築25年以内"
        elif by >= 1990:
            sb, br = 7, "築35年以内"
        elif by >= 1981:
            sb, br = 4, "新耐震（やや古め）"
        elif by > 0:
            sb, br = 0, "旧耐震（要注意）"
        else:
            sb, br = 8, "築年未入力"  # 不明時は中間値
        self.score_age = sb
        reasons.append(br)

        # ── 商流スコア（10点）────────────────────────────────────────────────
        b = self.broker.lower()
        if "売主" in b or "(s)" in b or "（s）" in b:
            sc, bcr = 10, "売主直接"
        elif "代理" in b or "(w)" in b or "（w）" in b:
            sc, bcr = 8, "代理"
        elif b:
            sc, bcr = 5, "仲介あり"
        else:
            sc, bcr = 7, "商流未入力"
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
    LLM なしの正規表現ベース抽出（翔栄フォーマット等の定型リスト向け）
    LLM が使えない場合のフォールバックとして使用。
    """
    items: list[BulkPropertyItem] = []

    # 価格（〇億〇万円 or 〇,〇〇〇万円）のある行を起点に抽出
    price_pattern = re.compile(
        r'(?P<price>(?:\d+億\d*(?:\,?\d+)?万円|\d[\d,]+万円|\d+億円))'
    )
    # 利回りパターン
    yield_pattern = re.compile(r'(\d+\.\d+)[\s　]*[%％]')
    # 駅徒歩パターン
    walk_pattern = re.compile(r'(?:徒歩|歩|walk)[\s　]*(\d+)[\s　]*(?:分|min)')
    # 築年パターン
    year_pattern = re.compile(r'((?:19|20)\d{2})年[\d月]*(?:予定|完成)?')
    # 構造パターン
    struct_pattern = re.compile(r'(RC造|SRC造|鉄骨造|木造|軽量鉄骨造|S造)')

    lines = text.splitlines()

    # 翔栄フォーマット特化パーサー（物件名→価格→利回りのブロック）
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        pm = price_pattern.search(line)
        if not pm:
            i += 1
            continue

        # 前後5行からデータ収集
        context_lines = lines[max(0, i-5): min(len(lines), i+15)]
        context = "\n".join(context_lines)

        item = BulkPropertyItem()
        item.source_index = len(items) + 1

        # 価格変換
        price_str = pm.group("price")
        price_man = _parse_price_man(price_str)
        item.price_man = price_man

        # 利回り
        ym = yield_pattern.search(context)
        if ym:
            item.gross_yield_pct = float(ym.group(1))

        # 住所（都道府県を含む行）
        for cl in context_lines:
            if any(p in cl for p in ["東京都", "神奈川県", "大阪府", "名古屋市", "愛知県",
                                      "埼玉県", "千葉県", "福岡県", "京都府", "兵庫県"]):
                item.address = cl.strip()
                break

        # 駅・徒歩
        wm = walk_pattern.search(context)
        if wm:
            item.walk_minutes = int(wm.group(1))

        # 駅名（「〇〇」の形式）
        station_m = re.search(r'「([^」]+)」', context)
        if station_m:
            item.station = station_m.group(1)

        # 築年
        ym2 = year_pattern.search(context)
        if ym2:
            item.built_year = int(ym2.group(1))

        # 構造
        sm = struct_pattern.search(context)
        if sm:
            item.structure = sm.group(1)

        # 取引態様
        if "売主（S）" in context or "売主(S)" in context:
            item.broker = "売主（S）"
        elif "代理（W）" in context or "代理(W)" in context:
            item.broker = "代理（W）"

        # 戸数
        unit_m = re.search(r'(\d+)[\s　]*戸', context)
        if unit_m:
            item.units = int(unit_m.group(1))

        # 物件名（価格行の前後で名前っぽい行）
        for cl in context_lines[:6]:
            cl = cl.strip()
            if cl and len(cl) >= 4 and not any(c.isdigit() for c in cl[:2]):
                item.property_name = cl
                break

        # 種別推定
        item.asset_type = _guess_asset_type(context)

        item.compute_quick_score()
        items.append(item)
        i += 10  # 次の物件へジャンプ

    return items


def extract_from_url(url: str, timeout: int = 10) -> tuple[str, str]:
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
                "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # 不要要素を削除
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # 連続空行を圧縮
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
            texts.append(page.get_text())
        return "\n".join(texts), ""
    except Exception as e:
        return "", str(e)


# ── ヘルパー関数 ──────────────────────────────────────────────────────────────
def _parse_price_man(s: str) -> Optional[float]:
    """「3億5000万円」「134,000万円」等を万円（float）に変換"""
    s = s.replace(",", "").replace("，", "").replace(" ", "")
    oku_m = re.search(r'(\d+)億(\d+)万', s)
    if oku_m:
        return float(oku_m.group(1)) * 10000 + float(oku_m.group(2))
    oku_only = re.search(r'(\d+)億', s)
    if oku_only:
        return float(oku_only.group(1)) * 10000
    man_m = re.search(r'(\d+)万', s)
    if man_m:
        return float(man_m.group(1))
    # 純粋な数字
    num_m = re.search(r'(\d+)', s)
    if num_m:
        v = float(num_m.group(1))
        if v >= 1_000_000:
            return v / 10_000   # 円→万円
        return v
    return None


def _guess_asset_type(text: str) -> str:
    """テキストから物件種別を推定"""
    if any(w in text for w in ["共同住宅", "一棟マンション", "マンション"]):
        return "一棟マンション"
    if any(w in text for w in ["アパート", "木造"]):
        return "一棟アパート"
    if any(w in text for w in ["区分", "専有"]):
        return "区分マンション"
    if any(w in text for w in ["土地", "用地", "更地"]):
        return "土地"
    if any(w in text for w in ["店舗", "商業", "テナント"]):
        return "商業・店舗"
    if any(w in text for w in ["事務所", "オフィス", "ビル"]):
        return "オフィス"
    if any(w in text for w in ["工場", "倉庫", "物流"]):
        return "工場・倉庫"
    return "一棟マンション"
