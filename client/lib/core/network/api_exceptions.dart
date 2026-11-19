/// Domain exceptions mapping backend proxy error taxonomy
class ApiException implements Exception {
  final String message;
  final String errorCode;
  final int statusCode;
  final dynamic details;

  const ApiException(
    this.message, {
    required this.errorCode,
    required this.statusCode,
    this.details,
  });

  @override
  String toString() => 'ApiException [$errorCode - $statusCode]: $message';
}

/// 400 Bad Request — Malformed or non-URL string
class InvalidUrlException extends ApiException {
  const InvalidUrlException(super.message, {super.details})
      : super(
          errorCode: 'INVALID_URL',
          statusCode: 400,
        );
}

/// 404 Not Found — Comment ID was not found in video or reply threads
class CommentNotFoundException extends ApiException {
  const CommentNotFoundException(super.message, {super.details})
      : super(
          errorCode: 'COMMENT_NOT_FOUND',
          statusCode: 404,
        );
}

/// 404 Not Found — Comment located, but contains no sticker
class StickerNotFoundException extends ApiException {
  const StickerNotFoundException(super.message, {super.details})
      : super(
          errorCode: 'STICKER_NOT_FOUND',
          statusCode: 404,
        );
}

/// 422 Unprocessable Entity — Link points to video without comment ID
class MissingCommentIdException extends ApiException {
  const MissingCommentIdException(super.message, {super.details})
      : super(
          errorCode: 'MISSING_COMMENT_ID',
          statusCode: 422,
        );
}

/// 422 Unprocessable Entity — Request validation failed
class ValidationException extends ApiException {
  const ValidationException(super.message, {super.details})
      : super(
          errorCode: 'VALIDATION_ERROR',
          statusCode: 422,
        );
}

/// 500 Server Error — Upstream scraping API key error
class ProviderAuthException extends ApiException {
  const ProviderAuthException(super.message, {super.details})
      : super(
          errorCode: 'PROVIDER_AUTH_ERROR',
          statusCode: 500,
        );
}

/// 502 Bad Gateway — Upstream extraction failure or rate limiting
class ExtractionException extends ApiException {
  const ExtractionException(super.message, {super.details})
      : super(
          errorCode: 'EXTRACTION_ERROR',
          statusCode: 502,
        );
}

/// Client-side network or connection failure
class NetworkConnectionException extends ApiException {
  const NetworkConnectionException(super.message, {super.details})
      : super(
          errorCode: 'NETWORK_CONNECTION_ERROR',
          statusCode: 0,
        );
}
