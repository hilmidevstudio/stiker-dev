import 'dart:async';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart' as sqflite;
import 'package:sqflite_common/sqlite_api.dart';
import '../constants/db_constants.dart';
import 'tables.dart';

/// SQLite Database Open Helper for StickerDrop Local Storage
/// Adheres to ADR-002 and 06-persistent-storage.md
class DatabaseHelper {
  static final DatabaseHelper instance = DatabaseHelper._internal();

  Database? _db;
  DatabaseFactory? _customFactory;
  String? _customDatabasePath;

  DatabaseHelper._internal();

  /// Public constructor for unit testing — creates an isolated instance.
  /// Inject [factory] and [databasePath] after construction.
  DatabaseHelper.forTesting({
    DatabaseFactory? factory,
    String? databasePath,
  })  : _customFactory = factory,
        _customDatabasePath = databasePath;

  /// Inject custom DatabaseFactory for unit testing (e.g. sqflite_common_ffi)
  void setDatabaseFactory(DatabaseFactory factory) {
    _customFactory = factory;
  }

  /// Inject custom database path for testing (e.g. in_memory_db_path or temporary folder)
  void setCustomDatabasePath(String? path) {
    _customDatabasePath = path;
  }

  /// Database getter with lazy initialization
  Future<Database> get database async {
    if (_db != null && _db!.isOpen) {
      return _db!;
    }
    _db = await _initDatabase();
    return _db!;
  }

  Future<Database> _initDatabase() async {
    final customFactory = _customFactory;

    if (customFactory != null) {
      final String dbPath = _customDatabasePath ??
          p.join(await customFactory.getDatabasesPath(), DbConstants.databaseName);
      return await customFactory.openDatabase(
        dbPath,
        options: OpenDatabaseOptions(
          version: DbConstants.databaseVersion,
          onConfigure: _onConfigure,
          onCreate: _onCreate,
          onUpgrade: _onUpgrade,
        ),
      );
    }

    // Standard Android / iOS mobile runtime using flutter sqflite plugin
    final String basePath = await sqflite.getDatabasesPath();
    final String dbPath = _customDatabasePath ?? p.join(basePath, DbConstants.databaseName);

    return await sqflite.openDatabase(
      dbPath,
      version: DbConstants.databaseVersion,
      onConfigure: _onConfigure,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  /// Ensure foreign key constraints are enforced on SQLite connections
  Future<void> _onConfigure(Database db) async {
    await db.execute('PRAGMA foreign_keys = ON');
  }

  /// Execute initial DDL scripts and record migration state
  Future<void> _onCreate(Database db, int version) async {
    final batch = db.batch();

    for (final statement in Tables.initialSchemaStatements) {
      batch.execute(statement);
    }

    // Record initial migration
    batch.rawInsert(
      '''
      INSERT INTO ${DbConstants.tableMigrations} (${DbConstants.colMigrationVersion}, ${DbConstants.colMigrationAppliedAt})
      VALUES (?, ?)
      ''',
      [version, DateTime.now().toUtc().toIso8601String()],
    );

    await batch.commit(noResult: true);
  }

  /// Future database schema migrations
  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    // Migration paths will be added here for schema updates beyond v1
  }

  /// Helper to run operations within an ACID transaction
  Future<T> transaction<T>(Future<T> Function(Transaction txn) action) async {
    final db = await database;
    return await db.transaction<T>(action);
  }

  /// Close active database connection
  Future<void> close() async {
    if (_db != null && _db!.isOpen) {
      await _db!.close();
      _db = null;
    }
  }

  /// Reset helper state (useful for tests)
  Future<void> reset() async {
    await close();
    _customDatabasePath = null;
    _customFactory = null;
  }
}
