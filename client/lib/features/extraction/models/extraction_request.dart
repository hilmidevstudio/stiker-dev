/// Payload for backend proxy extraction request
class ExtractionRequest {
  final String url;
  final String? provider;

  const ExtractionRequest({
    required this.url,
    this.provider,
  });

  Map<String, dynamic> toJson() => {
        'url': url,
        if (provider != null) 'provider': provider,
      };
}
