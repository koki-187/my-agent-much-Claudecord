"""
similarity_service.py — 類似過去案件レコメンドサービス (F3)

過去案件JSONから類似度スコアを算出し、上位 top_k 件を返す。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from app.models.property import AssetType, PropertyData

logger = logging.getLogger(__name__)

# 同種系統グループ（片方が含まれる場合に 0.5 類似とみなす）
_SIMILAR_ASSET_GROUPS: List[frozenset] = [
    frozenset({AssetType.APARTMENT_WHOLE, AssetType.APARTMENT_WOOD}),
    frozenset({AssetType.UNIT, AssetType.HOUSE}),
]

# 重み定義
_W_AREA = 0.35
_W_ASSET = 0.20
_W_PRICE = 0.20
_W_YIELD = 0.15
_W_YEAR = 0.10


@dataclass
class SimilarCase:
    """類似案件1件の表示用データ"""

    property_name: str
    address: str
    asset_type: str
    price: int                       # 円
    gross_yield: Optional[float]
    rank: Optional[str]              # S/A/B/C/D
    total_score: Optional[float]
    judgement: Optional[str]
    saved_at: str                    # "2026-03-15"
    similarity: float                # 0.0〜1.0
    match_reasons: List[str]         # 上位3要素の日本語ラベル
    file_id: str                     # JSONファイル名（クリックで詳細展開用）


class SimilarityService:
    def __init__(self, history_dir: str = "app/data/history") -> None:
        # 絶対パス化
        if not os.path.isabs(history_dir):
            base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            history_dir = os.path.join(base, history_dir)
        self._history_dir = history_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_similar(
        self,
        target: PropertyData,
        top_k: int = 3,
        min_similarity: float = 0.3,
    ) -> List[SimilarCase]:
        """類似度の高い順に top_k 件を返す。"""
        cases = self._load_all_cases()
        if not cases:
            return []

        scored: List[Tuple[float, SimilarCase]] = []
        for file_id, prop, meta in cases:
            sim, reasons = self._compute_similarity(target, prop, meta)
            if sim < min_similarity:
                continue
            saved_str = _format_saved_at(meta.get("saved_at", ""))
            sc = SimilarCase(
                property_name=prop.property_name or "",
                address=prop.address,
                asset_type=prop.asset_type.value,
                price=prop.price,
                gross_yield=prop.gross_yield,
                rank=meta.get("rank"),
                total_score=_safe_float(meta.get("score")),
                judgement=meta.get("judgement"),
                saved_at=saved_str,
                similarity=round(sim, 4),
                match_reasons=reasons,
                file_id=file_id,
            )
            scored.append((sim, sc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [sc for _, sc in scored[:top_k]]

    # ------------------------------------------------------------------
    # Storage loader
    # ------------------------------------------------------------------

    def _load_all_cases(self) -> List[Tuple[str, PropertyData, dict]]:
        """
        Returns: List of (file_id, PropertyData, analysis_metadata)
        analysis_metadata keys: rank, score, judgement, saved_at
        """
        results: List[Tuple[str, PropertyData, dict]] = []
        if not os.path.isdir(self._history_dir):
            return results

        for fname in os.listdir(self._history_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self._history_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    record = json.load(f)
                prop_dict = record.get("property")
                if not prop_dict:
                    continue
                prop = PropertyData(**prop_dict)
                meta = {
                    "rank": record.get("rank"),
                    "score": record.get("score"),
                    "judgement": None,   # storage_service は judgement を保存しない
                    "saved_at": record.get("saved_at", ""),
                }
                results.append((fname, prop, meta))
            except Exception as exc:
                logger.warning("案件ロード失敗 %s: %s", fname, exc)

        return results

    # ------------------------------------------------------------------
    # Similarity computation (pure functions below)
    # ------------------------------------------------------------------

    def _compute_similarity(
        self,
        target: PropertyData,
        case: PropertyData,
        meta: dict,
    ) -> Tuple[float, List[str]]:
        """
        重み付きスコアを算出し (score, match_reasons) を返す。
        gross_yield / built_year が欠損している場合は重みを再正規化する。
        """
        components: List[Tuple[str, float, float]] = []  # (label, weight, raw_score)

        # --- 1. エリア (0.35) ---
        area_score, area_label = _score_area(target.address, case.address)
        components.append((area_label, _W_AREA, area_score))

        # --- 2. 資産タイプ (0.20) ---
        asset_score, asset_label = _score_asset_type(target.asset_type, case.asset_type)
        components.append((asset_label, _W_ASSET, asset_score))

        # --- 3. 価格レンジ (0.20) ---
        price_score, price_label = _score_price(target.price, case.price)
        components.append((price_label, _W_PRICE, price_score))

        # --- 4. 利回り (0.15) — 欠損時スキップ ---
        if target.gross_yield is not None and case.gross_yield is not None:
            yield_score, yield_label = _score_yield(target.gross_yield, case.gross_yield)
            components.append((yield_label, _W_YIELD, yield_score))

        # --- 5. 築年帯 (0.10) — 欠損時スキップ ---
        if target.built_year is not None and case.built_year is not None:
            year_score, year_label = _score_built_year(target.built_year, case.built_year)
            components.append((year_label, _W_YEAR, year_score))

        # 再正規化
        total_weight = sum(w for _, w, _ in components)
        if total_weight == 0:
            return 0.0, []

        similarity = sum(w * s for _, w, s in components) / total_weight

        # match_reasons: スコア寄与(w*s)の高い順に最大3件
        contributions = sorted(
            [(label, w * s / total_weight) for label, w, s in components if s > 0],
            key=lambda x: x[1],
            reverse=True,
        )
        reasons = [label for label, _ in contributions[:3]]

        return similarity, reasons


# ------------------------------------------------------------------
# Pure scoring functions
# ------------------------------------------------------------------

def _score_area(addr_target: str, addr_case: str) -> Tuple[float, str]:
    """エリア類似度: 同区市=1.0, 同都道府県=0.4, その他=0.0"""
    ward_target = _extract_ward_or_city(addr_target)
    ward_case = _extract_ward_or_city(addr_case)
    pref_target = _extract_prefecture(addr_target)
    pref_case = _extract_prefecture(addr_case)

    if ward_target and ward_case and ward_target == ward_case:
        return 1.0, f"同エリア（{ward_target}）"
    if pref_target and pref_case and pref_target == pref_case:
        return 0.4, f"同都道府県（{pref_target}）"
    return 0.0, "エリア不一致"


def _score_asset_type(t: AssetType, c: AssetType) -> Tuple[float, str]:
    """資産タイプ類似度: 完全一致=1.0, 同系統=0.5, 異なる=0.0"""
    if t == c:
        return 1.0, f"同種別（{t.value}）"
    for group in _SIMILAR_ASSET_GROUPS:
        if t in group and c in group:
            return 0.5, f"類似種別（{t.value}/{c.value}）"
    return 0.0, "種別不一致"


def _score_price(p_target: int, p_case: int) -> Tuple[float, str]:
    """価格レンジ類似度: ±20%以内=1.0, ±100%超=0.0, 線形減衰"""
    if p_case == 0 or p_target == 0:    # ゼロ除算ガード (両方チェック)
        return 0.0, "価格不明"
    diff_ratio = abs(p_target - p_case) / p_case
    if diff_ratio <= 0.20:
        pct = round(diff_ratio * 100)
        return 1.0, f"価格±{pct}%"
    if diff_ratio >= 1.0:
        return 0.0, "価格乖離大"
    # 線形減衰: diff_ratio=0.20→1.0, diff_ratio=1.0→0.0
    score = 1.0 - (diff_ratio - 0.20) / (1.0 - 0.20)
    pct = round(diff_ratio * 100)
    return round(score, 4), f"価格±{pct}%"


def _score_yield(y_target: float, y_case: float) -> Tuple[float, str]:
    """利回り類似度: 差0.5%以内=1.0, 差3%以上=0.0, 線形減衰"""
    diff = abs(y_target - y_case)
    t_pct = round(y_target * 100, 1)
    c_pct = round(y_case * 100, 1)
    label = f"利回り近似({t_pct}%/{c_pct}%)"
    if diff <= 0.005:
        return 1.0, label
    if diff >= 0.03:
        return 0.0, label
    score = 1.0 - (diff - 0.005) / (0.03 - 0.005)
    return round(score, 4), label


def _score_built_year(y_target: int, y_case: int) -> Tuple[float, str]:
    """築年帯類似度: ±3年=1.0, ±10年=0.5, それ以上=0.0"""
    diff = abs(y_target - y_case)
    label = f"築年近接({y_target}/{y_case})"
    if diff <= 3:
        return 1.0, label
    if diff <= 10:
        return 0.5, label
    return 0.0, label


# ------------------------------------------------------------------
# Address parsing helpers
# ------------------------------------------------------------------

_PREFECTURE_SUFFIXES = ("都", "道", "府", "県")
# 47 都道府県の前方一致辞書 (「京都府」が「京都」として誤判定されるバグ回避)
_ALL_PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県",
    "沖縄県",
)


def _extract_prefecture(address: str) -> str:
    """住所から都道府県名を抽出する (47都道府県の前方一致を優先)"""
    if not address:
        return ""
    # まず47都道府県の前方一致 (「京都府」を「京都」と誤判定するバグ回避)
    for pref in _ALL_PREFECTURES:
        if address.startswith(pref):
            return pref
    # フォールバック: 接尾辞による検出
    for i, ch in enumerate(address):
        if ch in _PREFECTURE_SUFFIXES:
            return address[: i + 1]
    return ""


def _extract_ward_or_city(address: str) -> str:
    """住所から区・市・郡・町・村レベルを抽出する"""
    # 都道府県を除いた後の最初の区/市/郡/町/村
    pref = _extract_prefecture(address)
    rest = address[len(pref):]
    for suffix in ("区", "市", "郡", "町", "村"):
        idx = rest.find(suffix)
        if idx >= 0:
            return rest[: idx + 1]
    return ""


# ------------------------------------------------------------------
# Utility helpers
# ------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _format_saved_at(raw: str) -> str:
    """'20260315_123456' → '2026-03-15'"""
    try:
        dt = datetime.strptime(raw[:8], "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return raw
