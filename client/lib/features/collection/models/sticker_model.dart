import 'package:uuid/uuid.dart';
import '../../../core/constants/db_constants.dart';

/// Entity model representing a persistent sticker record in SQLite
/// Conforms to schema defined in docs/06-persistent-storage.md
class StickerModel {
  final int? id;
  final String internalId;
  final String sourcePlatform;
  final String sourceVideoId;
  final String sourceCommentId;
  final String sourceAuthor;
  final String? stickerId;
  final String originalMediaUrl;
  final String localMediaPath;
  final String mediaType;
  final bool isAnimated;
  final int width;
  final int height;
  final int fileSize;
  final int frameCount;
  final int durationMs;
  final String sha256;
  final String exportStatus;
  final String createdAt;
  final String updatedAt;

  StickerModel({
    this.id,
    String? internalId,
    this.sourcePlatform = 'tiktok',
    required this.sourceVideoId,
    required this.sourceCommentId,
    required this.sourceAuthor,
    this.stickerId,
    required this.originalMediaUrl,
    required this.localMediaPath,
    required this.mediaType,
    required this.isAnimated,
    required this.width,
    required this.height,
    required this.fileSize,
    this.frameCount = 1,
    this.durationMs = 0,
    required this.sha256,
    this.exportStatus = DbConstants.exportStatusPending,
    String? createdAt,
    String? updatedAt,
  })  : internalId = internalId ?? const Uuid().v4(),
        createdAt = createdAt ?? DateTime.now().toUtc().toIso8601String(),
        updatedAt = updatedAt ?? DateTime.now().toUtc().toIso8601String();

  /// Create model from SQLite database row map
  factory StickerModel.fromMap(Map<String, dynamic> map) {
    return StickerModel(
      id: map[DbConstants.colStickerId] as int?,
      internalId: map[DbConstants.colStickerInternalId] as String,
      sourcePlatform:
          map[DbConstants.colStickerSourcePlatform] as String? ?? 'tiktok',
      sourceVideoId: map[DbConstants.colStickerSourceVideoId] as String,
      sourceCommentId: map[DbConstants.colStickerSourceCommentId] as String,
      sourceAuthor: map[DbConstants.colStickerSourceAuthor] as String,
      stickerId: map[DbConstants.colStickerThirdPartyId] as String?,
      originalMediaUrl: map[DbConstants.colStickerOriginalMediaUrl] as String,
      localMediaPath: map[DbConstants.colStickerLocalMediaPath] as String,
      mediaType: map[DbConstants.colStickerMediaType] as String,
      isAnimated: (map[DbConstants.colStickerIsAnimated] as int? ?? 0) == 1,
      width: map[DbConstants.colStickerWidth] as int? ?? 512,
      height: map[DbConstants.colStickerHeight] as int? ?? 512,
      fileSize: map[DbConstants.colStickerFileSize] as int? ?? 0,
      frameCount: map[DbConstants.colStickerFrameCount] as int? ?? 1,
      durationMs: map[DbConstants.colStickerDurationMs] as int? ?? 0,
      sha256: map[DbConstants.colStickerSha256] as String,
      exportStatus: map[DbConstants.colStickerExportStatus] as String? ??
          DbConstants.exportStatusPending,
      createdAt: map[DbConstants.colStickerCreatedAt] as String,
      updatedAt: map[DbConstants.colStickerUpdatedAt] as String,
    );
  }

  /// Convert model to SQLite database column map
  Map<String, dynamic> toMap({bool includeId = true}) {
    final map = <String, dynamic>{
      DbConstants.colStickerInternalId: internalId,
      DbConstants.colStickerSourcePlatform: sourcePlatform,
      DbConstants.colStickerSourceVideoId: sourceVideoId,
      DbConstants.colStickerSourceCommentId: sourceCommentId,
      DbConstants.colStickerSourceAuthor: sourceAuthor,
      DbConstants.colStickerThirdPartyId: stickerId,
      DbConstants.colStickerOriginalMediaUrl: originalMediaUrl,
      DbConstants.colStickerLocalMediaPath: localMediaPath,
      DbConstants.colStickerMediaType: mediaType,
      DbConstants.colStickerIsAnimated: isAnimated ? 1 : 0,
      DbConstants.colStickerWidth: width,
      DbConstants.colStickerHeight: height,
      DbConstants.colStickerFileSize: fileSize,
      DbConstants.colStickerFrameCount: frameCount,
      DbConstants.colStickerDurationMs: durationMs,
      DbConstants.colStickerSha256: sha256,
      DbConstants.colStickerExportStatus: exportStatus,
      DbConstants.colStickerCreatedAt: createdAt,
      DbConstants.colStickerUpdatedAt: updatedAt,
    };
    if (includeId && id != null) {
      map[DbConstants.colStickerId] = id;
    }
    return map;
  }

  StickerModel copyWith({
    int? id,
    String? internalId,
    String? sourcePlatform,
    String? sourceVideoId,
    String? sourceCommentId,
    String? sourceAuthor,
    String? stickerId,
    String? originalMediaUrl,
    String? localMediaPath,
    String? mediaType,
    bool? isAnimated,
    int? width,
    int? height,
    int? fileSize,
    int? frameCount,
    int? durationMs,
    String? sha256,
    String? exportStatus,
    String? createdAt,
    String? updatedAt,
  }) {
    return StickerModel(
      id: id ?? this.id,
      internalId: internalId ?? this.internalId,
      sourcePlatform: sourcePlatform ?? this.sourcePlatform,
      sourceVideoId: sourceVideoId ?? this.sourceVideoId,
      sourceCommentId: sourceCommentId ?? this.sourceCommentId,
      sourceAuthor: sourceAuthor ?? this.sourceAuthor,
      stickerId: stickerId ?? this.stickerId,
      originalMediaUrl: originalMediaUrl ?? this.originalMediaUrl,
      localMediaPath: localMediaPath ?? this.localMediaPath,
      mediaType: mediaType ?? this.mediaType,
      isAnimated: isAnimated ?? this.isAnimated,
      width: width ?? this.width,
      height: height ?? this.height,
      fileSize: fileSize ?? this.fileSize,
      frameCount: frameCount ?? this.frameCount,
      durationMs: durationMs ?? this.durationMs,
      sha256: sha256 ?? this.sha256,
      exportStatus: exportStatus ?? this.exportStatus,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
