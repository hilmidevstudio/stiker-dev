import 'package:sqflite_common/sqlite_api.dart';
import '../../../core/constants/db_constants.dart';
import '../../../core/database/database_helper.dart';
import '../models/sticker_model.dart';
import '../storage/sha256_storage_manager.dart';

/// Integrity check report for persistent library
class LibraryIntegrityReport {
  final int totalCount;
  final int validCount;
  final List<int> missingFileStickerIds;
  final List<int> corruptHashStickerIds;

  const LibraryIntegrityReport({
    required this.totalCount,
    required this.validCount,
    required this.missingFileStickerIds,
    required this.corruptHashStickerIds,
  });

  bool get isHealthy =>
      missingFileStickerIds.isEmpty && corruptHashStickerIds.isEmpty;
}

/// SQLite Repository for managing Stickers persistence and deduplication
/// Implements specifications from ADR-002, ADR-005, and docs/06-persistent-storage.md
class StickerRepository {
  final DatabaseHelper _dbHelper;

  StickerRepository({DatabaseHelper? dbHelper})
      : _dbHelper = dbHelper ?? DatabaseHelper.instance;

  Future<Database> get _db async => await _dbHelper.database;

  /// Insert a new sticker with Two-Tier Deduplication (ADR-005)
  /// Returns existing record if duplicate comment or duplicate media is found
  Future<StickerModel> insertSticker(StickerModel sticker) async {
    final db = await _db;

    // Gate 1: Comment-Level Deduplication (ADR-005 Section 4.1)
    final existingByComment =
        await getStickerByCommentId(sticker.sourceCommentId);
    if (existingByComment != null) {
      return existingByComment;
    }

    // Gate 2: Media-Level Deduplication (ADR-005 Section 4.2)
    // The SQLite schema enforces UNIQUE(sha256). If identical media already exists,
    // return existing record avoiding redundant storage.
    final existingBySha256 = await getStickerBySha256(sticker.sha256);
    if (existingBySha256 != null) {
      return existingBySha256;
    }

    // Insert new unique sticker
    final id = await db.insert(
      DbConstants.tableStickers,
      sticker.toMap(includeId: false),
      conflictAlgorithm: ConflictAlgorithm.abort,
    );

    return sticker.copyWith(id: id);
  }

  /// Retrieve sticker by primary key ID
  Future<StickerModel?> getStickerById(int id) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tableStickers,
      where: '${DbConstants.colStickerId} = ?',
      whereArgs: [id],
      limit: 1,
    );

    if (results.isEmpty) return null;
    return StickerModel.fromMap(results.first);
  }

  /// Retrieve sticker by source comment ID (Gate 1 lookup)
  Future<StickerModel?> getStickerByCommentId(String commentId) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tableStickers,
      where: '${DbConstants.colStickerSourceCommentId} = ?',
      whereArgs: [commentId],
      limit: 1,
    );

    if (results.isEmpty) return null;
    return StickerModel.fromMap(results.first);
  }

  /// Retrieve sticker by SHA-256 hash (Gate 2 lookup)
  Future<StickerModel?> getStickerBySha256(String sha256) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tableStickers,
      where: '${DbConstants.colStickerSha256} = ?',
      whereArgs: [sha256],
      limit: 1,
    );

    if (results.isEmpty) return null;
    return StickerModel.fromMap(results.first);
  }

  /// List stickers with optional filters (animated, export status)
  Future<List<StickerModel>> getAllStickers({
    bool? isAnimated,
    String? exportStatus,
  }) async {
    final db = await _db;
    final whereClauses = <String>[];
    final whereArgs = <dynamic>[];

    if (isAnimated != null) {
      whereClauses.add('${DbConstants.colStickerIsAnimated} = ?');
      whereArgs.add(isAnimated ? 1 : 0);
    }

    if (exportStatus != null) {
      whereClauses.add('${DbConstants.colStickerExportStatus} = ?');
      whereArgs.add(exportStatus);
    }

    final whereString =
        whereClauses.isNotEmpty ? whereClauses.join(' AND ') : null;

    final results = await db.query(
      DbConstants.tableStickers,
      where: whereString,
      whereArgs: whereArgs.isNotEmpty ? whereArgs : null,
      orderBy: '${DbConstants.colStickerId} DESC',
    );

    return results.map((map) => StickerModel.fromMap(map)).toList();
  }

  /// Update export status (PENDING, EXPORTED, FAILED)
  Future<int> updateExportStatus(int id, String newStatus) async {
    final db = await _db;
    return await db.update(
      DbConstants.tableStickers,
      {
        DbConstants.colStickerExportStatus: newStatus,
        DbConstants.colStickerUpdatedAt:
            DateTime.now().toUtc().toIso8601String(),
      },
      where: '${DbConstants.colStickerId} = ?',
      whereArgs: [id],
    );
  }

  /// Delete sticker from database
  Future<int> deleteSticker(int id) async {
    final db = await _db;
    return await db.delete(
      DbConstants.tableStickers,
      where: '${DbConstants.colStickerId} = ?',
      whereArgs: [id],
    );
  }

  /// Startup Health Check & Library Integrity Scanner
  /// Implements 06-persistent-storage.md Section 5.2
  Future<LibraryIntegrityReport> verifyLibraryIntegrity(
    Sha256StorageManager storageManager,
  ) async {
    final allStickers = await getAllStickers();
    final missingIds = <int>[];
    final corruptIds = <int>[];
    int validCount = 0;

    for (final sticker in allStickers) {
      final stickerId = sticker.id!;
      final file = storageManager.getFileForRelativePath(sticker.localMediaPath);

      if (!await file.exists()) {
        missingIds.add(stickerId);
        continue;
      }

      final actualSize = await file.length();
      final actualHash = await Sha256StorageManager.computeFileSha256(file);

      if (actualSize != sticker.fileSize || actualHash != sticker.sha256) {
        corruptIds.add(stickerId);
      } else {
        validCount++;
      }
    }

    return LibraryIntegrityReport(
      totalCount: allStickers.length,
      validCount: validCount,
      missingFileStickerIds: missingIds,
      corruptHashStickerIds: corruptIds,
    );
  }
}
