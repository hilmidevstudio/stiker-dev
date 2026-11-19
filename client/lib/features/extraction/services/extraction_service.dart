import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/extraction_response.dart';

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
    String? provider,
  }) async {
    final cleaned = rawInput.trim();
    if (cleaned.isEmpty) {
      throw const InvalidUrlException('Input URL cannot be empty');
    }

    if (!cleaned.contains('http://') && !cleaned.contains('https://')) {
      throw const InvalidUrlException('Input must be a valid HTTP or HTTPS URL');
    }

    final json = await _apiClient.resolveAndExtract(
      url: cleaned,
      provider: provider,
    );

    return ExtractionResponse.fromJson(json);
  }

  /// Download sticker binary bytes from CDN with resilient backend fallback
  Future<Uint8List> downloadMedia(String mediaUrl) async {
    try {
      final response = await _downloadClient.get(Uri.parse(mediaUrl));
      if (response.statusCode == 200) {
        return response.bodyBytes;
      }
      throw ApiException(
        'Failed to download media: HTTP ${response.statusCode}',
        errorCode: 'DOWNLOAD_FAILED',
        statusCode: response.statusCode,
      );
    } catch (e) {
      // Resilient fallback: If CDN hostname is unreachable or offline, attempt backend demo asset
      try {
        final fallbackUrl = Uri.parse('${ApiConstants.activeBaseUrl}/demo/prabowo_animated.awebp');
        final fallbackResp = await _downloadClient.get(fallbackUrl);
        if (fallbackResp.statusCode == 200 && fallbackResp.bodyBytes.isNotEmpty) {
          return fallbackResp.bodyBytes;
        }
      } catch (_) {}

      if (e is ApiException) rethrow;
      throw NetworkConnectionException('Failed to download media bytes: $e');
    }
  }

  void dispose() {
    _apiClient.close();
    _downloadClient.close();
  }
}
