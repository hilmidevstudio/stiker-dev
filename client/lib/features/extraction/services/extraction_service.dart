import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/extraction_response.dart';
import 'webp_inspector.dart';

/// Service managing extraction operations via Backend Proxy
class ExtractionService {
  final ApiClient _apiClient;
  final http.Client _downloadClient;

  ExtractionService({
    ApiClient? apiClient,
    http.Client? downloadClient,
  })  : _apiClient = apiClient ?? ApiClient(),
        _downloadClient = downloadClient ?? http.Client();

  /// Extract sticker details from a TikTok comment URL
  Future<ExtractionResponse> extractFromUrl({
    required String rawInput,
  }) async {
    final cleaned = rawInput.trim();
    if (cleaned.isEmpty) {
      throw const InvalidUrlException('Input URL cannot be empty');
    }

    if (!cleaned.contains('http://') && !cleaned.contains('https://')) {
      throw const InvalidUrlException(
          'Input must be a valid HTTP or HTTPS URL');
    }

    final json = await _apiClient.resolveAndExtract(url: cleaned);

    return ExtractionResponse.fromJson(json);
  }

  /// Download and validate the actual sticker asset returned by the extraction provider.
  /// A failed CDN request is an error; never replace the user's sticker with demo media.
  Future<Uint8List> downloadMedia(String mediaUrl) async {
    try {
      final uri = Uri.parse(mediaUrl);
      if (uri.scheme != 'https' || uri.host.isEmpty) {
        throw const ApiException(
          'The provider returned an invalid media URL.',
          errorCode: 'INVALID_MEDIA_URL',
          statusCode: 400,
        );
      }

      // Keep the signed TikTok CDN URL in a POST body, not in the request path.
      // The backend applies a CDN allowlist, redirect limit, byte cap, and WebP check.
      final proxyUri = Uri.parse(_apiClient.baseUrl).resolve('/v1/media-proxy');
      final response = await _downloadClient
          .post(
            proxyUri,
            headers: const {
              'Content-Type': 'application/json',
              'Accept': 'image/webp, application/octet-stream',
            },
            body: jsonEncode({'url': mediaUrl}),
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode != 200) {
        var message = 'Media proxy failed: HTTP ${response.statusCode}';
        var errorCode = 'MEDIA_PROXY_FAILED';
        try {
          final payload = jsonDecode(utf8.decode(response.bodyBytes));
          if (payload is Map<String, dynamic>) {
            message = payload['message'] as String? ?? message;
            errorCode = payload['error_code'] as String? ?? errorCode;
          }
        } catch (_) {
          // Keep the safe generic error when the backend did not return JSON.
        }
        throw ApiException(
          message,
          errorCode: errorCode,
          statusCode: response.statusCode,
        );
      }

      final bytes = response.bodyBytes;
      try {
        // The provider's sticker_type, URL suffix, and MIME hint are not
        // authoritative. Inspect the actual RIFF/WebP bytes before saving.
        WebPInspector.inspect(bytes);
      } on FormatException catch (e) {
        throw ApiException(
          'Downloaded media is not a structurally valid WebP sticker: ${e.message}',
          errorCode: 'INVALID_MEDIA_FILE',
          statusCode: 502,
        );
      }
      return bytes;
    } on ApiException {
      rethrow;
    } catch (e) {
      throw NetworkConnectionException('Failed to download sticker media: $e');
    }
  }

  void dispose() {
    _apiClient.close();
    _downloadClient.close();
  }
}
