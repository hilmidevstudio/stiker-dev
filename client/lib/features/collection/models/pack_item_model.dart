import 'dart:convert';
import '../../../core/constants/db_constants.dart';

/// Entity model representing a sticker entry inside a pack
/// Conforms to schema defined in docs/06-persistent-storage.md
class PackItemModel {
  final int? id;
  final int packId;
  final int stickerId;
  final int sortOrder;
  final List<String> emojis;

  PackItemModel({
    this.id,
    required this.packId,
    required this.stickerId,
    this.sortOrder = 0,
    List<String>? emojis,
  }) : emojis = emojis ?? const ['🔥'];

  factory PackItemModel.fromMap(Map<String, dynamic> map) {
    List<String> parsedEmojis = ['🔥'];
    final rawEmojis = map[DbConstants.colPackItemEmojis];
    if (rawEmojis is String) {
      try {
        final decoded = jsonDecode(rawEmojis);
        if (decoded is List) {
          parsedEmojis = decoded.map((e) => e.toString()).toList();
        }
      } catch (_) {
        parsedEmojis = [rawEmojis];
      }
    } else if (rawEmojis is List) {
      parsedEmojis = rawEmojis.map((e) => e.toString()).toList();
    }

    return PackItemModel(
      id: map[DbConstants.colPackItemId] as int?,
      packId: map[DbConstants.colPackItemPackId] as int,
      stickerId: map[DbConstants.colPackItemStickerId] as int,
      sortOrder: map[DbConstants.colPackItemSortOrder] as int? ?? 0,
      emojis: parsedEmojis,
    );
  }

  Map<String, dynamic> toMap({bool includeId = true}) {
    final map = <String, dynamic>{
      DbConstants.colPackItemPackId: packId,
      DbConstants.colPackItemStickerId: stickerId,
      DbConstants.colPackItemSortOrder: sortOrder,
      DbConstants.colPackItemEmojis: jsonEncode(emojis),
    };
    if (includeId && id != null) {
      map[DbConstants.colPackItemId] = id;
    }
    return map;
  }
}
