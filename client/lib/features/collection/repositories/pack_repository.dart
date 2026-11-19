import 'package:sqflite_common/sqlite_api.dart';
import '../../../core/constants/db_constants.dart';
import '../../../core/database/database_helper.dart';
import '../models/pack_model.dart';
import '../models/pack_item_model.dart';

/// SQLite Repository for managing Pack and PackItem persistence
/// Implements ADR-006 (Virtual Pack Partitioning) and ADR-007 (Animated/Static isolation)
class PackRepository {
  final DatabaseHelper _dbHelper;

  PackRepository({DatabaseHelper? dbHelper})
      : _dbHelper = dbHelper ?? DatabaseHelper.instance;

  Future<Database> get _db async => await _dbHelper.database;

  /// Insert a new pack record
  Future<PackModel> insertPack(PackModel pack) async {
    final db = await _db;
    final id = await db.insert(
      DbConstants.tablePacks,
      pack.toMap(includeId: false),
      conflictAlgorithm: ConflictAlgorithm.abort,
    );
    return pack.copyWith(id: id);
  }

  /// Find pack by its unique WhatsApp identifier string
  Future<PackModel?> getPackByIdentifier(String identifier) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tablePacks,
      where: '${DbConstants.colPackIdentifier} = ?',
      whereArgs: [identifier],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return PackModel.fromMap(results.first);
  }

  /// Get pack by primary key
  Future<PackModel?> getPackById(int id) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tablePacks,
      where: '${DbConstants.colPackId} = ?',
      whereArgs: [id],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return PackModel.fromMap(results.first);
  }

  /// List all packs, optionally filtered by animated status (ADR-007)
  Future<List<PackModel>> getAllPacks({bool? isAnimated}) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tablePacks,
      where: isAnimated != null
          ? '${DbConstants.colPackIsAnimated} = ?'
          : null,
      whereArgs: isAnimated != null ? [isAnimated ? 1 : 0] : null,
      orderBy: '${DbConstants.colPackId} ASC',
    );
    return results.map((m) => PackModel.fromMap(m)).toList();
  }

  /// Update pack sticker count
  Future<void> updateStickerCount(int packId, int newCount) async {
    final db = await _db;
    await db.update(
      DbConstants.tablePacks,
      {
        DbConstants.colPackStickerCount: newCount,
        DbConstants.colPackUpdatedAt: DateTime.now().toUtc().toIso8601String(),
      },
      where: '${DbConstants.colPackId} = ?',
      whereArgs: [packId],
    );
  }

  /// Delete a pack (cascades to pack_items via ON DELETE CASCADE)
  Future<int> deletePack(int packId) async {
    final db = await _db;
    return await db.delete(
      DbConstants.tablePacks,
      where: '${DbConstants.colPackId} = ?',
      whereArgs: [packId],
    );
  }

  /// Add a sticker to a pack
  Future<PackItemModel> addStickerToPack(PackItemModel item) async {
    final db = await _db;
    final id = await db.insert(
      DbConstants.tablePackItems,
      item.toMap(includeId: false),
      conflictAlgorithm: ConflictAlgorithm.ignore,
    );
    return PackItemModel(
      id: id,
      packId: item.packId,
      stickerId: item.stickerId,
      sortOrder: item.sortOrder,
      emojis: item.emojis,
    );
  }

  /// Get all items in a pack, ordered by sort_order
  Future<List<PackItemModel>> getPackItems(int packId) async {
    final db = await _db;
    final results = await db.query(
      DbConstants.tablePackItems,
      where: '${DbConstants.colPackItemPackId} = ?',
      whereArgs: [packId],
      orderBy: '${DbConstants.colPackItemSortOrder} ASC',
    );
    return results.map((m) => PackItemModel.fromMap(m)).toList();
  }

  /// Remove a sticker from a pack
  Future<int> removeStickerFromPack(int packId, int stickerId) async {
    final db = await _db;
    return await db.delete(
      DbConstants.tablePackItems,
      where: '${DbConstants.colPackItemPackId} = ? AND '
          '${DbConstants.colPackItemStickerId} = ?',
      whereArgs: [packId, stickerId],
    );
  }
}
