from dataclasses import dataclass, field
from typing import Optional, List
import csv
import os


@dataclass
class DevLandResult:
    """デベロッパー用地逆算分析結果"""
    # 想定開発規模
    estimated_floor_area_sqm: Optional[float]     # 想定延床面積（㎡）
    estimated_floor_area_tsubo: Optional[float]   # 想定延床面積（坪）
    estimated_units: Optional[int]                 # 想定戸数（マンション）

    # デベ収支
    total_sales_revenue: Optional[int]             # 想定総販売額（円）
    construction_cost: Optional[int]               # 建築費総額（円）
    dev_expenses: Optional[int]                    # 諸費用・販管費等（円）
    dev_profit_target: Optional[int]               # デベ目標利益（円）

    # 適正買値
    dev_max_land_price: Optional[int]              # デベが出せる最大地価（円）
    dev_land_price_per_tsubo: Optional[int]        # 坪単価（円）
    dev_land_price_per_sqm: Optional[int]          # ㎡単価（円）

    # 入力価格評価
    price_evaluation: str                          # 割安/適正/やや高い/高すぎる/判定不可
    price_vs_dev_max: Optional[float]              # 売値/デベ最大買値比率

    # 分析ベース
    matched_area: str                              # マッチしたエリア
    sale_price_used: Optional[int]                 # 使用した分譲単価（円/㎡）
    construction_cost_used: Optional[int]          # 使用した建築費単価（円/㎡）
    dev_type: str                                  # MANSION/KODATE/APARTMENT

    # メッセージ
    comment: str
    recommendation: str                            # 追う/条件次第/捨てる
    confidence: str                                # high/medium/low


class DeveloperLandEngine:
    """
    デベロッパー用地逆算指値エンジン

    【基本ロジック】
    デベが買える上限地価 = 総販売額 × 残地価率

    残地価率（土地代÷総販売額）：
    - 都心マンション（高容積）: 25〜30%
    - 郊外マンション（中容積）: 20〜25%
    - 建売住宅（低容積）: 25〜35%（建築費が安い分、土地比率が上がる）

    建築費（2025年水準・RC造）:
    - 都心: 50〜55万円/㎡
    - 郊外: 44〜50万円/㎡
    - 木造建売: 26〜32万円/㎡

    デベ利益目標:
    - マンションデベ: 売上の15〜18%
    - 建売業者: 売上の10〜15%
    """

    # デベ費用構造（総販売額に対する比率）
    DEV_COST_RATIOS = {
        "MANSION": {
            "construction": 0.45,    # 建築費（容積によって変動）
            "expenses": 0.10,        # 諸費用・設計・販管費等
            "profit": 0.15,          # 利益目標
            "land": 0.30,            # 残地価率（100% - 上記）
        },
        "KODATE": {
            "construction": 0.35,    # 木造建売の建築費比率
            "expenses": 0.10,
            "profit": 0.12,
            "land": 0.43,            # 建売は土地比率が高い
        },
        "APARTMENT": {
            "construction": 0.50,    # 賃貸収益アパート
            "expenses": 0.10,
            "profit": 0.12,
            "land": 0.28,
        }
    }

    def __init__(self):
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dev_land_market.csv')
        self._data = []
        try:
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self._data = list(reader)
        except FileNotFoundError:
            pass
        # type フィールドを大文字に正規化（検索ループ内での .upper() コスト削減）
        for row in self._data:
            if 'type' in row and row['type']:
                row['type'] = row['type'].upper()

    def analyze(
        self,
        address: str,
        price: int,
        land_area_sqm: Optional[float] = None,
        floor_area_ratio: Optional[float] = None,
        building_coverage_ratio: Optional[float] = None,
        zoning: Optional[str] = None,
        dev_type: Optional[str] = None,  # MANSION/KODATE/APARTMENT (None=自動判定)
        seller_net_price: Optional[int] = None,  # 売主手取り希望額（仲介手数料別）
    ) -> DevLandResult:
        """デベロッパー用地の逆算分析"""

        # 開発タイプ自動判定
        if dev_type is None:
            dev_type = self._auto_detect_dev_type(address, zoning, floor_area_ratio)

        # エリアデータ検索
        market_row = self._find_market_data(address, dev_type)
        matched_area = "推定値（エリアデータなし）"
        sale_price_per_sqm = None
        construction_cost_per_sqm = None

        if market_row:
            matched_area = f"{market_row.get('prefecture', '')}{market_row.get('city', '')}"
            try:
                sale_price_per_sqm = int(float(market_row.get('sale_price_per_sqm', 0)))
                construction_cost_per_sqm = int(float(market_row.get('construction_cost_per_sqm', 0)))
            except (ValueError, TypeError):
                pass

        # デフォルト単価（データなし時）
        if not sale_price_per_sqm:
            sale_price_per_sqm = self._estimate_sale_price(address, dev_type)
        if not construction_cost_per_sqm:
            construction_cost_per_sqm = self._estimate_construction_cost(address, dev_type)

        # MANSIONで建築費 >= 分譲単価の場合 → 開発採算が取れない → KODATEに自動切替
        if dev_type == "MANSION" and construction_cost_per_sqm >= sale_price_per_sqm:
            dev_type = "KODATE"
            market_row_kodate = self._find_market_data(address, "KODATE")
            if market_row_kodate:
                matched_area = f"{market_row_kodate.get('prefecture', '')}{market_row_kodate.get('city', '')} (KODATE)"
                try:
                    sale_price_per_sqm = int(float(market_row_kodate.get('sale_price_per_sqm', 0))) or sale_price_per_sqm
                    construction_cost_per_sqm = int(float(market_row_kodate.get('construction_cost_per_sqm', 0))) or construction_cost_per_sqm
                except (ValueError, TypeError):
                    pass
            else:
                matched_area = f"{matched_area} → KODATE(建築費超過)"
                sale_price_per_sqm = self._estimate_sale_price(address, "KODATE")
                construction_cost_per_sqm = self._estimate_construction_cost(address, "KODATE")
            dev_ratios = self.DEV_COST_RATIOS["KODATE"]

        # 容積率がない場合は推定
        if floor_area_ratio is None:
            floor_area_ratio = self._estimate_far(zoning, dev_type)

        # 延床面積計算
        estimated_floor_area = None
        if land_area_sqm and floor_area_ratio:
            # KODATEは建売実態に合わせFARを1.5にキャップ（2階建て建売の上限）
            effective_far = min(floor_area_ratio, 1.5) if dev_type == "KODATE" else floor_area_ratio
            estimated_floor_area = land_area_sqm * effective_far * 0.95  # 5%減（共用部等）

        # デベ収支計算
        total_sales = None
        construction_total = None
        dev_expenses = None
        dev_profit = None
        dev_max_land = None
        dev_land_per_tsubo = None
        dev_land_per_sqm = None

        dev_ratios = self.DEV_COST_RATIOS.get(dev_type, self.DEV_COST_RATIOS["MANSION"])

        if land_area_sqm and estimated_floor_area and sale_price_per_sqm:
            # 土地面積あり: 延床から総販売額を計算し、残地価率でデベ最大買値を算出
            total_sales = int(estimated_floor_area * sale_price_per_sqm)
            # 建築費は実単価×延床、諸費用・利益は残地価率から逆算して参考表示
            construction_total = int(estimated_floor_area * construction_cost_per_sqm)
            dev_expenses = int(total_sales * dev_ratios["expenses"])
            dev_profit = int(total_sales * dev_ratios["profit"])
            # デベ最大買値: 残地価率（land ratio）で直接算出（実務的アプローチ）
            dev_max_land = int(total_sales * dev_ratios["land"])
            if dev_max_land < 0:
                dev_max_land = 0
            dev_land_per_sqm = int(dev_max_land / land_area_sqm)
            dev_land_per_tsubo = int(dev_land_per_sqm * 3.3058)

        elif not land_area_sqm and price > 0:
            # 土地面積不明: デベが土地1㎡に払える上限単価を算出し、坪単価のみ表示
            # 式: 延床販売単価 × FAR × 建設効率 × 残地価率 = デベ最大坪単価（土地）
            dev_max_per_land_sqm = sale_price_per_sqm * floor_area_ratio * 0.95 * dev_ratios["land"]
            if dev_max_per_land_sqm > 0:
                # 坪単価を算出（比較用）
                dev_land_per_sqm = int(dev_max_per_land_sqm)
                dev_land_per_tsubo = int(dev_max_per_land_sqm * 3.3058)
                # 参考: 売値 ÷ デベ適正坪単価 = 「この価格で買えるなら最低この面積が必要」
                implied_land_sqm = price / dev_max_per_land_sqm
                estimated_floor_area = implied_land_sqm * floor_area_ratio * 0.95
                total_sales = int(estimated_floor_area * sale_price_per_sqm)
                construction_total = int(estimated_floor_area * construction_cost_per_sqm)
                dev_expenses = int(total_sales * dev_ratios["expenses"])
                dev_profit = int(total_sales * dev_ratios["profit"])
                # dev_max_land は None のまま（面積不明で金額比較不能）
                # 評価は「土地面積確認要」に切り替え

        # 売主手取り考慮
        effective_price = seller_net_price if seller_net_price else price
        if seller_net_price:
            # 仲介手数料を上乗せした実際の取引価格
            effective_price = int(seller_net_price * 1.04)  # 手数料3%+税概算

        # 価格評価
        evaluation, ratio, comment, recommendation = self._evaluate_price(
            effective_price, dev_max_land, address, dev_type, dev_land_per_tsubo
        )

        # 戸数推定（マンション）
        units = None
        if dev_type == "MANSION" and estimated_floor_area:
            avg_unit_size = 65.0  # 平均専有面積65㎡と仮定
            units = max(1, int(estimated_floor_area * 0.75 / avg_unit_size))  # 専有率75%

        confidence = "high" if market_row else ("medium" if floor_area_ratio else "low")

        return DevLandResult(
            estimated_floor_area_sqm=round(estimated_floor_area, 1) if estimated_floor_area else None,
            estimated_floor_area_tsubo=round(estimated_floor_area / 3.3058, 1) if estimated_floor_area else None,
            estimated_units=units,
            total_sales_revenue=total_sales,
            construction_cost=construction_total,
            dev_expenses=dev_expenses,
            dev_profit_target=dev_profit,
            dev_max_land_price=dev_max_land,
            dev_land_price_per_tsubo=dev_land_per_tsubo,
            dev_land_price_per_sqm=dev_land_per_sqm,
            price_evaluation=evaluation,
            price_vs_dev_max=round(ratio, 2) if ratio else None,
            matched_area=matched_area,
            sale_price_used=sale_price_per_sqm,
            construction_cost_used=construction_cost_per_sqm,
            dev_type=dev_type,
            comment=comment,
            recommendation=recommendation,
            confidence=confidence,
        )

    def _auto_detect_dev_type(self, address: str, zoning: Optional[str], far: Optional[float]) -> str:
        """開発タイプを自動判定"""
        # 容積率200%以上 or 商業地域 → マンション
        if far and far >= 2.0:
            return "MANSION"
        if zoning and any(z in zoning for z in ["商業", "近隣商業"]):
            return "MANSION"
        # 住宅系 + 容積率低い → 建売
        if far and far <= 1.5:
            return "KODATE"
        # 東京23区内 → マンション傾向
        if address and any(k in address for k in ["東京都千代田区", "東京都港区", "東京都渋谷区", "東京都新宿区",
                                                    "東京都中央区", "東京都文京区", "東京都品川区", "東京都目黒区"]):
            return "MANSION"
        # デフォルト（郊外・容積率不明）→ 判定できないが MANSION を優先
        return "MANSION"

    def _find_market_data(self, address: str, dev_type: str) -> Optional[dict]:
        """エリアデータを検索"""
        if not self._data:
            return None
        best_score = 0
        best_row = None
        for row in self._data:
            if row.get('type', '') != dev_type.upper():
                continue
            score = 0
            pref = row.get('prefecture', '')
            city = row.get('city', '')
            area = row.get('area', '')
            if pref and pref in address:
                score += 30
            if city and city in address:
                score += 50
            if area and area in address:
                score += 20
            if score > best_score:
                best_score = score
                best_row = row
        return best_row if best_score >= 30 else None

    def _estimate_sale_price(self, address: str, dev_type: str) -> int:
        """データなし時の概算分譲単価"""
        major = any(a in address for a in ["東京都", "大阪府", "愛知県名古屋市"])
        if dev_type == "MANSION":
            return 700_000 if major else 400_000
        elif dev_type == "KODATE":
            return 400_000 if major else 250_000
        return 500_000

    def _estimate_construction_cost(self, address: str, dev_type: str) -> int:
        """データなし時の概算建築費"""
        major = any(a in address for a in ["東京都", "大阪府", "愛知県名古屋市"])
        if dev_type == "MANSION":
            return 480_000 if major else 430_000
        elif dev_type == "KODATE":
            return 290_000 if major else 260_000
        return 450_000

    def _estimate_far(self, zoning: Optional[str], dev_type: str) -> float:
        """容積率推定"""
        if zoning:
            mapping = {
                "第一種低層住居": 1.0, "第二種低層住居": 1.5,
                "第一種中高層住居": 2.0, "第二種中高層住居": 2.0,
                "第一種住居地域": 2.0, "第二種住居地域": 2.0,
                "準住居地域": 2.0, "近隣商業地域": 3.0,
                "商業地域": 5.0, "準工業地域": 2.0,
            }
            for key, val in mapping.items():
                if key in zoning:
                    return val
        return 2.0 if dev_type == "MANSION" else 1.5

    def _evaluate_price(self, price: int, dev_max: Optional[int], address: str,
                        dev_type: str, dev_per_tsubo: Optional[int]):
        """価格評価・コメント・推奨判断"""
        if dev_max is None or dev_max <= 0:
            # 土地面積不明: 坪単価での参考評価のみ
            if dev_per_tsubo:
                tsubo_man = dev_per_tsubo // 10000
                return (
                    "土地面積確認要",
                    None,
                    f"土地面積が未確認のため正確な買値計算ができません。"
                    f"デベが出せる上限坪単価は約{tsubo_man}万円/坪です。"
                    f"紹介元に土地面積（坪数）を確認し、「売値÷坪数」と比較してください。",
                    "情報確認が必要（土地面積確認後に再評価）"
                )
            return (
                "判定不可",
                None,
                "土地面積・容積率が不明のため正確な評価ができません。面積・容積率を確認してください。",
                "情報確認が必要"
            )

        ratio = price / dev_max
        tsubo_str = f"（デベ適正坪単価: {dev_per_tsubo:,}円/坪）" if dev_per_tsubo else ""

        if ratio <= 0.85:
            eval_str = "割安"
            comment = f"売値がデベ最大買値の{ratio:.0%}。割安水準でデベロッパーに提案できる。{tsubo_str}"
            rec = "追う"
        elif ratio <= 1.05:
            eval_str = "適正"
            comment = f"売値はデベ最大買値の{ratio:.0%}。適正水準。指値なしでも成立する可能性がある。{tsubo_str}"
            rec = "追う"
        elif ratio <= 1.20:
            eval_str = "やや高い"
            comment = (
                f"売値がデベ最大買値の{ratio:.0%}。"
                f"{int((ratio - 1) * 100)}%程度の指値交渉が必要。売主の最低ラインを確認のこと。{tsubo_str}"
            )
            rec = "条件次第"
        elif ratio <= 1.40:
            eval_str = "高い"
            comment = (
                f"売値がデベ最大買値の{ratio:.0%}。デベには厳しい水準。"
                f"大幅な指値（{int((1 - 1 / ratio) * 100)}%以上）か、売主の価格下落待ち。{tsubo_str}"
            )
            rec = "条件次第"
        else:
            eval_str = "高すぎる"
            comment = (
                f"売値がデベ最大買値の{ratio:.0%}。現状ではデベは動けない水準。"
                f"大幅な価格改定または別の出口（実需・自社保有）が必要。{tsubo_str}"
            )
            rec = "捨てる（現時点）"

        return eval_str, ratio, comment, rec
