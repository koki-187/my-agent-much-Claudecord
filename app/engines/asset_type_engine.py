from typing import Tuple
from app.models.property import PropertyData, AssetType


# 物件種別ごとの目標利回り（デフォルト）
TARGET_YIELDS: dict[AssetType, float] = {
    AssetType.APARTMENT_WHOLE: 0.075,
    AssetType.APARTMENT_WOOD: 0.085,
    AssetType.UNIT: 0.060,
    AssetType.HOUSE: 0.065,
    AssetType.LAND: 0.000,  # 土地は収益還元なし
    AssetType.COMMERCIAL: 0.065,
    AssetType.OFFICE: 0.055,
    AssetType.FACTORY: 0.070,
}

# 物件種別ごとのスコアウェイト（price, yield, liquidity, development, risk, broker）
SCORE_WEIGHTS: dict[AssetType, Tuple[float, float, float, float, float, float]] = {
    AssetType.APARTMENT_WHOLE:  (0.25, 0.20, 0.15, 0.15, 0.15, 0.10),
    AssetType.APARTMENT_WOOD:   (0.25, 0.20, 0.15, 0.10, 0.20, 0.10),
    AssetType.UNIT:             (0.25, 0.20, 0.20, 0.05, 0.20, 0.10),
    AssetType.HOUSE:            (0.30, 0.15, 0.20, 0.10, 0.15, 0.10),
    AssetType.LAND:             (0.20, 0.00, 0.15, 0.35, 0.20, 0.10),  # 土地は開発重視
    AssetType.COMMERCIAL:       (0.20, 0.25, 0.15, 0.10, 0.20, 0.10),
    AssetType.OFFICE:           (0.20, 0.25, 0.15, 0.10, 0.20, 0.10),
    AssetType.FACTORY:          (0.25, 0.20, 0.15, 0.10, 0.20, 0.10),
}


class AssetTypeEngine:
    def get_target_yield(self, asset_type: AssetType) -> float:
        return TARGET_YIELDS.get(asset_type, 0.075)

    def get_score_weights(self, asset_type: AssetType) -> Tuple[float, float, float, float, float, float]:
        return SCORE_WEIGHTS.get(asset_type, (0.25, 0.20, 0.15, 0.15, 0.15, 0.10))

    def detect_asset_specific_risks(self, property_data: PropertyData) -> list[dict]:
        """物件種別固有のリスクを検知する"""
        risks = []
        asset_type = property_data.asset_type

        if asset_type == AssetType.UNIT:
            if property_data.management_fee_monthly and property_data.management_fee_monthly >= 30000:
                risks.append({
                    "type": "管理費高額リスク",
                    "level": "medium",
                    "message": f"管理費が月{property_data.management_fee_monthly:,}円と高く、実質利回りを圧迫する"
                })
            if property_data.repair_reserve_monthly and property_data.repair_reserve_monthly >= 20000:
                risks.append({
                    "type": "修繕積立金リスク",
                    "level": "medium",
                    "message": f"修繕積立金が月{property_data.repair_reserve_monthly:,}円と高い"
                })

        elif asset_type == AssetType.LAND:
            if property_data.floor_area_ratio is None:
                risks.append({
                    "type": "容積率未確認",
                    "level": "high",
                    "message": "容積率が未確認。建築可能面積・価値の根拠が不明"
                })
            if property_data.road_access and "4m未満" in property_data.road_access:
                risks.append({
                    "type": "接道幅員不足",
                    "level": "high",
                    "message": "接道幅員4m未満の可能性。セットバック必要で実効面積が減少"
                })
            if property_data.zoning is None:
                risks.append({
                    "type": "用途地域未確認",
                    "level": "high",
                    "message": "用途地域未確認。開発可能用途・建蔽率・容積率が不明"
                })

        elif asset_type in (AssetType.COMMERCIAL, AssetType.OFFICE):
            if property_data.tenant_name is None:
                risks.append({
                    "type": "テナント情報不明",
                    "level": "high",
                    "message": "テナント情報不明。退去リスク・賃料継続性が判断できない"
                })
            from datetime import datetime as _dt
            if property_data.lease_expiry:
                try:
                    expiry_dt = _dt.strptime(property_data.lease_expiry, "%Y-%m-%d")
                    months_remaining = (expiry_dt - _dt.now()).days / 30
                    if months_remaining <= 6:
                        risks.append({
                            "type": "テナント退去リスク（緊急）",
                            "level": "critical",
                            "message": f"賃貸借契約満了まで約{int(months_remaining)}ヶ月。退去後の空室・NOI消失リスクが極めて高い。即座にテナント意向確認が必要。"
                        })
                    elif months_remaining <= 12:
                        risks.append({
                            "type": "テナント退去リスク（高）",
                            "level": "high",
                            "message": f"賃貸借契約満了まで約{int(months_remaining)}ヶ月。早急なテナント継続交渉・代替テナント準備が必要。"
                        })
                    elif months_remaining <= 24:
                        risks.append({
                            "type": "賃貸借契約更新リスク",
                            "level": "medium",
                            "message": f"賃貸借契約満了まで約{int(months_remaining/12*10)/10}年。次回更新条件・賃料改定に注意。"
                        })
                    # 24ヶ月超はリスクなし（正常）
                except (ValueError, TypeError):
                    risks.append({
                        "type": "契約満了日不明",
                        "level": "medium",
                        "message": "賃貸借契約満了日の形式が不正。短期退去リスクを排除できない。"
                    })
            else:
                risks.append({
                    "type": "契約満了日不明",
                    "level": "medium",
                    "message": "賃貸借契約満了日が不明。短期退去リスクを排除できない"
                })
            if property_data.lease_type and "普通" in property_data.lease_type:
                risks.append({
                    "type": "普通借家リスク",
                    "level": "medium",
                    "message": "普通借家契約。テナント退去要請が難しく、賃料改定に制約"
                })

        elif asset_type == AssetType.FACTORY:
            if property_data.zoning and "工業" not in property_data.zoning and "準工業" not in property_data.zoning:
                risks.append({
                    "type": "用途地域ミスマッチ",
                    "level": "high",
                    "message": "工業系用途地域以外の可能性。操業継続・転用・出口が限定される"
                })
            if property_data.truck_access is None:
                risks.append({
                    "type": "トラック接車未確認",
                    "level": "medium",
                    "message": "大型トラック接車可否未確認。工場・倉庫用途の死活問題"
                })

        elif asset_type == AssetType.APARTMENT_WOOD:
            if property_data.built_year and property_data.built_year < 2000:
                risks.append({
                    "type": "木造老朽化リスク",
                    "level": "medium",
                    "message": "木造の経年劣化。屋根・外壁・設備の大規模修繕リスクが高い"
                })

        elif asset_type == AssetType.HOUSE:
            if property_data.current_status and "空家" in property_data.current_status:
                risks.append({
                    "type": "空家リスク",
                    "level": "medium",
                    "message": "空家状態。賃借人確保または実需需要の有無を確認する必要あり"
                })

        return risks

    def get_asset_type_label(self, asset_type: AssetType) -> str:
        return asset_type.value

    def get_liquidity_base_score(self, asset_type: AssetType) -> int:
        """物件種別ごとの流動性ベーススコア"""
        base_scores = {
            AssetType.APARTMENT_WHOLE: 70,
            AssetType.APARTMENT_WOOD: 65,
            AssetType.UNIT: 75,
            AssetType.HOUSE: 72,
            AssetType.LAND: 68,
            AssetType.COMMERCIAL: 55,
            AssetType.OFFICE: 50,
            AssetType.FACTORY: 45,
        }
        return base_scores.get(asset_type, 70)
