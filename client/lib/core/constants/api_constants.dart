/// Constants for API Backend Proxy Consumer and Link Resolver
class ApiConstants {
  ApiConstants._();

  /// Default base URL for local testing.
  /// On Android emulator, '10.0.2.2' maps to the host machine's '127.0.0.1'.
  static const String defaultAndroidEmulatorBaseUrl = 'http://10.0.2.2:8000';
  static const String defaultDesktopBaseUrl = 'http://127.0.0.1:8000';

  /// Active base URL (defaults to emulator, can be configured at runtime)
  static String activeBaseUrl = defaultDesktopBaseUrl;

  /// Endpoints
  static const String healthEndpoint = '/health';
  static const String resolveAndExtractEndpoint = '/v1/resolve-and-extract';

  /// Timeout durations
  static const Duration requestTimeout = Duration(seconds: 30);
  static const Duration connectTimeout = Duration(seconds: 10);

  /// Standard Headers
  static const Map<String, String> jsonHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}
