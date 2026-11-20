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
      throw const InvalidUrlException('Input must be a valid HTTP or HTTPS URL');
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

      final response = await _downloadClient.get(uri);
      if (response.statusCode != 200) {
        throw ApiException(
          'Failed to download media: HTTP ${response.statusCode}',
          errorCode: 'DOWNLOAD_FAILED',
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
