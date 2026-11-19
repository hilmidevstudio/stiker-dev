import '../../../core/constants/db_constants.dart';

/// Entity model representing a virtual WhatsApp pack in SQLite
/// Conforms to schema defined in docs/06-persistent-storage.md
class PackModel {
  final int? id;
  final String identifier;
  final String name;
  final String publisher;
  final String trayImagePath;
  final bool isAnimated;
  final int stickerCount;
  final String createdAt;
  final String updatedAt;

  PackModel({
    this.id,
    required this.identifier,
    required this.name,
    this.publisher = 'StickerDrop User',
    required this.trayImagePath,
    this.isAnimated = false,
    this.stickerCount = 0,
    String? createdAt,
    String? updatedAt,
  })  : createdAt = createdAt ?? DateTime.now().toUtc().toIso8601String(),
        updatedAt = updatedAt ?? DateTime.now().toUtc().toIso8601String();

  factory PackModel.fromMap(Map<String, dynamic> map) {
    return PackModel(
      id: map[DbConstants.colPackId] as int?,
      identifier: map[DbConstants.colPackIdentifier] as String,
      name: map[DbConstants.colPackName] as String,
      publisher:
          map[DbConstants.colPackPublisher] as String? ?? 'StickerDrop User',
      trayImagePath: map[DbConstants.colPackTrayImagePath] as String,
      isAnimated: (map[DbConstants.colPackIsAnimated] as int? ?? 0) == 1,
      stickerCount: map[DbConstants.colPackStickerCount] as int? ?? 0,
      createdAt: map[DbConstants.colPackCreatedAt] as String,
      updatedAt: map[DbConstants.colPackUpdatedAt] as String,
    );
  }

  Map<String, dynamic> toMap({bool includeId = true}) {
    final map = <String, dynamic>{
      DbConstants.colPackIdentifier: identifier,
      DbConstants.colPackName: name,
      DbConstants.colPackPublisher: publisher,
      DbConstants.colPackTrayImagePath: trayImagePath,
      DbConstants.colPackIsAnimated: isAnimated ? 1 : 0,
      DbConstants.colPackStickerCount: stickerCount,
      DbConstants.colPackCreatedAt: createdAt,
      DbConstants.colPackUpdatedAt: updatedAt,
    };
    if (includeId && id != null) {
      map[DbConstants.colPackId] = id;
    }
    return map;
  }

  PackModel copyWith({
    int? id,
    String? identifier,
    String? name,
    String? publisher,
    String? trayImagePath,
    bool? isAnimated,
    int? stickerCount,
    String? createdAt,
    String? updatedAt,
  }) {
    return PackModel(
      id: id ?? this.id,
      identifier: identifier ?? this.identifier,
      name: name ?? this.name,
      publisher: publisher ?? this.publisher,
      trayImagePath: trayImagePath ?? this.trayImagePath,
      isAnimated: isAnimated ?? this.isAnimated,
      stickerCount: stickerCount ?? this.stickerCount,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
