import csv
import json
import os
from datetime import datetime
from typing import List, Optional
from app.models.property import PropertyData, AssetType


STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "history")


class StorageService:
    def __init__(self, storage_dir: str = STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_deal(self, property_data: PropertyData, report: str, score: float, rank: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_slug = (property_data.property_name or "unnamed").replace(" ", "_")[:20]
        filename = f"{timestamp}_{name_slug}.json"
        filepath = os.path.join(self.storage_dir, filename)

        record = {
            "saved_at": timestamp,
            "property": property_data.model_dump(),
            "score": score,
            "rank": rank,
            "report_preview": report[:200],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)

        self._update_index(filename, property_data, score, rank, timestamp)
        return filepath

    def _update_index(self, filename: str, property_data: PropertyData,
                      score: float, rank: str, timestamp: str) -> None:
        index_path = os.path.join(self.storage_dir, "index.csv")
        is_new = not os.path.exists(index_path)
        with open(index_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["saved_at", "filename", "property_name", "asset_type",
                                  "address", "price", "score", "rank"])
            writer.writerow([
                timestamp, filename,
                property_data.property_name or "",
                property_data.asset_type.value,
                property_data.address,
                property_data.price,
                score, rank
            ])

    def list_deals(self) -> List[dict]:
        index_path = os.path.join(self.storage_dir, "index.csv")
        if not os.path.exists(index_path):
            return []
        with open(index_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def load_deal(self, filename: str) -> Optional[dict]:
        filepath = os.path.join(self.storage_dir, filename)
        if not os.path.exists(filepath):
            return None
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    def export_csv(self, output_path: str = "deals_export.csv") -> str:
        deals = self.list_deals()
        if not deals:
            return ""
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=deals[0].keys())
            writer.writeheader()
            writer.writerows(deals)
        return output_path
