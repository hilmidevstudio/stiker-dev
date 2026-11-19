import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../constants/api_constants.dart';
import 'api_exceptions.dart';

/// Core HTTP Client communicating with the Backend Proxy Microservice
class ApiClient {
  final http.Client _httpClient;
  final String _baseUrl;

  ApiClient({
    http.Client? httpClient,
    String? baseUrl,
  })  : _httpClient = httpClient ?? http.Client(),
        _baseUrl = baseUrl ?? ApiConstants.activeBaseUrl;

  String get baseUrl => _baseUrl;

  /// Check backend service health and connectivity
  Future<Map<String, dynamic>> checkHealth() async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.healthEndpoint}');
    try {
      final response = await _httpClient
          .get(uri, headers: ApiConstants.jsonHeaders)
          .timeout(ApiConstants.connectTimeout);

      return _handleResponse(response);
    } on SocketException catch (e) {
      throw NetworkConnectionException(
        'Cannot connect to backend server at $_baseUrl: ${e.message}',
      );
    } on TimeoutException {
      throw const NetworkConnectionException(
        'Backend connection timed out while checking health.',
      );
    }
  }

  /// Request link resolution and sticker extraction
  Future<Map<String, dynamic>> resolveAndExtract({
    required String url,
  }) async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.resolveAndExtractEndpoint}');
    final requestBody = jsonEncode({'url': url});

    try {
      final response = await _httpClient
          .post(
            uri,
            headers: ApiConstants.jsonHeaders,
            body: requestBody,
          )
          .timeout(ApiConstants.requestTimeout);

      return _handleResponse(response);
    } on SocketException catch (e) {
      throw NetworkConnectionException(
        'Network error connecting to backend: ${e.message}',
      );
    } on TimeoutException {
      throw const NetworkConnectionException(
        'Extraction request timed out after 30 seconds.',
      );
    }
  }

  /// Process HTTP response and map backend error taxonomy to domain exceptions
  Map<String, dynamic> _handleResponse(http.Response response) {
    Map<String, dynamic> body;
    try {
      body = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      if (response.statusCode >= 200 && response.statusCode < 300) {
        return {'raw': response.body};
      }
      throw ApiException(
        'Non-JSON server response (HTTP ${response.statusCode})',
        errorCode: 'INVALID_RESPONSE',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body;
    }

    // Map error taxonomy
    final errorCode = body['error_code'] as String? ?? 'UNKNOWN_ERROR';
    final message = body['message'] as String? ?? 'An unexpected error occurred';
    final details = body['details'];

    switch (errorCode) {
      case 'INVALID_URL':
        throw InvalidUrlException(message, details: details);
      case 'COMMENT_NOT_FOUND':
        throw CommentNotFoundException(message, details: details);
      case 'STICKER_NOT_FOUND':
        throw StickerNotFoundException(message, details: details);
      case 'MISSING_COMMENT_ID':
        throw MissingCommentIdException(message, details: details);
      case 'VALIDATION_ERROR':
        throw ValidationException(message, details: details);
      case 'PROVIDER_AUTH_ERROR':
        throw ProviderAuthException(message, details: details);
      case 'EXTRACTION_ERROR':
        throw ExtractionException(message, details: details);
      default:
        throw ApiException(
          message,
          errorCode: errorCode,
          statusCode: response.statusCode,
          details: details,
        );
    }
  }

  void close() {
    _httpClient.close();
  }
}
