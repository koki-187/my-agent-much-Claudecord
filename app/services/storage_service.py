import csv
import json
import logging
import os
from datetime import datetime
from typing import List, Optional
from app.models.property import PropertyData, AssetType


STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "history")

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, storage_dir: str = STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_deal(self, property_data: PropertyData, report: str, score: float, rank: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        existing_filename = self._find_existing_deal(property_data.address, property_data.price)
        if existing_filename:
            filename = existing_filename
        else:
            # パストラバーサル防止: ディレクトリ区切り文字・制御文字を除去
            import re
            raw_slug = property_data.property_name or "unnamed"
            name_slug = re.sub(r'[/\\<>:"|?*\x00-\x1f]', '', raw_slug).replace(" ", "_")[:20] or "unnamed"
            filename = f"{timestamp}_{name_slug}.json"

        filepath = os.path.join(self.storage_dir, filename)

        record = {
            "saved_at": timestamp,
            "property": property_data.model_dump(),
            "score": score,
            "rank": rank,
            "report_preview": report[:200],
            "report": report,
            "property_name": property_data.property_name or "",
            "asset_type": property_data.asset_type.value,
            "address": property_data.address,
            "price": property_data.price,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)

        self._update_index(filename, property_data, score, rank, timestamp,
                           is_update=existing_filename is not None)
        logger.info("案件保存: %s", filepath)
        self._auto_backup()
        return filepath

    def _find_existing_deal(self, address: str, price: int) -> Optional[str]:
        """同一住所・価格の既存ファイル名を返す（なければNone）。
        旧: O(n) 全件ループ → 新: dict ルックアップ O(1)。
        list_deals() の副作用で _deals_index_dict が構築される。"""
        self.list_deals()   # キャッシュ更新トリガ
        return StorageService._deals_index_dict.get((address, str(price))) or None

    def _update_index(self, filename: str, property_data: PropertyData,
                      score: float, rank: str, timestamp: str,
                      is_update: bool = False) -> None:
        index_path = os.path.join(self.storage_dir, "index.csv")

        if is_update and os.path.exists(index_path):
            # 既存レコードを読み込み、該当ファイル名の行を差し替える
            with open(index_path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

            updated = False
            for row in rows:
                if row.get("filename") == filename:
                    row["saved_at"] = timestamp
                    row["property_name"] = property_data.property_name or ""
                    row["asset_type"] = property_data.asset_type.value
                    row["address"] = property_data.address
                    row["price"] = str(property_data.price)
                    row["score"] = str(score)
                    row["rank"] = rank
                    updated = True
                    break

            if updated:
                fieldnames = ["saved_at", "filename", "property_name", "asset_type",
                              "address", "price", "score", "rank"]
                with open(index_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                return

        # 新規追加（またはis_updateだがindexに該当行がなかった場合のフォールバック）
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

    def _auto_backup(self) -> None:
        """日次バックアップ: app/data/backup/YYYYMMDD/ にhistoryディレクトリをコピー"""
        import shutil
        today = datetime.now().strftime("%Y%m%d")
        backup_base = os.path.join(os.path.dirname(self.storage_dir), "backup")
        backup_dir = os.path.join(backup_base, today)

        # 今日のバックアップがすでにある場合はスキップ
        if os.path.exists(backup_dir):
            return

        try:
            os.makedirs(backup_base, exist_ok=True)
            shutil.copytree(self.storage_dir, backup_dir)
            # 古いバックアップを削除（30日以上前）
            self._cleanup_old_backups(backup_base, keep_days=30)
        except Exception as e:
            logger.warning("バックアップ失敗: %s", e)

    def _cleanup_old_backups(self, backup_base: str, keep_days: int = 30) -> None:
        """古いバックアップディレクトリを削除"""
        import shutil
        cutoff = datetime.now()
        for name in os.listdir(backup_base):
            try:
                backup_date = datetime.strptime(name, "%Y%m%d")
                age_days = (cutoff - backup_date).days
                if age_days > keep_days:
                    shutil.rmtree(os.path.join(backup_base, name), ignore_errors=True)
            except ValueError:
                pass  # YYYYMMDD形式でないディレクトリはスキップ

    # ── インメモリキャッシュ (mtime ベース無効化) ──
    _deals_cache: List[dict] = []
    _deals_cache_mtime: float = 0.0
    _deals_index_dict: dict = {}   # (address, price) → filename の高速ルックアップ用

    def list_deals(self) -> List[dict]:
        """index.csv から全案件メタを返す。mtime キャッシュで I/O 最小化。"""
        index_path = os.path.join(self.storage_dir, "index.csv")
        if not os.path.exists(index_path):
            return []
        try:
            mtime = os.path.getmtime(index_path)
        except OSError:
            mtime = 0.0
        # ファイル更新がなければキャッシュを返す (O(0))
        if mtime == StorageService._deals_cache_mtime and StorageService._deals_cache:
            return StorageService._deals_cache
        # 更新あり → CSV 再読込 + dict 化
        with open(index_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        StorageService._deals_cache = rows
        StorageService._deals_cache_mtime = mtime
        StorageService._deals_index_dict = {
            (r.get("address", ""), str(r.get("price", ""))): r.get("filename", "")
            for r in rows
        }
        return rows

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
