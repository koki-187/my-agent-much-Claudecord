from dataclasses import dataclass
from typing import Optional
import csv
import os


@dataclass
class AreaTrendResult:
    """エリアトレンド評価結果"""
    matched_area: str                     # マッチしたエリア
    trend: str                            # 上昇/横ばい/下落
    price_change_yoy: Optional[float]     # 前年比変動率
    rental_demand: str                    # 賃貸需要（高/中/低）
    vacancy_rate: Optional[float]         # 推定空室率
    comment: str                          # 市場コメント
    confidence: str                       # 信頼度（high/medium/low）
    trend_score_adjustment: int           # スコア加算/減算値（-15〜+15）


class AreaTrendEngine:
    """エリア相場トレンド評価エンジン"""

    def __init__(self):
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "area_trends.csv"
        )
        self._data = []
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._data = list(reader)
        except FileNotFoundError:
            pass

    def evaluate(
        self, address: str, asset_type_key: str = "ALL"
    ) -> Optional[AreaTrendResult]:
        """住所とasset_typeからエリアトレンドを評価"""
        if not self._data or not address:
            return None

        best_match = None
        best_score = 0

        for row in self._data:
            score = 0
            if row["prefecture"] in address:
                score += 40
            if row["city"] in address:
                score += 40
            if row["asset_type"] == asset_type_key:
                score += 20
            elif row["asset_type"] == "ALL":
                score += 5

            if score > best_score:
                best_score = score
                best_match = row

        # 都道府県+市区町村の両方が一致する必要がある（prefecture-onlyはミスマッチのリスク）
        if not best_match or best_score < 80:
            return None

        trend = best_match.get("trend", "横ばい")
        raw_change = best_match.get("price_change_yoy", "")
        price_change: Optional[float] = None
        if raw_change:
            try:
                price_change = float(raw_change)
            except ValueError:
                price_change = None

        raw_vacancy = best_match.get("vacancy_rate", "")
        vacancy_rate: Optional[float] = None
        if raw_vacancy:
            try:
                vacancy_rate = float(raw_vacancy)
            except ValueError:
                vacancy_rate = None

        # スコア調整値（トレンドに基づく）
        if trend == "上昇":
            adj = 10 if price_change is not None and price_change >= 0.05 else 5
        elif trend == "下落":
            adj = -10 if price_change is not None and price_change <= -0.05 else -5
        else:
            adj = 0

        confidence = (
            "high" if best_score >= 75 else "medium" if best_score >= 40 else "low"
        )

        return AreaTrendResult(
            matched_area=f"{best_match['prefecture']}{best_match['city']}",
            trend=trend,
            price_change_yoy=price_change,
            rental_demand=best_match.get("rental_demand", "中"),
            vacancy_rate=vacancy_rate,
            comment=best_match.get("comment", ""),
            confidence=confidence,
            trend_score_adjustment=adj,
        )
