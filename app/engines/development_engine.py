from app.models.property import PropertyData


class DevelopmentEngine:
    def score_development(self, property_data: PropertyData) -> int:
        score = 70

        if property_data.road_access:
            if "再建築不可" in property_data.road_access:
                return 10
            if "不明" in property_data.road_access:
                score -= 20

        if property_data.zoning is None:
            score -= 10

        if property_data.floor_area_ratio is None:
            score -= 10

        if property_data.legal_notes:
            score -= 20

        return max(min(score, 100), 0)
