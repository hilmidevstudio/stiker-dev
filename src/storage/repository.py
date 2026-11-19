"""
Persistent Sticker Repository for StickerDrop.
Implements ACID CRUD operations, deduplication, and library integrity verification.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import os
import uuid
import hashlib
import datetime
import sqlite3

from .db import DatabaseManager


@dataclass
class StickerRecord:
    id: int
    internal_id: str
    source_platform: str
    source_video_id: str
    source_comment_id: str
    source_author: str
    sticker_id: Optional[str]
    original_media_url: str
    local_media_path: str
    media_type: str
    is_animated: bool
    width: int
    height: int
    file_size: int
    frame_count: int
    duration_ms: int
    sha256: str
    export_status: str
    created_at: str
    updated_at: str


@dataclass
class IntegrityReport:
    total_records: int
    valid_records: int
    missing_files: List[str]
    corrupted_files: List[str]
    is_healthy: bool


class DuplicateStickerError(Exception):
    """Raised when an identical sticker exists in the library."""
    pass


class StickerRepository:
    """
    Manages persistent sticker entities and local media asset storage.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        media_root_dir: str = "data/media"
    ):
        self.db = db_manager
        self.media_root = os.path.abspath(media_root_dir)
        os.makedirs(self.media_root, exist_ok=True)

    def _row_to_record(self, row: sqlite3.Row) -> StickerRecord:
        return StickerRecord(
            id=row["id"],
            internal_id=row["internal_id"],
            source_platform=row["source_platform"],
            source_video_id=row["source_video_id"],
            source_comment_id=row["source_comment_id"],
            source_author=row["source_author"],
            sticker_id=row["sticker_id"],
            original_media_url=row["original_media_url"],
            local_media_path=row["local_media_path"],
            media_type=row["media_type"],
            is_animated=bool(row["is_animated"]),
            width=row["width"],
            height=row["height"],
            file_size=row["file_size"],
            frame_count=row["frame_count"],
            duration_ms=row["duration_ms"],
            sha256=row["sha256"],
            export_status=row["export_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def save_sticker(
        self,
        source_video_id: str,
        source_comment_id: str,
        source_author: str,
        original_media_url: str,
        media_bytes: bytes,
        is_animated: bool,
        width: int,
        height: int,
        frame_count: int = 1,
        duration_ms: int = 0,
        sticker_id: Optional[str] = None,
        source_platform: str = "tiktok"
    ) -> Tuple[StickerRecord, bool]:
        """
        Atomically saves sticker metadata and binary file.
        Returns (StickerRecord, was_created: bool).
        If comment_id or sha256 already exists, returns existing record with was_created=False.
        """
        # Step 1: Check Comment-level deduplication
        existing_by_comment = self.get_by_comment_id(source_comment_id)
        if existing_by_comment:
            return existing_by_comment, False

        # Step 2: Check Media-level deduplication (SHA-256)
        computed_sha256 = hashlib.sha256(media_bytes).hexdigest()
        existing_by_hash = self.get_by_sha256(computed_sha256)
        if existing_by_hash:
            return existing_by_hash, False

        # Step 3: Write media file atomically
        extension = ".awebp" if is_animated else ".webp"
        filename = f"{computed_sha256}{extension}"
        permanent_path = os.path.join(self.media_root, filename)
        temp_path = os.path.join(self.media_root, f"tmp_{uuid.uuid4().hex}{extension}")

        with open(temp_path, "wb") as f:
            f.write(media_bytes)
        os.replace(temp_path, permanent_path)

        relative_path = os.path.relpath(permanent_path, start=os.getcwd())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        internal_id = str(uuid.uuid4())
        media_type = "image/awebp" if is_animated else "image/webp"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stickers (
                    internal_id, source_platform, source_video_id, source_comment_id,
                    source_author, sticker_id, original_media_url, local_media_path,
                    media_type, is_animated, width, height, file_size, frame_count,
                    duration_ms, sha256, export_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                internal_id, source_platform, source_video_id, source_comment_id,
                source_author, sticker_id, original_media_url, relative_path,
                media_type, 1 if is_animated else 0, width, height, len(media_bytes),
                frame_count, duration_ms, computed_sha256, "PENDING", now, now
            ))
            conn.commit()
            record_id = cursor.lastrowid

        return self.get_by_id(record_id), True

    def get_by_id(self, record_id: int) -> Optional[StickerRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stickers WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_by_internal_id(self, internal_id: str) -> Optional[StickerRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stickers WHERE internal_id = ?", (internal_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_by_comment_id(self, comment_id: str) -> Optional[StickerRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stickers WHERE source_comment_id = ?", (str(comment_id),))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_by_sha256(self, sha256_hash: str) -> Optional[StickerRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stickers WHERE sha256 = ?", (sha256_hash,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def list_all(
        self,
        is_animated: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[StickerRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if is_animated is not None:
                cursor.execute(
                    "SELECT * FROM stickers WHERE is_animated = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (1 if is_animated else 0, limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT * FROM stickers ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def count(self, is_animated: Optional[bool] = None) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if is_animated is not None:
                cursor.execute(
                    "SELECT COUNT(*) FROM stickers WHERE is_animated = ?",
                    (1 if is_animated else 0,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM stickers")
            return cursor.fetchone()[0]

    def delete_by_internal_id(self, internal_id: str) -> bool:
        record = self.get_by_internal_id(internal_id)
        if not record:
            return False

        # Remove local file if present
        if os.path.exists(record.local_media_path):
            try:
                os.remove(record.local_media_path)
            except OSError:
                pass

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stickers WHERE internal_id = ?", (internal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def verify_library_integrity(self) -> IntegrityReport:
        """
        Scans all records, verifying that local media files exist on disk,
        match database size, and pass SHA-256 cryptographic verification.
        """
        all_records = self.list_all(limit=10000)
        missing: List[str] = []
        corrupted: List[str] = []
        valid_count = 0

        for r in all_records:
            if not os.path.exists(r.local_media_path):
                missing.append(r.internal_id)
                continue

            try:
                with open(r.local_media_path, "rb") as f:
                    content = f.read()
                if len(content) != r.file_size:
                    corrupted.append(f"{r.internal_id} (size mismatch)")
                    continue
                actual_sha = hashlib.sha256(content).hexdigest()
                if actual_sha != r.sha256:
                    corrupted.append(f"{r.internal_id} (hash mismatch)")
                    continue
                valid_count += 1
            except Exception as e:
                corrupted.append(f"{r.internal_id} ({str(e)})")

        is_healthy = (len(missing) == 0 and len(corrupted) == 0)
        return IntegrityReport(
            total_records=len(all_records),
            valid_records=valid_count,
            missing_files=missing,
            corrupted_files=corrupted,
            is_healthy=is_healthy
        )
