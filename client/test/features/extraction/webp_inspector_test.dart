import 'dart:convert';
import 'dart:typed_data';

import 'package:test/test.dart';
import 'package:client/features/extraction/services/webp_inspector.dart';

Uint8List _chunk(String name, List<int> payload) {
  final out = <int>[
    ...ascii.encode(name),
    payload.length & 0xff,
    (payload.length >> 8) & 0xff,
    (payload.length >> 16) & 0xff,
    (payload.length >> 24) & 0xff,
    ...payload,
  ];
  if (payload.length.isOdd) out.add(0);
  return Uint8List.fromList(out);
}

Uint8List _riff(List<Uint8List> chunks) {
  final body = <int>[...ascii.encode('WEBP')];
  for (final chunk in chunks) {
    body.addAll(chunk);
  }
  final size = body.length;
  return Uint8List.fromList([
    ...ascii.encode('RIFF'),
    size & 0xff,
    (size >> 8) & 0xff,
    (size >> 16) & 0xff,
    (size >> 24) & 0xff,
    ...body,
  ]);
}

void main() {
  group('WebPInspector', () {
    test('classifies a static extended WebP from binary flags and chunks', () {
      const width = 458;
      const height = 498;
      final vp8x = <int>[
        0x10, 0, 0, 0,
        (width - 1) & 0xff,
        ((width - 1) >> 8) & 0xff,
        ((width - 1) >> 16) & 0xff,
        (height - 1) & 0xff,
        ((height - 1) >> 8) & 0xff,
        ((height - 1) >> 16) & 0xff,
      ];
      final bytes = _riff([
        _chunk('VP8X', vp8x),
        _chunk('ALPH', [0, 0]),
        _chunk('VP8 ', List<int>.filled(10, 0)),
      ]);

      final info = WebPInspector.inspect(bytes);
      expect(info.isAnimated, isFalse);
      expect(info.frameCount, 1);
      expect(info.durationMs, 0);
      expect(info.width, width);
      expect(info.height, height);
      expect(info.hasAlpha, isTrue);
      expect(info.extension, 'webp');
      expect(info.mimeType, 'image/webp');
    });

    test('classifies animated WebP from ANIM and ANMF chunks', () {
      final animated = base64Decode(
        'UklGRoQAAABXRUJQVlA4WAoAAAACAAAADwAADwAAQU5JTQYAAAAAAAAAAABBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAAJWUDhMDwAAAC8PwAMABxD9j/4HIqL/AQBBTk1GKAAAAAAAAAAAAA8AAA8AAHgAAABWUDhMDwAAAC8PwAMABxDR//4HIqL/AQA=',
      );
      final info = WebPInspector.inspect(Uint8List.fromList(animated));
      expect(info.isAnimated, isTrue);
      expect(info.frameCount, 2);
      expect(info.durationMs, 240);
      expect(info.extension, 'awebp');
    });

    test('rejects inconsistent RIFF size', () {
      final bytes = _riff([
        _chunk('VP8 ', List<int>.filled(10, 0)),
      ]);
      bytes[4] = bytes[4] + 1;
      expect(() => WebPInspector.inspect(bytes), throwsA(isA<FormatException>()));
    });

    test('rejects animation flag without animation chunks', () {
      final vp8x = <int>[0x02, 0, 0, 0, 15, 0, 0, 15, 0, 0];
      final bytes = _riff([
        _chunk('VP8X', vp8x),
        _chunk('VP8 ', List<int>.filled(10, 0)),
      ]);
      expect(() => WebPInspector.inspect(bytes), throwsA(isA<FormatException>()));
    });
  });
}
