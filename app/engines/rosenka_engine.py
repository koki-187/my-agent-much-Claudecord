from dataclasses import dataclass
from typing import Optional
import csv
import os


@dataclass
class RosenkaResult:
    """路線価マッチング結果"""
    matched_area: str                      # マッチしたエリア名
    rosenka_per_sqm: int                   # 路線価（円/㎡）
    land_price_per_sqm: int                # 公示地価（円/㎡）
    actual_per_sqm: Optional[float]        # 売出価格の㎡単価
    ratio_to_rosenka: Optional[float]      # 路線価比（売出/路線価）
    ratio_to_land_price: Optional[float]   # 公示地価比
    evaluation: str                        # 評価（割安/適正/やや高い/高い）
    comment: str                           # コメント
    confidence: str                        # マッチング信頼度（high/medium/low）


class RosenkaEngine:
    """全国路線価・公示地価マッチングエンジン"""

    _CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'rosenka.csv')

    def __init__(self) -> None:
        self._data: list[dict] = []
        self._load_csv()

    def _load_csv(self) -> None:
        path = os.path.abspath(self._CSV_PATH)
        if not os.path.exists(path):
            return
        with open(path, encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row['rosenka_per_sqm'] = int(row['rosenka_per_sqm'])
                    row['land_price_per_sqm'] = int(row['land_price_per_sqm'])
                    row['year'] = int(row['year'])
                    self._data.append(row)
                except (ValueError, KeyError):
                    continue

    def _extract_address_parts(self, address: str) -> dict:
        """住所文字列から都道府県・市区町村・エリアを抽出する"""
        parts = {'prefecture': '', 'city': '', 'area': address}

        prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
        ]

        for pref in prefectures:
            if pref in address:
                parts['prefecture'] = pref
                remainder = address.replace(pref, '', 1)

                # 市区町村を抽出（区・市・町・村の順で試みる）
                for suffix in ('区', '市', '町', '村'):
                    idx = remainder.find(suffix)
                    if idx != -1:
                        city_candidate = remainder[: idx + 1]
                        # 「大阪市中央区」のような政令市＋区の形式に対応
                        if suffix == '区' and '市' in remainder[:idx]:
                            city_idx = remainder.find('市')
                            city_candidate = remainder[: idx + 1]
                        parts['city'] = city_candidate
                        parts['area'] = remainder[idx + 1:]
                        break
                break

        return parts

    def _match_score(
        self,
        row: dict,
        parts: dict,
        zoning: Optional[str],
    ) -> int:
        """マッチングスコアを計算する（最大110点）"""
        score = 0

        # 都道府県一致: 40点
        if parts['prefecture'] and row['prefecture'] == parts['prefecture']:
            score += 40
        elif parts['prefecture'] and parts['prefecture'] in row['prefecture']:
            score += 20

        # 市区町村一致: 35点
        if parts['city']:
            if row['city'] == parts['city']:
                score += 35
            elif parts['city'] in row['city'] or row['city'] in parts['city']:
                score += 20

        # エリア一致: 20点
        if parts['area']:
            if row['area'] == parts['area']:
                score += 20
            elif parts['area'] in row['area'] or row['area'] in parts['area']:
                score += 10

        # 用途地域一致: 15点
        if zoning:
            if row['zone_type'] == zoning:
                score += 15
            elif zoning in row['zone_type'] or row['zone_type'] in zoning:
                score += 8

        return score

    def lookup(
        self,
        address: str,
        price: int,
        land_area_sqm: Optional[float],
        zoning: Optional[str] = None,
    ) -> Optional[RosenkaResult]:
        """
        住所・価格・土地面積・用途地域から路線価情報を検索してRosenkaResultを返す。
        マッチする行が見つからない場合はNoneを返す。
        """
        if not self._data:
            return None

        parts = self._extract_address_parts(address)

        best_row: Optional[dict] = None
        best_score = -1

        for row in self._data:
            score = self._match_score(row, parts, zoning)
            if score > best_score:
                best_score = score
                best_row = row

        # 都道府県 + 部分的な市区町村レベルの一致が必要（スコア60未満は誤マッチの恐れ）
        if best_score < 60 or best_row is None:
            return None

        rosenka = best_row['rosenka_per_sqm']
        land_price = best_row['land_price_per_sqm']
        matched_area = f"{best_row['prefecture']}{best_row['city']} {best_row['area']} ({best_row['zone_type']})"

        # 信頼度判定
        if best_score >= 75:
            confidence = 'high'
        elif best_score >= 40:
            confidence = 'medium'
        else:
            confidence = 'low'

        # ㎡単価・比率の計算
        actual_per_sqm: Optional[float] = None
        ratio_to_rosenka: Optional[float] = None
        ratio_to_land_price: Optional[float] = None

        if land_area_sqm and land_area_sqm > 0 and price > 0:
            actual_per_sqm = price / land_area_sqm
            if rosenka > 0:
                ratio_to_rosenka = actual_per_sqm / rosenka
            if land_price > 0:
                ratio_to_land_price = actual_per_sqm / land_price

        # 評価ロジック
        evaluation, comment = self._evaluate(ratio_to_rosenka)

        return RosenkaResult(
            matched_area=matched_area,
            rosenka_per_sqm=rosenka,
            land_price_per_sqm=land_price,
            actual_per_sqm=actual_per_sqm,
            ratio_to_rosenka=ratio_to_rosenka,
            ratio_to_land_price=ratio_to_land_price,
            evaluation=evaluation,
            comment=comment,
            confidence=confidence,
        )

    def _evaluate(self, ratio: Optional[float]) -> tuple[str, str]:
        """路線価比から評価とコメントを返す"""
        if ratio is None:
            return '判定不可', '土地面積が未指定のため路線価比を算出できません'
        if ratio < 0.8:
            return '割安', f'路線価の{ratio:.1%}水準。相場より割安で購入余地あり'
        if ratio < 1.1:
            return '適正', f'路線価の{ratio:.1%}水準。相場と概ね整合した適正価格帯'
        if ratio < 1.4:
            return 'やや高い', f'路線価の{ratio:.1%}水準。相場をやや上回り、指値交渉を推奨'
        return '高い', f'路線価の{ratio:.1%}水準。相場を大幅に上回り、慎重な検討が必要'
