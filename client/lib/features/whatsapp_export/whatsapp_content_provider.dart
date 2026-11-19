import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:path/path.dart' as p;
import '../collection/models/pack_model.dart';
import '../collection/repositories/pack_repository.dart';
import '../collection/repositories/sticker_repository.dart';
import '../collection/storage/sha256_storage_manager.dart';

/// Builds WhatsApp-compatible contents.json metadata and exports physical pack assets
/// Implements 07-whatsapp-integration.md Section 3 & 4
class WhatsAppContentProvider {
  final PackRepository _packRepository;
  final StickerRepository _stickerRepository;

  WhatsAppContentProvider({
    PackRepository? packRepository,
    StickerRepository? stickerRepository,
  })  : _packRepository = packRepository ?? PackRepository(),
        _stickerRepository = stickerRepository ?? StickerRepository();

  /// Generate the full WhatsApp contents.json structure for all exportable packs
  Future<Map<String, dynamic>> buildContentsJson({
    String androidPlayStoreLink =
        'https://play.google.com/store/apps/details?id=com.stickerdrop.app',
    String iosAppStoreLink = '',
  }) async {
    final allPacks = await _packRepository.getAllPacks();
    final exportablePacks = allPacks
        .where((p) => p.stickerCount >= 3)
        .toList();

    final stickerPacksJson = <Map<String, dynamic>>[];
    for (final pack in exportablePacks) {
      final packJson = await _buildPackJson(pack);
      if (packJson != null) {
        stickerPacksJson.add(packJson);
      }
    }

    return {
      'android_play_store_link': androidPlayStoreLink,
      'ios_app_store_link': iosAppStoreLink,
      'sticker_packs': stickerPacksJson,
    };
  }

  Future<Map<String, dynamic>?> _buildPackJson(PackModel pack) async {
    final items = await _packRepository.getPackItems(pack.id!);
    if (items.length < 3) return null;

    final stickersJson = <Map<String, dynamic>>[];
    for (final item in items) {
      final sticker = await _stickerRepository.getStickerById(item.stickerId);
      if (sticker == null) continue;
      final ext = sticker.isAnimated ? 'awebp' : 'webp';
      final fileName = '${sticker.sha256}.$ext';

      stickersJson.add({
        'image_file': fileName,
        'emojis': item.emojis,
      });
    }

    if (stickersJson.length < 3) return null;

    return {
      'identifier': pack.identifier,
      'name': pack.name,
      'publisher': pack.publisher,
      'tray_image_file': 'tray_icon.png',
      'publisher_email': 'support@stickerdrop.app',
      'publisher_website': 'https://stickerdrop.app',
      'privacy_policy_website': 'https://stickerdrop.app/privacy',
      'license_agreement_website': 'https://stickerdrop.app/terms',
      'animated_sticker_pack': pack.isAnimated,
      'stickers': stickersJson,
    };
  }

  /// Prepare physical export folder and contents.json file for WhatsApp ContentProvider
  Future<String> exportPackDirectory({
    required PackModel pack,
    required Directory baseDir,
    required Sha256StorageManager storageManager,
  }) async {
    final exportRoot = Directory(p.join(baseDir.path, 'whatsapp_packs'));
    final packDir = Directory(p.join(exportRoot.path, pack.identifier));
    if (!await packDir.exists()) {
      await packDir.create(recursive: true);
    }

    // 1. Write tray_icon.png (96x96)
    final trayFile = File(p.join(packDir.path, 'tray_icon.png'));
    if (!await trayFile.exists()) {
      await trayFile.writeAsBytes(generateSyntheticTrayIconPng(96, 96), flush: true);
    }

    // 2. Copy/Link stickers into the pack folder
    final items = await _packRepository.getPackItems(pack.id!);
    for (final item in items) {
      final sticker = await _stickerRepository.getStickerById(item.stickerId);
      if (sticker == null) continue;

      final ext = sticker.isAnimated ? 'awebp' : 'webp';
      final fileName = '${sticker.sha256}.$ext';
      final destFile = File(p.join(packDir.path, fileName));

      final srcFile = storageManager.getFileForRelativePath(sticker.localMediaPath);
      if (!await srcFile.exists() || await srcFile.length() == 0) {
        throw StateError('Sticker source file is missing or empty: ${sticker.id}');
      }

      if (!await destFile.exists() || await destFile.length() == 0) {
        if (await destFile.exists()) await destFile.delete();
        await srcFile.copy(destFile.path);
      }
      if (!await destFile.exists() || await destFile.length() == 0) {
        throw StateError('Failed to prepare sticker file for WhatsApp: ${sticker.id}');
      }
    }

    // 3. Write contents.json in whatsapp_packs/
    final manifestData = await buildContentsJson();
    final manifestFile = File(p.join(exportRoot.path, 'contents.json'));
    await manifestFile.writeAsString(
      const JsonEncoder.withIndent('  ').convert(manifestData),
      flush: true,
    );

    return packDir.path;
  }

  /// Synthesizes a valid 96x96 PNG for WhatsApp Tray Icon
  static List<int> generateSyntheticTrayIconPng(int width, int height) {
    final builder = BytesBuilder();
    builder.add([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]); // PNG header

    // IHDR Chunk
    final ihdrData = ByteData(13)
      ..setUint32(0, width, Endian.big)
      ..setUint32(4, height, Endian.big)
      ..setUint8(8, 8)  // Bit depth
      ..setUint8(9, 6)  // Color type RGBA
      ..setUint8(10, 0) // Compression
      ..setUint8(11, 0) // Filter
      ..setUint8(12, 0); // Interlace
    _writeChunk(builder, 'IHDR', ihdrData.buffer.asUint8List());

    // IDAT Chunk with raw pixel scanlines
    final rawScanlines = BytesBuilder();
    for (int y = 0; y < height; y++) {
      rawScanlines.addByte(0); // Filter byte: None
      for (int x = 0; x < width; x++) {
        if (x >= 8 && x < 88 && y >= 8 && y < 88) {
          rawScanlines.add([30, 144, 255, 220]); // DodgerBlue with opacity
        } else {
          rawScanlines.add([0, 0, 0, 0]); // Transparent
        }
      }
    }

    final compressed = zlib.encode(rawScanlines.toBytes());
    _writeChunk(builder, 'IDAT', Uint8List.fromList(compressed));

    // IEND Chunk
    _writeChunk(builder, 'IEND', Uint8List(0));

    return builder.toBytes();
  }

  static void _writeChunk(BytesBuilder builder, String type, Uint8List data) {
    final lenBytes = ByteData(4)..setUint32(0, data.length, Endian.big);
    builder.add(lenBytes.buffer.asUint8List());

    final typeBytes = ascii.encode(type);
    builder.add(typeBytes);
    builder.add(data);

    // CRC32 calculation
    final crcData = Uint8List(typeBytes.length + data.length);
    crcData.setRange(0, typeBytes.length, typeBytes);
    crcData.setRange(typeBytes.length, crcData.length, data);
    final crc = _crc32(crcData);

    final crcBytes = ByteData(4)..setUint32(0, crc, Endian.big);
    builder.add(crcBytes.buffer.asUint8List());
  }

  static int _crc32(List<int> bytes) {
    var crc = 0xFFFFFFFF;
    for (final b in bytes) {
      crc ^= b;
      for (var i = 0; i < 8; i++) {
        if ((crc & 1) != 0) {
          crc = (crc >>> 1) ^ 0xEDB88320;
        } else {
          crc = crc >>> 1;
        }
      }
    }
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF;
  }

  /// Render contents.json as a JSON string
  Future<String> buildContentsJsonString() async {
    final json = await buildContentsJson();
    return const JsonEncoder.withIndent('  ').convert(json);
  }
}
