import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:test/test.dart';

import 'package:client/core/database/database_helper.dart';
import 'package:client/core/network/api_client.dart';
import 'package:client/features/extraction/services/extraction_service.dart';
import 'package:client/features/extraction/services/webp_inspector.dart';
import 'package:client/features/collection/models/sticker_model.dart';
import 'package:client/features/collection/repositories/sticker_repository.dart';
import 'package:client/features/collection/repositories/pack_repository.dart';
import 'package:client/features/collection/storage/sha256_storage_manager.dart';
import 'package:client/features/collection/services/virtual_pack_partitioner.dart';
import 'package:client/features/whatsapp_export/whatsapp_content_provider.dart';

void main() {
  sqfliteFfiInit();
  final factory = databaseFactoryFfi;

  late DatabaseHelper dbHelper;
  late StickerRepository stickerRepo;
  late PackRepository packRepo;
  late Directory tempBaseDir;
  late Sha256StorageManager storageManager;

  setUp(() async {
    tempBaseDir = await Directory.systemTemp.createTemp('e2e_stickerdrop_');
    dbHelper = DatabaseHelper.forTesting(
      factory: factory,
      databasePath: inMemoryDatabasePath,
    );
    stickerRepo = StickerRepository(dbHelper: dbHelper);
    packRepo = PackRepository(dbHelper: dbHelper);
    storageManager = Sha256StorageManager(baseDir: tempBaseDir);
    await storageManager.initialize();
  });

  tearDown(() async {
    await dbHelper.close();
    await dbHelper.reset();
    if (await tempBaseDir.exists()) {
      await tempBaseDir.delete(recursive: true);
    }
  });

  test('E2E Flow: Extraction -> Storage -> SQLite Repo -> Pack Partition -> WA Export',
      () async {
    // -------------------------------------------------------------
    // Step 1: Mock Backend Proxy & Extraction Service
    // -------------------------------------------------------------
    final mockExtractionPayload = {
      'success': true,
      'message': 'Sticker extracted successfully',
      'video_id': '7708356144804236564',
      'comment_id': '7708394712596972308',
      'canonical_url': 'https://www.tiktok.com/@nyariprompt/video/7708356144804236564',
      'comment_text': 'ngajak ribut kamu? 🗿',
      'create_time': 1731600000,
      'digg_count': 88,
      'author': {
        'uid': '7435664412436120631',
        'unique_id': 'crazyolshop1',
        'nickname': 'crazyolshop1',
        'avatar_url': 'https://p16-sign-va.tiktokcdn.com/avatar.webp',
      },
      'sticker': {
        'sticker_id': '7421890123456789012',
        'sticker_type': 2,
        'is_animated': true,
        'format': 'awebp',
        'media_url': 'https://cdn.tiktok.com/prabowo_animated.awebp',
        'width': 300,
        'height': 300,
      },
      'provider_used': 'MockProvider',
    };

    // Real two-frame animated WebP fixtures. The media validator correctly
    // rejects arbitrary/random bytes, so the E2E test must serve valid WebP.
    final animatedWebpFixtures = <List<int>>[
      base64Decode(
        'UklGRoQAAABXRUJQVlA4WAoAAAACAAAADwAADwAAQU5JTQYAAAAAAAAAAABBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAAJWUDhMDwAAAC8PwAMABxD9j/4HIqL/AQBBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAABWUDhMDwAAAC8PwAMABxDR//4HIqL/AQA=',
      ),
      base64Decode(
        'UklGRoQAAABXRUJQVlA4WAoAAAACAAAADwAADwAAQU5JTQYAAAAAAAAAAABBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAAJWUDhMDwAAAC8PwAMAB9D/iP4HIqL/AQBBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAABWUDhMEAAAAC8PwAMAB9D//kf/AxHR/wA=',
      ),
      base64Decode(
        'UklGRoQAAABXRUJQVlA4WAoAAAACAAAADwAADwAAQU5JTQYAAAAAAAAAAABBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAAJWUDhMEAAAAC8PwAMABxD973//AxHR/wBBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAABWUDhMEAAAAC8PwAMAB9D/6H//AxHR/wA=',
      ),
    ];
    final fakeBinaryBytes = animatedWebpFixtures.first;

    final mockHttpClient = MockClient((request) async {
      if (request.url.path.contains('resolve-and-extract')) {
        return http.Response(jsonEncode(mockExtractionPayload), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.toString().contains('prabowo_animated.awebp')) {
        return http.Response.bytes(fakeBinaryBytes, 200);
      }
      return http.Response('Not Found', 404);
    });

    final apiClient = ApiClient(httpClient: mockHttpClient, baseUrl: 'http://localhost:8000');
    final extractionService = ExtractionService(apiClient: apiClient, downloadClient: mockHttpClient);

    // Run extraction
    final extraction = await extractionService.extractFromUrl(rawInput: 'https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/');
    expect(extraction.success, isTrue);
    expect(extraction.commentId, equals('7708394712596972308'));
    expect(extraction.sticker.isAnimated, isTrue);

    // Download bytes
    final downloadedBytes = await extractionService.downloadMedia(extraction.sticker.mediaUrl);
    expect(downloadedBytes.length, greaterThan(12));
    expect(ascii.decode(downloadedBytes.sublist(0, 4)), equals('RIFF'));
    expect(ascii.decode(downloadedBytes.sublist(8, 12)), equals('WEBP'));
    final mediaInfo = WebPInspector.inspect(Uint8List.fromList(downloadedBytes));
    expect(mediaInfo.isAnimated, isTrue);
    expect(mediaInfo.frameCount, equals(2));

    // -------------------------------------------------------------
    // Step 2: Media Storage via SHA-256 Storage Manager
    // Classification and extension come from the binary, not API hints.
    // -------------------------------------------------------------
    final storageResult = await storageManager.saveMediaBytes(
      bytes: downloadedBytes,
      extension: mediaInfo.extension,
    );
    expect(storageResult.isExistingFile, isFalse);
    expect(storageResult.sha256, hasLength(64));
    expect(File(storageResult.absolutePath).existsSync(), isTrue);

    // -------------------------------------------------------------
    // Step 3: SQLite Repository Persistence & Deduplication
    // -------------------------------------------------------------
    final sticker1 = await stickerRepo.insertSticker(StickerModel(
      sourceVideoId: extraction.videoId,
      sourceCommentId: extraction.commentId,
      sourceAuthor: '@${extraction.author.uniqueId}',
      stickerId: extraction.sticker.stickerId,
      originalMediaUrl: extraction.sticker.mediaUrl,
      localMediaPath: storageResult.relativePath,
      mediaType: mediaInfo.mimeType,
      isAnimated: mediaInfo.isAnimated,
      width: mediaInfo.width,
      height: mediaInfo.height,
      fileSize: storageResult.fileSize,
      frameCount: mediaInfo.frameCount,
      durationMs: mediaInfo.durationMs,
      sha256: storageResult.sha256,
    ));

    expect(sticker1.id, isNotNull);

    // Deduplication check: Gate 1 (duplicate comment)
    final dupComment = await stickerRepo.insertSticker(sticker1);
    expect(dupComment.id, equals(sticker1.id)); // Same record returned

    // Add 2 more distinct stickers to fulfill WhatsApp min 3 stickers requirement
    for (int i = 2; i <= 3; i++) {
      final dummyBytes = animatedWebpFixtures[i - 1];
      final res = await storageManager.saveMediaBytes(bytes: dummyBytes, extension: 'awebp');
      await stickerRepo.insertSticker(StickerModel(
        sourceVideoId: 'video_$i',
        sourceCommentId: 'comment_$i',
        sourceAuthor: '@author_$i',
        originalMediaUrl: 'https://cdn.tiktok.com/sticker_$i.awebp',
        localMediaPath: res.relativePath,
        mediaType: 'image/awebp',
        isAnimated: true,
        width: 300,
        height: 300,
        fileSize: res.fileSize,
        sha256: res.sha256,
      ));
    }

    final totalStickers = await stickerRepo.getAllStickers();
    expect(totalStickers.length, equals(3));

    // -------------------------------------------------------------
    // Step 4: Virtual Pack Partitioning (ADR-006 & ADR-007)
    // -------------------------------------------------------------
    final partitioner = VirtualPackPartitioner(
      stickerRepository: stickerRepo,
      packRepository: packRepo,
    );
    final partitionResult = await partitioner.partitionAndSyncPacks();

    expect(partitionResult.readyPacks.length, equals(1));
    expect(partitionResult.incompletePacks.isEmpty, isTrue);

    final readyPack = partitionResult.readyPacks.first;
    expect(readyPack.identifier, equals('stickerdrop_pack_anim_001'));
    expect(readyPack.isAnimated, isTrue);
    expect(readyPack.stickerCount, equals(3));

    // -------------------------------------------------------------
    // Step 5: WhatsApp Physical Pack Export & contents.json Generation
    // -------------------------------------------------------------
    final contentProvider = WhatsAppContentProvider(
      packRepository: packRepo,
      stickerRepository: stickerRepo,
    );

    final exportedPackPath = await contentProvider.exportPackDirectory(
      pack: readyPack,
      baseDir: tempBaseDir,
      storageManager: storageManager,
    );

    expect(Directory(exportedPackPath).existsSync(), isTrue);

    // Verify tray icon created
    final trayFile = File(p.join(exportedPackPath, 'tray_icon.png'));
    expect(trayFile.existsSync(), isTrue);
    expect(trayFile.lengthSync(), greaterThan(0));

    // Verify sticker files copied
    final packStickerFiles = Directory(exportedPackPath)
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.awebp'))
        .toList();
    expect(packStickerFiles.length, equals(3));

    // Verify contents.json exists and is valid WhatsApp format
    final contentsJsonFile = File(p.join(tempBaseDir.path, 'whatsapp_packs', 'contents.json'));
    expect(contentsJsonFile.existsSync(), isTrue);

    final manifestJson = jsonDecode(contentsJsonFile.readAsStringSync());
    expect(manifestJson['android_play_store_link'], contains('com.stickerdrop.app'));
    expect(manifestJson['sticker_packs'], isList);
    expect(manifestJson['sticker_packs'].length, equals(1));

    final exportedPackJson = manifestJson['sticker_packs'][0];
    expect(exportedPackJson['identifier'], equals('stickerdrop_pack_anim_001'));
    expect(exportedPackJson['animated_sticker_pack'], isTrue);
    expect(exportedPackJson['stickers'].length, equals(3));
    expect(exportedPackJson['stickers'][0]['emojis'], contains('🔥'));
  });
}
