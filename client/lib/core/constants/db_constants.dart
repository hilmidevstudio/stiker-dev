/// SQLite Database and Table Constants as specified in 06-persistent-storage.md
class DbConstants {
  DbConstants._();

  static const String databaseName = 'stickerdrop.db';
  static const int databaseVersion = 1;

  // Table Names
  static const String tableMigrations = 'schema_migrations';
  static const String tableStickers = 'stickers';
  static const String tablePacks = 'packs';
  static const String tablePackItems = 'pack_items';

  // Columns: schema_migrations
  static const String colMigrationVersion = 'version';
  static const String colMigrationAppliedAt = 'applied_at';

  // Columns: stickers
  static const String colStickerId = 'id';
  static const String colStickerInternalId = 'internal_id';
  static const String colStickerSourcePlatform = 'source_platform';
  static const String colStickerSourceVideoId = 'source_video_id';
  static const String colStickerSourceCommentId = 'source_comment_id';
  static const String colStickerSourceAuthor = 'source_author';
  static const String colStickerThirdPartyId = 'sticker_id';
  static const String colStickerOriginalMediaUrl = 'original_media_url';
  static const String colStickerLocalMediaPath = 'local_media_path';
  static const String colStickerMediaType = 'media_type';
  static const String colStickerIsAnimated = 'is_animated';
  static const String colStickerWidth = 'width';
  static const String colStickerHeight = 'height';
  static const String colStickerFileSize = 'file_size';
  static const String colStickerFrameCount = 'frame_count';
  static const String colStickerDurationMs = 'duration_ms';
  static const String colStickerSha256 = 'sha256';
  static const String colStickerExportStatus = 'export_status';
  static const String colStickerCreatedAt = 'created_at';
  static const String colStickerUpdatedAt = 'updated_at';

  // Export Status Enum Values
  static const String exportStatusPending = 'PENDING';
  static const String exportStatusExported = 'EXPORTED';
  static const String exportStatusFailed = 'FAILED';

  // Columns: packs
  static const String colPackId = 'id';
  static const String colPackIdentifier = 'identifier';
  static const String colPackName = 'name';
  static const String colPackPublisher = 'publisher';
  static const String colPackTrayImagePath = 'tray_image_path';
  static const String colPackIsAnimated = 'is_animated';
  static const String colPackStickerCount = 'sticker_count';
  static const String colPackCreatedAt = 'created_at';
  static const String colPackUpdatedAt = 'updated_at';

  // Columns: pack_items
  static const String colPackItemId = 'id';
  static const String colPackItemPackId = 'pack_id';
  static const String colPackItemStickerId = 'sticker_id';
  static const String colPackItemSortOrder = 'sort_order';
  static const String colPackItemEmojis = 'emojis';
}
