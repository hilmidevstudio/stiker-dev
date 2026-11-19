import 'dart:convert';
import 'package:test/test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:client/core/network/api_client.dart';
import 'package:client/core/network/api_exceptions.dart';
import 'package:client/features/extraction/models/extraction_response.dart';

/// Builds a MockClient that returns a preset response
MockClient buildMockClient(Map<String, dynamic> body, {int statusCode = 200}) {
  return MockClient((_) async => http.Response(
        jsonEncode(body),
        statusCode,
        headers: {'content-type': 'application/json'},
      ));
}

/// Full mock success payload matching docs/12-backend-implementation-report.md §5.2
Map<String, dynamic> get mockSuccessPayload => {
      'success': true,
      'message': 'Sticker extracted successfully',
      'video_id': '7708356144804236564',
      'comment_id': '7708394712596972308',
      'canonical_url':
          'https://www.tiktok.com/@nyariprompt/video/7708356144804236564',
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
        'media_url':
            'https://p16-sign-useastdict.tiktokcdn.com/prabowo_animated.awebp',
        'static_url':
            'https://p16-sign-useastdict.tiktokcdn.com/prabowo_static.webp',
        'animated_url':
            'https://p16-sign-useastdict.tiktokcdn.com/prabowo_animated.awebp',
        'width': 300,
        'height': 300,
      },
      'provider_used': 'MockProvider',
      'sha256': null,
    };

void main() {
  group('ApiClient HTTP Layer', () {
    test('GET /health returns ok status body', () async {
      final client = buildMockClient({'status': 'ok', 'service': 'StickerDrop Backend'});
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      final result = await apiClient.checkHealth();
      expect(result['status'], equals('ok'));
      expect(result['service'], equals('StickerDrop Backend'));
    });

    test('POST /v1/resolve-and-extract returns success response', () async {
      final client = buildMockClient(mockSuccessPayload);
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      final result = await apiClient.resolveAndExtract(
        url: 'https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/',
        provider: 'mock',
      );

      expect(result['success'], isTrue);
      expect(result['comment_id'], equals('7708394712596972308'));
      expect(result['video_id'], equals('7708356144804236564'));
    });

    test('HTTP 400 INVALID_URL maps to InvalidUrlException', () async {
      final client = buildMockClient(
        {
          'success': false,
          'error_code': 'INVALID_URL',
          'message': 'The input is not a valid URL.',
          'details': {'path': '/v1/resolve-and-extract'},
        },
        statusCode: 400,
      );
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () async => await apiClient.resolveAndExtract(url: 'not-a-url'),
        throwsA(isA<InvalidUrlException>()),
      );
    });

    test('HTTP 404 COMMENT_NOT_FOUND maps to CommentNotFoundException',
        () async {
      final client = buildMockClient(
        {
          'success': false,
          'error_code': 'COMMENT_NOT_FOUND',
          'message': 'Comment was not found in this video.',
          'details': null,
        },
        statusCode: 404,
      );
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () async => await apiClient.resolveAndExtract(url: 'https://vt.tiktok.com/abc'),
        throwsA(isA<CommentNotFoundException>()),
      );
    });

    test('HTTP 404 STICKER_NOT_FOUND maps to StickerNotFoundException',
        () async {
      final client = buildMockClient(
        {
          'success': false,
          'error_code': 'STICKER_NOT_FOUND',
          'message': 'Comment found but has no sticker.',
          'details': null,
        },
        statusCode: 404,
      );
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () async => await apiClient.resolveAndExtract(url: 'https://vt.tiktok.com/abc'),
        throwsA(isA<StickerNotFoundException>()),
      );
    });

    test('HTTP 422 MISSING_COMMENT_ID maps to MissingCommentIdException',
        () async {
      final client = buildMockClient(
        {
          'success': false,
          'error_code': 'MISSING_COMMENT_ID',
          'message': 'Link points to a video, not a comment.',
          'details': null,
        },
        statusCode: 422,
      );
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () async => await apiClient.resolveAndExtract(url: 'https://vt.tiktok.com/abc'),
        throwsA(isA<MissingCommentIdException>()),
      );
    });

    test('HTTP 502 EXTRACTION_ERROR maps to ExtractionException', () async {
      final client = buildMockClient(
        {
          'success': false,
          'error_code': 'EXTRACTION_ERROR',
          'message': 'Upstream scraping service failed.',
          'details': null,
        },
        statusCode: 502,
      );
      final apiClient = ApiClient(
        httpClient: client,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () async => await apiClient.resolveAndExtract(url: 'https://vt.tiktok.com/abc'),
        throwsA(isA<ExtractionException>()),
      );
    });
  });

  // ─────────────────────────────────────────────
  // SECTION 2: ExtractionResponse Deserialization
  // ─────────────────────────────────────────────
  group('ExtractionResponse deserialization', () {
    test('fromJson parses all fields correctly from mock payload', () {
      final response = ExtractionResponse.fromJson(mockSuccessPayload);

      expect(response.success, isTrue);
      expect(response.videoId, equals('7708356144804236564'));
      expect(response.commentId, equals('7708394712596972308'));
      expect(response.author.uniqueId, equals('crazyolshop1'));
      expect(response.sticker.isAnimated, isTrue);
      expect(response.sticker.format, equals('awebp'));
      expect(response.sticker.width, equals(300));
      expect(response.sticker.height, equals(300));
      expect(response.providerUsed, equals('MockProvider'));
      expect(response.sha256, isNull);
    });

    test('fromJson handles missing optional fields gracefully', () {
      final minimalPayload = <String, dynamic>{
        'success': true,
        'message': 'ok',
        'video_id': '123',
        'comment_id': '456',
        'canonical_url': 'https://tiktok.com',
        'comment_text': '',
        'create_time': 0,
        'digg_count': 0,
        'author': <String, dynamic>{},
        'sticker': <String, dynamic>{},
        'provider_used': 'mock',
      };

      final response = ExtractionResponse.fromJson(minimalPayload);
      expect(response.videoId, equals('123'));
      expect(response.author.uid, equals(''));
      expect(response.sticker.format, equals('webp'));
      expect(response.sha256, isNull);
    });

    test('AuthorInfo.fromJson correctly maps all fields', () {
      final authorJson = mockSuccessPayload['author'] as Map<String, dynamic>;
      final author = AuthorInfo.fromJson(authorJson);

      expect(author.uid, equals('7435664412436120631'));
      expect(author.uniqueId, equals('crazyolshop1'));
      expect(author.nickname, equals('crazyolshop1'));
      expect(author.avatarUrl, startsWith('https://'));
    });

    test('StickerMetadata.fromJson correctly identifies animated awebp format',
        () {
      final stickerJson = mockSuccessPayload['sticker'] as Map<String, dynamic>;
      final sticker = StickerMetadata.fromJson(stickerJson);

      expect(sticker.isAnimated, isTrue);
      expect(sticker.stickerType, equals(2));
      expect(sticker.format, equals('awebp'));
      expect(sticker.animatedUrl, isNotNull);
      expect(sticker.staticUrl, isNotNull);
    });
  });
}
