from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class RepairItem:
    """修繕項目"""
    name: str           # 工事名称
    unit_cost: int      # 単価（円/㎡ or 円/戸 or 円/箇所）
    unit: str           # 単位
    urgency: str        # 緊急度（即時/5年以内/10年以内/20年以内）
    cost_estimate: int  # 費用見積もり（円）


@dataclass
class RepairCostResult:
    """修繕費積算結果"""
    immediate_cost: int          # 即時修繕費（円）
    five_year_cost: int          # 5年以内修繕費（円）
    ten_year_cost: int           # 10年以内修繕費（円）
    total_lifecycle_cost: int    # ライフサイクル総修繕費（円）
    repair_items: List[RepairItem]  # 修繕項目リスト
    comment: str                 # コメント
    inflation_adjusted: bool     # 2024年建築費高騰調整済みフラグ


class RepairCostEngine:
    """
    修繕費積算エンジン
    2024-2025年建築資材・人件費高騰（前年比+15〜25%）を反映
    国土交通省の修繕費標準（建物の種類・築年別）を参考
    """

    # 2024年修繕費単価（円/㎡）建築費高騰後
    UNIT_COSTS_2024 = {
        "外壁塗装_RC": 8500,        # RC造外壁塗装
        "外壁塗装_木造": 5500,      # 木造外壁塗装
        "屋上防水": 12000,          # 屋上防水
        "屋根葺替_木造": 15000,     # 木造屋根葺替
        "給排水設備更新": 45000,    # 給排水一式（円/戸）
        "電気設備更新": 25000,      # 電気設備（円/戸）
        "エレベーター更新": 7000000,  # エレベーター1基
        "エアコン更新": 200000,     # エアコン1台
        "外構整備": 15000,          # 外構（円/㎡）
        "室内リフォーム": 350000,   # 1戸あたり（フルリフォーム）
    }

    def estimate(
        self,
        asset_type_key: str,
        building_area_sqm: Optional[float],
        built_year: Optional[int],
        structure: Optional[str],
        planned_repairs_cost: Optional[int] = None,
        unit_count: Optional[int] = None,
        has_elevator: bool = False,
    ) -> RepairCostResult:
        """修繕費を積算"""
        current_year = 2025
        age = (current_year - built_year) if built_year else 20
        area = building_area_sqm or 100.0

        items: List[RepairItem] = []

        # 構造種別判定（structure 未入力時は asset_type_key から推定）
        is_rc = bool(structure and ("RC" in structure or "鉄筋" in structure or "SRC" in structure))
        is_wood = bool(structure and ("木造" in structure or "W造" in structure))
        is_steel = bool(structure and ("鉄骨" in structure or "S造" in structure))

        if not (is_rc or is_wood or is_steel):
            # 構造が未指定の場合は物件種別から推定
            if asset_type_key in ("APARTMENT_WOOD", "HOUSE"):
                is_wood = True
            elif asset_type_key in ("APARTMENT_WHOLE", "UNIT", "OFFICE", "COMMERCIAL", "HOTEL"):
                is_rc = True
            elif asset_type_key in ("FACTORY", "WAREHOUSE"):
                is_steel = True

        # 外壁塗装（築10年以上）
        if age >= 10:
            unit = (
                self.UNIT_COSTS_2024["外壁塗装_RC"]
                if is_rc
                else self.UNIT_COSTS_2024["外壁塗装_木造"]
            )
            urgency = "即時" if age >= 20 else "5年以内"
            cost = int(area * unit * 0.3)  # 外壁面積は延床の30%概算
            items.append(RepairItem("外壁塗装・補修", unit, "円/㎡", urgency, cost))

        # 屋上防水（RC・鉄骨造、築15年以上）
        if (is_rc or is_steel) and age >= 15:
            urgency = "即時" if age >= 25 else "5年以内"
            cost = int(area * self.UNIT_COSTS_2024["屋上防水"] * 0.15)
            items.append(
                RepairItem("屋上防水", self.UNIT_COSTS_2024["屋上防水"], "円/㎡", urgency, cost)
            )

        # 木造屋根葺替（築25年以上）
        if is_wood and age >= 25:
            cost = int(area * self.UNIT_COSTS_2024["屋根葺替_木造"] * 0.12)
            items.append(
                RepairItem(
                    "屋根葺替",
                    self.UNIT_COSTS_2024["屋根葺替_木造"],
                    "円/㎡",
                    "即時",
                    cost,
                )
            )

        # 給排水設備（築30年以上で更新、戸数ベース）
        if age >= 30 and unit_count:
            cost = unit_count * self.UNIT_COSTS_2024["給排水設備更新"]
            items.append(
                RepairItem(
                    "給排水設備更新",
                    self.UNIT_COSTS_2024["給排水設備更新"],
                    "円/戸",
                    "即時",
                    cost,
                )
            )

        # 電気設備（築25年以上、戸数ベース）
        if age >= 25 and unit_count:
            cost = unit_count * self.UNIT_COSTS_2024["電気設備更新"]
            urgency = "即時" if age >= 35 else "10年以内"
            items.append(
                RepairItem(
                    "電気設備更新",
                    self.UNIT_COSTS_2024["電気設備更新"],
                    "円/戸",
                    urgency,
                    cost,
                )
            )

        # ---- 木造アパート特有の修繕（戸数不明でも延床面積ベースで計上） ----
        if is_wood:
            # 給排水・給湯設備更新（築20年〜）戸数不明時は延床基準
            if age >= 20 and not unit_count:
                urgency = "即時" if age >= 30 else "5年以内"
                cost = int(area * 3000)  # 延床㎡×3,000円概算
                items.append(
                    RepairItem("給排水・給湯設備更新（概算）", 3000, "円/㎡", urgency, cost)
                )
            # 電気設備・給湯器更新（築15年〜）戸数不明時は延床基準
            if age >= 15 and not unit_count:
                urgency = "即時" if age >= 25 else "10年以内"
                cost = int(area * 2000)  # 延床㎡×2,000円概算
                items.append(
                    RepairItem("電気設備・給湯器更新（概算）", 2000, "円/㎡", urgency, cost)
                )
            # 内装リフォーム（投資物件の入居者入替時コスト、築10年〜）
            if age >= 10 and not unit_count:
                urgency = "5年以内" if age < 20 else "即時"
                cost = int(area * 5000)  # 延床㎡×5,000円概算
                items.append(
                    RepairItem("内装リフォーム（概算）", 5000, "円/㎡", urgency, cost)
                )

        # エレベーター（築20年以上）
        if has_elevator and age >= 20:
            urgency = "即時" if age >= 30 else "10年以内"
            items.append(
                RepairItem(
                    "エレベーター更新",
                    self.UNIT_COSTS_2024["エレベーター更新"],
                    "円/基",
                    urgency,
                    self.UNIT_COSTS_2024["エレベーター更新"],
                )
            )

        # 入力済み修繕費がある場合は追加
        if planned_repairs_cost and planned_repairs_cost > 0:
            items.append(
                RepairItem(
                    "売主申告修繕費",
                    planned_repairs_cost,
                    "円（申告値）",
                    "即時",
                    planned_repairs_cost,
                )
            )

        # 集計
        immediate = sum(i.cost_estimate for i in items if i.urgency == "即時")
        five_year = sum(i.cost_estimate for i in items if i.urgency == "5年以内")
        ten_year = sum(i.cost_estimate for i in items if i.urgency == "10年以内")
        twenty_year = sum(i.cost_estimate for i in items if i.urgency == "20年以内")
        total = immediate + five_year + ten_year + twenty_year

        # コメント生成
        if age >= 30:
            comment = (
                f"築{age}年。大規模修繕サイクルの節目。"
                "早急な修繕費用の確認と価格交渉への活用を推奨。2024年建築費高騰反映済み。"
            )
        elif age >= 20:
            comment = (
                f"築{age}年。外壁・防水等の経年劣化が進む段階。"
                "修繕費を価格折衝材料とすること。"
            )
        elif age >= 10:
            comment = (
                f"築{age}年。建物状態は比較的良好だが、外装等の定期メンテが必要。"
            )
        else:
            comment = f"築{age}年。新築〜築浅物件。大規模修繕の必要性は当面低い。"

        return RepairCostResult(
            immediate_cost=immediate,
            five_year_cost=five_year,
            ten_year_cost=ten_year,
            total_lifecycle_cost=total,
            repair_items=items,
            comment=comment,
            inflation_adjusted=True,
        )
