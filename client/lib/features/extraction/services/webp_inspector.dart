import 'dart:typed_data';

/// Facts derived from the downloaded WebP bytes, not from a provider's filename
/// or sticker_type field. These values are authoritative for local storage.
class WebPInspection {
  final bool isAnimated;
  final bool hasAlpha;
  final int width;
  final int height;
  final int frameCount;
  final int durationMs;
  final int fileSize;
  final String extension;
  final String mimeType;

  const WebPInspection({
    required this.isAnimated,
    required this.hasAlpha,
    required this.width,
    required this.height,
    required this.frameCount,
    required this.durationMs,
    required this.fileSize,
    required this.extension,
    required this.mimeType,
  });
}

/// Minimal strict RIFF/WebP container inspector.
/// It validates chunk boundaries and derives animation from VP8X/ANIM/ANMF.
class WebPInspector {
  static int _u32(Uint8List data, int offset) =>
      data[offset] |
      (data[offset + 1] << 8) |
      (data[offset + 2] << 16) |
      (data[offset + 3] << 24);

  static int _u24(Uint8List data, int offset) =>
      data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16);

  static int _u16(Uint8List data, int offset) =>
      data[offset] | (data[offset + 1] << 8);

  static String _fourCc(Uint8List data, int offset) =>
      String.fromCharCodes(data.sublist(offset, offset + 4));

  static WebPInspection inspect(Uint8List bytes) {
    if (bytes.length < 20 ||
        _fourCc(bytes, 0) != 'RIFF' ||
        _fourCc(bytes, 8) != 'WEBP') {
      throw const FormatException('Downloaded file is not a valid RIFF/WebP container.');
    }

    final riffEnd = _u32(bytes, 4) + 8;
    if (riffEnd != bytes.length || riffEnd < 20) {
      throw const FormatException('WebP RIFF size does not match the downloaded file length.');
    }

    var offset = 12;
    var hasVp8x = false;
    var animationFlag = false;
    var hasAnimChunk = false;
    var hasAlpha = false;
    var frameCount = 0;
    var durationMs = 0;
    var width = 0;
    var height = 0;
    var hasImagePayload = false;

    while (offset < riffEnd) {
      if (riffEnd - offset < 8) {
        throw const FormatException('Truncated WebP chunk header.');
      }

      final chunk = _fourCc(bytes, offset);
      final chunkSize = _u32(bytes, offset + 4);
      final payloadStart = offset + 8;
      final payloadEnd = payloadStart + chunkSize;
      final paddedEnd = payloadEnd + (chunkSize.isOdd ? 1 : 0);

      if (payloadEnd > riffEnd || paddedEnd > riffEnd) {
        throw FormatException('WebP chunk $chunk exceeds the RIFF container boundary.');
      }

      switch (chunk) {
        case 'VP8X':
          if (chunkSize != 10) {
            throw const FormatException('Invalid VP8X chunk length.');
          }
          hasVp8x = true;
          final flags = bytes[payloadStart];
          animationFlag = (flags & 0x02) != 0;
          hasAlpha = (flags & 0x10) != 0;
          width = _u24(bytes, payloadStart + 4) + 1;
          height = _u24(bytes, payloadStart + 7) + 1;
          break;
        case 'ALPH':
          hasAlpha = true;
          break;
        case 'ANIM':
          if (chunkSize != 6) {
            throw const FormatException('Invalid ANIM chunk length.');
          }
          hasAnimChunk = true;
          break;
        case 'ANMF':
          if (chunkSize < 16) {
            throw const FormatException('Invalid ANMF frame header.');
          }
          frameCount++;
          durationMs += _u24(bytes, payloadStart + 12);
          hasImagePayload = true;
          break;
        case 'VP8 ':
          hasImagePayload = true;
          if (width == 0 && chunkSize >= 10 &&
              bytes[payloadStart + 3] == 0x9d &&
              bytes[payloadStart + 4] == 0x01 &&
              bytes[payloadStart + 5] == 0x2a) {
            width = _u16(bytes, payloadStart + 6) & 0x3fff;
            height = _u16(bytes, payloadStart + 8) & 0x3fff;
          }
          break;
        case 'VP8L':
          hasImagePayload = true;
          if (width == 0 && chunkSize >= 5 && bytes[payloadStart] == 0x2f) {
            final b1 = bytes[payloadStart + 1];
            final b2 = bytes[payloadStart + 2];
            final b3 = bytes[payloadStart + 3];
            final b4 = bytes[payloadStart + 4];
            width = 1 + (b1 | ((b2 & 0x3f) << 8));
            height = 1 + ((b2 >> 6) | (b3 << 2) | ((b4 & 0x0f) << 10));
          }
          break;
      }

      offset = paddedEnd;
    }

    if (offset != riffEnd || !hasImagePayload) {
      throw const FormatException('WebP container is incomplete or has no image payload.');
    }

    final hasFrameChunks = frameCount > 0;
    final isAnimated = hasVp8x && animationFlag && hasAnimChunk && hasFrameChunks;
    if (animationFlag != hasAnimChunk || animationFlag != hasFrameChunks) {
      throw const FormatException('WebP animation flag and animation chunks are inconsistent.');
    }

    if (width <= 0 || height <= 0) {
      throw const FormatException('Could not determine WebP dimensions.');
    }

    final normalizedFrames = isAnimated ? frameCount : 1;
    final normalizedDuration = isAnimated ? durationMs : 0;
    return WebPInspection(
      isAnimated: isAnimated,
      hasAlpha: hasAlpha,
      width: width,
      height: height,
      frameCount: normalizedFrames,
      durationMs: normalizedDuration,
      fileSize: bytes.length,
      extension: isAnimated ? 'awebp' : 'webp',
      mimeType: isAnimated ? 'image/awebp' : 'image/webp',
    );
  }
}
