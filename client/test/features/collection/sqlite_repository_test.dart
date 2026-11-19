import 'dart:io';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:test/test.dart';

import 'package:client/core/database/database_helper.dart';
import 'package:client/core/constants/db_constants.dart';
import 'package:client/features/collection/models/sticker_model.dart';
import 'package:client/features/collection/models/pack_model.dart';
import 'package:client/features/collection/models/pack_item_model.dart';
import 'package:client/features/collection/repositories/sticker_repository.dart';
import 'package:client/features/collection/repositories/pack_repository.dart';
import 'package:client/features/collection/storage/sha256_storage_manager.dart';

/// Utility to build a test StickerModel with minimal required fields
StickerModel buildTestSticker({
  String sourceCommentId = 'comment_001',
  String sourceVideoId = 'video_001',
  String sha256 = 'aaabbbccc111222333deadbeef00000000000000000000000000000000000001',
  bool isAnimated = true,
}) {
  return StickerModel(
    sourceVideoId: sourceVideoId,
    sourceCommentId: sourceCommentId,
    sourceAuthor: '@crazyolshop1',
    originalMediaUrl:
        'https://cdn.tiktok.com/sticker/$sourceCommentId.awebp',
    localMediaPath: 'media/$sha256.awebp',
    mediaType: 'image/awebp',
    isAnimated: isAnimated,
    width: 300,
    height: 300,
    fileSize: 128000,
    sha256: sha256,
  );
}

void main() {
  // Initialize sqflite FFI for desktop/pure-Dart test execution
  sqfliteFfiInit();
  final factory = databaseFactoryFfi;

  late DatabaseHelper dbHelper;
  late StickerRepository stickerRepo;
  late PackRepository packRepo;
  late Directory tempDir;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('stickerdrop_test_');
    // Use forTesting() — isolated instance with in-memory SQLite (ADR-002)
    dbHelper = DatabaseHelper.forTesting(
      factory: factory,
      databasePath: inMemoryDatabasePath,
    );

    stickerRepo = StickerRepository(dbHelper: dbHelper);
    packRepo = PackRepository(dbHelper: dbHelper);
  });

  tearDown(() async {
    await dbHelper.close();
    await dbHelper.reset();
    if (await tempDir.exists()) {
      await tempDir.delete(recursive: true);
    }
  });

  // ─────────────────────────────────────────────
  // SECTION 1: SQLite Schema Initialization
  // ─────────────────────────────────────────────
  group('SQLite Schema Initialization', () {
    test('Schema_v1 creates stickers, packs, pack_items, and schema_migrations tables',
        () async {
      final db = await dbHelper.database;
      final tables = await db.rawQuery(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
      );
      final tableNames = tables.map((r) => r['name'] as String).toList();

      expect(tableNames, containsAll([
        DbConstants.tableMigrations,
        DbConstants.tableStickers,
        DbConstants.tablePacks,
        DbConstants.tablePackItems,
      ]));
    });

    test('schema_migrations table records initial version 1', () async {
      final db = await dbHelper.database;
      final rows = await db.query(DbConstants.tableMigrations);
      expect(rows.length, equals(1));
      expect(rows.first[DbConstants.colMigrationVersion], equals(1));
    });

    test('PRAGMA foreign_keys returns ON', () async {
      final db = await dbHelper.database;
      final result = await db.rawQuery('PRAGMA foreign_keys');
      expect(result.first['foreign_keys'], equals(1));
    });

    test('Required indexes exist on stickers table', () async {
      final db = await dbHelper.database;
      final indexes = await db.rawQuery(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='stickers'",
      );
      final indexNames = indexes.map((r) => r['name'] as String).toList();
      expect(indexNames, contains('idx_stickers_source_comment_id'));
      expect(indexNames, contains('idx_stickers_sha256'));
      expect(indexNames, contains('idx_stickers_export_status'));
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 2: Sticker Insert & Query
  // ─────────────────────────────────────────────
  group('Sticker Insert & Query', () {
    test('Insert and retrieve sticker by ID', () async {
      final sticker = buildTestSticker();
      final inserted = await stickerRepo.insertSticker(sticker);

      expect(inserted.id, isNotNull);
      expect(inserted.id, greaterThan(0));

      final fetched = await stickerRepo.getStickerById(inserted.id!);
      expect(fetched, isNotNull);
      expect(fetched!.sourceCommentId, equals('comment_001'));
      expect(fetched.sha256,
          equals('aaabbbccc111222333deadbeef00000000000000000000000000000000000001'));
      expect(fetched.exportStatus, equals(DbConstants.exportStatusPending));
      expect(fetched.isAnimated, isTrue);
    });

    test('getAllStickers returns all inserted stickers', () async {
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_1',
        sha256: 'sha256_a_111111111111111111111111111111111111111111111111111111111',
      ));
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_2',
        sha256: 'sha256_b_222222222222222222222222222222222222222222222222222222222',
        isAnimated: false,
      ));

      final all = await stickerRepo.getAllStickers();
      expect(all.length, equals(2));
    });

    test('getAllStickers filters by isAnimated', () async {
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_anim',
        sha256: 'sha_anim_111111111111111111111111111111111111111111111111111111',
        isAnimated: true,
      ));
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_static',
        sha256: 'sha_stat_222222222222222222222222222222222222222222222222222222',
        isAnimated: false,
      ));

      final animatedOnly = await stickerRepo.getAllStickers(isAnimated: true);
      final staticOnly = await stickerRepo.getAllStickers(isAnimated: false);

      expect(animatedOnly.length, equals(1));
      expect(animatedOnly.first.isAnimated, isTrue);
      expect(staticOnly.length, equals(1));
      expect(staticOnly.first.isAnimated, isFalse);
    });

    test('updateExportStatus changes status to EXPORTED', () async {
      final inserted = await stickerRepo.insertSticker(buildTestSticker());
      expect(inserted.exportStatus, equals(DbConstants.exportStatusPending));

      await stickerRepo.updateExportStatus(
          inserted.id!, DbConstants.exportStatusExported);

      final fetched = await stickerRepo.getStickerById(inserted.id!);
      expect(fetched!.exportStatus, equals(DbConstants.exportStatusExported));
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 3: ADR-005 Two-Tier Deduplication
  // ─────────────────────────────────────────────
  group('ADR-005: Two-Tier Deduplication', () {
    test('[Gate 1] Duplicate source_comment_id returns existing record without re-insert',
        () async {
      final sticker = buildTestSticker(sourceCommentId: 'cmt_dup');
      final first = await stickerRepo.insertSticker(sticker);
      expect(first.id, isNotNull);

      // Attempt re-insert with same comment ID
      final second = await stickerRepo.insertSticker(sticker.copyWith(
        sha256: 'totally_different_sha_but_same_comment_111111111111111111111',
      ));

      // Must return existing record (same ID)
      expect(second.id, equals(first.id));

      // Only one record should exist
      final all = await stickerRepo.getAllStickers();
      expect(all.length, equals(1));
    });

    test('[Gate 2] Duplicate sha256 returns existing record (same media, different comment)',
        () async {
      const sharedHash =
          'shared_media_sha256_abcdef1234567890abcdef1234567890abcdef1234';

      final sticker1 = buildTestSticker(
        sourceCommentId: 'cmt_first',
        sha256: sharedHash,
      );
      final first = await stickerRepo.insertSticker(sticker1);
      expect(first.id, isNotNull);

      // Different comment ID but identical SHA-256 binary content
      final sticker2 = buildTestSticker(
        sourceCommentId: 'cmt_second_different_comment',
        sha256: sharedHash, // Same binary content
      );
      final second = await stickerRepo.insertSticker(sticker2);

      // Must return first record (same SHA256)
      expect(second.id, equals(first.id));

      // Only one record should exist
      final all = await stickerRepo.getAllStickers();
      expect(all.length, equals(1));
    });

    test('Distinct comment + distinct sha256 creates two separate records', () async {
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_x',
        sha256: 'sha_x_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      ));
      await stickerRepo.insertSticker(buildTestSticker(
        sourceCommentId: 'cmt_y',
        sha256: 'sha_y_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      ));

      final all = await stickerRepo.getAllStickers();
      expect(all.length, equals(2));
    });

    test('getStickerByCommentId returns correct record', () async {
      final inserted = await stickerRepo.insertSticker(
        buildTestSticker(sourceCommentId: 'cmt_find_me'),
      );

      final found = await stickerRepo.getStickerByCommentId('cmt_find_me');
      expect(found, isNotNull);
      expect(found!.id, equals(inserted.id));

      final notFound =
          await stickerRepo.getStickerByCommentId('cmt_does_not_exist');
      expect(notFound, isNull);
    });

    test('getStickerBySha256 returns correct record', () async {
      const hash =
          'specific_sha256_000000000000000000000000000000000000000000000';
      final inserted =
          await stickerRepo.insertSticker(buildTestSticker(sha256: hash));

      final found = await stickerRepo.getStickerBySha256(hash);
      expect(found, isNotNull);
      expect(found!.id, equals(inserted.id));

      final notFound = await stickerRepo
          .getStickerBySha256('nonexistent_sha256_xxxxxxxxxxxxxxxxxxxx');
      expect(notFound, isNull);
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 4: Pack & PackItem Operations
  // ─────────────────────────────────────────────
  group('Pack & PackItem Repository', () {
    test('Insert and retrieve pack by identifier', () async {
      final pack = PackModel(
        identifier: 'stickerdrop_anim_001',
        name: 'StickerDrop Animated 1',
        trayImagePath: 'media/tray_icon.png',
        isAnimated: true,
      );
      final inserted = await packRepo.insertPack(pack);

      expect(inserted.id, isNotNull);

      final fetched =
          await packRepo.getPackByIdentifier('stickerdrop_anim_001');
      expect(fetched, isNotNull);
      expect(fetched!.name, equals('StickerDrop Animated 1'));
      expect(fetched.isAnimated, isTrue);
    });

    test('addStickerToPack creates pack_items record', () async {
      final pack = await packRepo.insertPack(PackModel(
        identifier: 'pack_items_test',
        name: 'Test Pack',
        trayImagePath: 'media/tray.png',
      ));

      final sticker = await stickerRepo.insertSticker(buildTestSticker());

      await packRepo.addStickerToPack(PackItemModel(
        packId: pack.id!,
        stickerId: sticker.id!,
        sortOrder: 0,
        emojis: ['🔥', '🗿'],
      ));

      final items = await packRepo.getPackItems(pack.id!);
      expect(items.length, equals(1));
      expect(items.first.stickerId, equals(sticker.id));
      expect(items.first.emojis, containsAll(['🔥', '🗿']));
    });

    test('getAllPacks filters by isAnimated (ADR-007)', () async {
      await packRepo.insertPack(PackModel(
        identifier: 'pack_anim',
        name: 'Animated Pack',
        trayImagePath: 'media/tray.png',
        isAnimated: true,
      ));
      await packRepo.insertPack(PackModel(
        identifier: 'pack_static',
        name: 'Static Pack',
        trayImagePath: 'media/tray.png',
        isAnimated: false,
      ));

      final animPacks = await packRepo.getAllPacks(isAnimated: true);
      final staticPacks = await packRepo.getAllPacks(isAnimated: false);

      expect(animPacks.length, equals(1));
      expect(animPacks.first.isAnimated, isTrue);
      expect(staticPacks.length, equals(1));
      expect(staticPacks.first.isAnimated, isFalse);
    });

    test('deletePack cascades to pack_items (ON DELETE CASCADE)', () async {
      final pack = await packRepo.insertPack(PackModel(
        identifier: 'cascade_pack',
        name: 'Cascade Test',
        trayImagePath: 'media/tray.png',
      ));
      final sticker = await stickerRepo.insertSticker(buildTestSticker());
      await packRepo.addStickerToPack(PackItemModel(
        packId: pack.id!,
        stickerId: sticker.id!,
      ));

      // Verify item exists before deletion
      final before = await packRepo.getPackItems(pack.id!);
      expect(before.length, equals(1));

      // Delete pack
      await packRepo.deletePack(pack.id!);

      // pack_items must be gone due to ON DELETE CASCADE
      final after = await packRepo.getPackItems(pack.id!);
      expect(after.length, equals(0));
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 5: SHA-256 Storage Manager
  // ─────────────────────────────────────────────
  group('SHA-256 Storage Manager (ADR-005 Gate 2)', () {
    late Sha256StorageManager storageManager;

    setUp(() {
      storageManager = Sha256StorageManager(baseDir: tempDir);
    });

    test('saveMediaBytes creates content-addressed file at media/<sha256>.awebp',
        () async {
      final fakeBytes = List<int>.generate(1024, (i) => i % 256);
      final result = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'awebp',
      );

      expect(result.isExistingFile, isFalse);
      expect(result.fileSize, equals(1024));
      expect(result.sha256, hasLength(64)); // SHA-256 hex = 64 chars
      expect(result.relativePath, startsWith('media/'));
      expect(result.relativePath, endsWith('.awebp'));

      // Actual file must exist on disk
      final file = File(result.absolutePath);
      expect(await file.exists(), isTrue);
    });

    test('saveMediaBytes returns isExistingFile=true for duplicate binary content',
        () async {
      final fakeBytes = List<int>.generate(512, (i) => i * 2);

      // First save
      final first = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'webp',
      );
      expect(first.isExistingFile, isFalse);

      // Second save — same bytes
      final second = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'webp',
      );
      expect(second.isExistingFile, isTrue);
      expect(second.sha256, equals(first.sha256));
      expect(second.relativePath, equals(first.relativePath));
    });

    test('verifyMediaIntegrity passes for valid file', () async {
      final fakeBytes = List<int>.generate(256, (i) => i);
      final result = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'webp',
      );

      final isValid = await storageManager.verifyMediaIntegrity(
        relativePath: result.relativePath,
        expectedSha256: result.sha256,
        expectedSize: result.fileSize,
      );

      expect(isValid, isTrue);
    });

    test('verifyMediaIntegrity fails for missing file', () async {
      final isValid = await storageManager.verifyMediaIntegrity(
        relativePath: 'media/nonexistent_sha256.webp',
        expectedSha256:
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        expectedSize: 1024,
      );
      expect(isValid, isFalse);
    });

    test('verifyMediaIntegrity fails for tampered file (wrong hash)', () async {
      final fakeBytes = List<int>.generate(256, (i) => i);
      final result = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'webp',
      );

      // Overwrite file with different content
      final file = File(result.absolutePath);
      await file.writeAsString('tampered content');

      final isValid = await storageManager.verifyMediaIntegrity(
        relativePath: result.relativePath,
        expectedSha256: result.sha256,
        expectedSize: result.fileSize,
      );
      expect(isValid, isFalse);
    });

    test('computeSha256 is deterministic for same input', () {
      final bytes = [1, 2, 3, 4, 5, 6, 7, 8];
      final hash1 = Sha256StorageManager.computeSha256(bytes);
      final hash2 = Sha256StorageManager.computeSha256(bytes);
      expect(hash1, equals(hash2));
      expect(hash1, hasLength(64));
    });

    test('computeSha256 produces different hashes for different inputs', () {
      final hash1 = Sha256StorageManager.computeSha256([1, 2, 3]);
      final hash2 = Sha256StorageManager.computeSha256([4, 5, 6]);
      expect(hash1, isNot(equals(hash2)));
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 6: Library Integrity Scanner
  // ─────────────────────────────────────────────
  group('Library Integrity Scanner (06-persistent-storage.md §5.2)', () {
    late Sha256StorageManager storageManager;

    setUp(() {
      storageManager = Sha256StorageManager(baseDir: tempDir);
    });

    test('verifyLibraryIntegrity reports healthy for all valid files', () async {
      final fakeBytes = List<int>.generate(512, (i) => i);
      final result = await storageManager.saveMediaBytes(
        bytes: fakeBytes,
        extension: 'awebp',
      );

      final sticker = await stickerRepo.insertSticker(StickerModel(
        sourceVideoId: 'vid_001',
        sourceCommentId: 'cmt_integrity_ok',
        sourceAuthor: '@author',
        originalMediaUrl: 'https://cdn.example.com/sticker.awebp',
        localMediaPath: result.relativePath,
        mediaType: 'image/awebp',
        isAnimated: true,
        width: 300,
        height: 300,
        fileSize: result.fileSize,
        sha256: result.sha256,
      ));
      expect(sticker.id, isNotNull);

      final report =
          await stickerRepo.verifyLibraryIntegrity(storageManager);
      expect(report.isHealthy, isTrue);
      expect(report.totalCount, equals(1));
      expect(report.validCount, equals(1));
    });

    test('verifyLibraryIntegrity flags missing file', () async {
      await stickerRepo.insertSticker(StickerModel(
        sourceVideoId: 'vid_002',
        sourceCommentId: 'cmt_missing_file',
        sourceAuthor: '@author',
        originalMediaUrl: 'https://cdn.example.com/missing.awebp',
        localMediaPath: 'media/file_does_not_exist.awebp',
        mediaType: 'image/awebp',
        isAnimated: true,
        width: 300,
        height: 300,
        fileSize: 1024,
        sha256:
            'nonexistent_hash_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      ));

      final report =
          await stickerRepo.verifyLibraryIntegrity(storageManager);
      expect(report.isHealthy, isFalse);
      expect(report.missingFileStickerIds.length, equals(1));
    });
  });
}
