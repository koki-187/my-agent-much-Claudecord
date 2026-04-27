from typing import List
from app.models.property import PropertyData
from app.models.client import ClientData


class BuyerMatchingEngine:
    def match_clients(self, property_data: PropertyData, clients: List[ClientData]) -> List[dict]:
        matched: List[dict] = []

        for client in clients:
            score = 0
            reasons: List[str] = []

            if client.max_price and property_data.price <= client.max_price:
                score += 30
                reasons.append("予算内")

            if client.min_yield:
                net_yield = property_data.net_yield
                if net_yield and net_yield >= client.min_yield:
                    score += 30
                    reasons.append("希望利回りを満たす")

            for area in client.target_areas:
                if area in property_data.address:
                    score += 30
                    reasons.append("希望エリアに該当")

            if score >= 50:
                matched.append({
                    "client_name": client.client_name,
                    "score": score,
                    "reasons": reasons
                })

        return sorted(matched, key=lambda x: x["score"], reverse=True)
