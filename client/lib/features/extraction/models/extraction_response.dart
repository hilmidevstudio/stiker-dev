/// Author info returned by backend proxy
class AuthorInfo {
  final String uid;
  final String uniqueId;
  final String nickname;
  final String avatarUrl;

  const AuthorInfo({
    required this.uid,
    required this.uniqueId,
    required this.nickname,
    required this.avatarUrl,
  });

  factory AuthorInfo.fromJson(Map<String, dynamic> json) {
    return AuthorInfo(
      uid: json['uid'] as String? ?? '',
      uniqueId: json['unique_id'] as String? ?? '',
      nickname: json['nickname'] as String? ?? '',
      avatarUrl: json['avatar_url'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'uid': uid,
        'unique_id': uniqueId,
        'nickname': nickname,
        'avatar_url': avatarUrl,
      };
}

/// Sticker media metadata returned by backend proxy
class StickerMetadata {
  final String stickerId;
  final int stickerType;
  final bool isAnimated;
  final String format;
  final String mediaUrl;
  final String? staticUrl;
  final String? animatedUrl;
  final int width;
  final int height;

  const StickerMetadata({
    required this.stickerId,
    required this.stickerType,
    required this.isAnimated,
    required this.format,
    required this.mediaUrl,
    this.staticUrl,
    this.animatedUrl,
    required this.width,
    required this.height,
  });

  factory StickerMetadata.fromJson(Map<String, dynamic> json) {
    return StickerMetadata(
      stickerId: json['sticker_id']?.toString() ?? '',
      stickerType: json['sticker_type'] as int? ?? 1,
      isAnimated: json['is_animated'] as bool? ?? false,
      format: json['format'] as String? ?? 'webp',
      mediaUrl: json['media_url'] as String? ?? '',
      staticUrl: json['static_url'] as String?,
      animatedUrl: json['animated_url'] as String?,
      width: json['width'] as int? ?? 512,
      height: json['height'] as int? ?? 512,
    );
  }

  Map<String, dynamic> toJson() => {
        'sticker_id': stickerId,
        'sticker_type': stickerType,
        'is_animated': isAnimated,
        'format': format,
        'media_url': mediaUrl,
        if (staticUrl != null) 'static_url': staticUrl,
        if (animatedUrl != null) 'animated_url': animatedUrl,
        'width': width,
        'height': height,
      };
}

/// Normalized extraction response from backend proxy
class ExtractionResponse {
  final bool success;
  final String message;
  final String videoId;
  final String commentId;
  final String canonicalUrl;
  final String commentText;
  final int createTime;
  final int diggCount;
  final AuthorInfo author;
  final StickerMetadata sticker;
  final String providerUsed;
  final String? sha256;

  const ExtractionResponse({
    required this.success,
    required this.message,
    required this.videoId,
    required this.commentId,
    required this.canonicalUrl,
    required this.commentText,
    required this.createTime,
    required this.diggCount,
    required this.author,
    required this.sticker,
    required this.providerUsed,
    this.sha256,
  });

  factory ExtractionResponse.fromJson(Map<String, dynamic> json) {
    return ExtractionResponse(
      success: json['success'] as bool? ?? false,
      message: json['message'] as String? ?? '',
      videoId: json['video_id']?.toString() ?? '',
      commentId: json['comment_id']?.toString() ?? '',
      canonicalUrl: json['canonical_url'] as String? ?? '',
      commentText: json['comment_text'] as String? ?? '',
      createTime: json['create_time'] as int? ?? 0,
      diggCount: json['digg_count'] as int? ?? 0,
      author: AuthorInfo.fromJson(
        json['author'] as Map<String, dynamic>? ?? {},
      ),
      sticker: StickerMetadata.fromJson(
        json['sticker'] as Map<String, dynamic>? ?? {},
      ),
      providerUsed: json['provider_used'] as String? ?? 'unknown',
      sha256: json['sha256'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'success': success,
        'message': message,
        'video_id': videoId,
        'comment_id': commentId,
        'canonical_url': canonicalUrl,
        'comment_text': commentText,
        'create_time': createTime,
        'digg_count': diggCount,
        'author': author.toJson(),
        'sticker': sticker.toJson(),
        'provider_used': providerUsed,
        if (sha256 != null) 'sha256': sha256,
      };
}
