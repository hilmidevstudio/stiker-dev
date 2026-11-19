import 'package:test/test.dart';
import 'package:client/features/collection/models/sticker_model.dart';
import 'package:client/features/collection/models/pack_model.dart';
import 'package:client/features/collection/models/pack_item_model.dart';
import 'package:client/core/constants/db_constants.dart';

void main() {
  group('StickerModel Serialization', () {
    test('toMap includes all required fields', () {
      final sticker = StickerModel(
        sourceVideoId: 'vid_001',
        sourceCommentId: 'cmt_001',
        sourceAuthor: '@author',
        originalMediaUrl: 'https://cdn.tiktok.com/sticker.awebp',
        localMediaPath: 'media/abc123.awebp',
        mediaType: 'image/awebp',
        isAnimated: true,
        width: 300,
        height: 300,
        fileSize: 128000,
        sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      );

      final map = sticker.toMap(includeId: false);

      expect(map[DbConstants.colStickerSourceCommentId], equals('cmt_001'));
      expect(map[DbConstants.colStickerIsAnimated], equals(1));
      expect(map[DbConstants.colStickerExportStatus],
          equals(DbConstants.exportStatusPending));
      expect(map.containsKey(DbConstants.colStickerId), isFalse);
    });

    test('fromMap correctly parses integer boolean fields', () {
      final now = DateTime.now().toUtc().toIso8601String();
      final map = {
        DbConstants.colStickerId: 42,
        DbConstants.colStickerInternalId: 'uuid-test',
        DbConstants.colStickerSourcePlatform: 'tiktok',
        DbConstants.colStickerSourceVideoId: 'vid',
        DbConstants.colStickerSourceCommentId: 'cmt',
        DbConstants.colStickerSourceAuthor: '@test',
        DbConstants.colStickerThirdPartyId: null,
        DbConstants.colStickerOriginalMediaUrl: 'https://cdn.example.com/s.awebp',
        DbConstants.colStickerLocalMediaPath: 'media/abc.awebp',
        DbConstants.colStickerMediaType: 'image/awebp',
        DbConstants.colStickerIsAnimated: 1,
        DbConstants.colStickerWidth: 300,
        DbConstants.colStickerHeight: 300,
        DbConstants.colStickerFileSize: 50000,
        DbConstants.colStickerFrameCount: 10,
        DbConstants.colStickerDurationMs: 2000,
        DbConstants.colStickerSha256:
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        DbConstants.colStickerExportStatus: DbConstants.exportStatusPending,
        DbConstants.colStickerCreatedAt: now,
        DbConstants.colStickerUpdatedAt: now,
      };

      final sticker = StickerModel.fromMap(map);
      expect(sticker.id, equals(42));
      expect(sticker.isAnimated, isTrue);
      expect(sticker.frameCount, equals(10));
      expect(sticker.durationMs, equals(2000));
    });

    test('internalId is auto-generated UUID if not provided', () {
      final s1 = StickerModel(
        sourceVideoId: 'vid',
        sourceCommentId: 'cmt1',
        sourceAuthor: '@a',
        originalMediaUrl: 'https://url.com',
        localMediaPath: 'media/x.awebp',
        mediaType: 'image/awebp',
        isAnimated: false,
        width: 512,
        height: 512,
        fileSize: 1024,
        sha256: 'sha_1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      );
      final s2 = StickerModel(
        sourceVideoId: 'vid',
        sourceCommentId: 'cmt2',
        sourceAuthor: '@a',
        originalMediaUrl: 'https://url.com',
        localMediaPath: 'media/y.awebp',
        mediaType: 'image/awebp',
        isAnimated: false,
        width: 512,
        height: 512,
        fileSize: 1024,
        sha256: 'sha_2_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      );
      expect(s1.internalId, isNot(equals(s2.internalId)));
      expect(s1.internalId.length, equals(36)); // UUID v4 format
    });
  });

  group('PackModel Serialization', () {
    test('toMap includes all required fields', () {
      final pack = PackModel(
        identifier: 'pack_anim_001',
        name: 'StickerDrop Animated 1',
        trayImagePath: 'media/tray.png',
        isAnimated: true,
        stickerCount: 5,
      );

      final map = pack.toMap(includeId: false);
      expect(map[DbConstants.colPackIdentifier], equals('pack_anim_001'));
      expect(map[DbConstants.colPackIsAnimated], equals(1));
      expect(map[DbConstants.colPackStickerCount], equals(5));
      expect(map.containsKey(DbConstants.colPackId), isFalse);
    });

    test('fromMap correctly restores all fields', () {
      final now = DateTime.now().toUtc().toIso8601String();
      final map = {
        DbConstants.colPackId: 7,
        DbConstants.colPackIdentifier: 'test_pack',
        DbConstants.colPackName: 'Test Pack',
        DbConstants.colPackPublisher: 'StickerDrop User',
        DbConstants.colPackTrayImagePath: 'media/tray.png',
        DbConstants.colPackIsAnimated: 0,
        DbConstants.colPackStickerCount: 15,
        DbConstants.colPackCreatedAt: now,
        DbConstants.colPackUpdatedAt: now,
      };

      final pack = PackModel.fromMap(map);
      expect(pack.id, equals(7));
      expect(pack.isAnimated, isFalse);
      expect(pack.stickerCount, equals(15));
    });
  });

  group('PackItemModel Serialization', () {
    test('emojis JSON round-trip encoding/decoding is lossless', () {
      final item = PackItemModel(
        packId: 1,
        stickerId: 2,
        sortOrder: 0,
        emojis: ['🔥', '🗿', '😂'],
      );

      final map = item.toMap(includeId: false);
      final restored = PackItemModel.fromMap({
        ...map,
        DbConstants.colPackItemId: null,
      });

      expect(restored.emojis, equals(['🔥', '🗿', '😂']));
    });

    test('default emojis value is 🔥 when none provided', () {
      final item = PackItemModel(packId: 1, stickerId: 1);
      expect(item.emojis, equals(['🔥']));
    });
  });
}
