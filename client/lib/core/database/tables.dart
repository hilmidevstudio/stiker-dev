/// DDL SQL Statements for StickerDrop Local SQLite Database
/// Matches specification defined in docs/06-persistent-storage.md
class Tables {
  Tables._();

  static const String createSchemaMigrationsTable = '''
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
''';

  static const String createStickersTable = '''
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
''';

  static const String createIdxStickersSourceCommentId = '''
CREATE INDEX IF NOT EXISTS idx_stickers_source_comment_id ON stickers(source_comment_id);
''';

  static const String createIdxStickersSha256 = '''
CREATE INDEX IF NOT EXISTS idx_stickers_sha256 ON stickers(sha256);
''';

  static const String createIdxStickersExportStatus = '''
CREATE INDEX IF NOT EXISTS idx_stickers_export_status ON stickers(export_status);
''';

  static const String createPacksTable = '''
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
''';

  static const String createPackItemsTable = '''
CREATE TABLE IF NOT EXISTS pack_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id INTEGER NOT NULL REFERENCES packs(id) ON DELETE CASCADE,
    sticker_id INTEGER NOT NULL REFERENCES stickers(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    emojis TEXT NOT NULL DEFAULT '["🔥"]',
    UNIQUE(pack_id, sticker_id),
    UNIQUE(pack_id, sort_order)
);
''';

  /// Returns list of all initial creation statements in execution order
  static List<String> get initialSchemaStatements => [
        createSchemaMigrationsTable,
        createStickersTable,
        createIdxStickersSourceCommentId,
        createIdxStickersSha256,
        createIdxStickersExportStatus,
        createPacksTable,
        createPackItemsTable,
      ];
}
