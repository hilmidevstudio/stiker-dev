"""
SQLite Database Connection and Migration Manager for StickerDrop.
"""

import sqlite3
import os
from typing import Optional


SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_id TEXT NOT NULL UNIQUE,
    source_platform TEXT NOT NULL DEFAULT 'tiktok',
    source_video_id TEXT NOT NULL,
    source_comment_id TEXT NOT NULL UNIQUE,
    source_author TEXT NOT NULL,
    sticker_id TEXT,
    original_media_url TEXT NOT NULL,
    local_media_path TEXT NOT NULL,
    media_type TEXT NOT NULL,
    is_animated INTEGER NOT NULL DEFAULT 0,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    file_size INTEGER NOT NULL,
    frame_count INTEGER NOT NULL DEFAULT 1,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL UNIQUE,
    export_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stickers_source_comment_id ON stickers(source_comment_id);
CREATE INDEX IF NOT EXISTS idx_stickers_sha256 ON stickers(sha256);
CREATE INDEX IF NOT EXISTS idx_stickers_export_status ON stickers(export_status);

CREATE TABLE IF NOT EXISTS packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    publisher TEXT NOT NULL DEFAULT 'StickerDrop User',
    tray_image_path TEXT NOT NULL,
    is_animated INTEGER NOT NULL DEFAULT 0,
    sticker_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pack_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id INTEGER NOT NULL REFERENCES packs(id) ON DELETE CASCADE,
    sticker_id INTEGER NOT NULL REFERENCES stickers(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    emojis TEXT NOT NULL DEFAULT '["🔥"]',
    UNIQUE(pack_id, sticker_id),
    UNIQUE(pack_id, sort_order)
);
"""


class DatabaseManager:
    """Manages SQLite connection lifecycle and schema migrations."""

    def __init__(self, db_path: str = "data/stickerdrop.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        """Initializes tables and executes migrations."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_V1)
            # Record migration version 1
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (1, datetime('now'))"
                )
            conn.commit()
