import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as p;
import 'package:uuid/uuid.dart';

/// Result of media storage operation
class MediaStorageResult {
  final String relativePath;
  final String absolutePath;
  final String sha256;
  final int fileSize;
  final bool isExistingFile;

  const MediaStorageResult({
    required this.relativePath,
    required this.absolutePath,
    required this.sha256,
    required this.fileSize,
    required this.isExistingFile,
  });
}

/// Storage manager responsible for local filesystem media repository
/// Enforces SHA-256 naming, atomic writes, and deduplication per ADR-002 & ADR-005
class Sha256StorageManager {
  final Directory _baseDir;
  final String _mediaSubDir;

  Sha256StorageManager({
    required Directory baseDir,
    String mediaSubDir = 'media',
  })  : _baseDir = baseDir,
        _mediaSubDir = mediaSubDir;

  Directory get mediaDirectory => Directory(p.join(_baseDir.path, _mediaSubDir));

  /// Ensure the media folder exists
  Future<void> initialize() async {
    final dir = mediaDirectory;
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
  }

  /// Compute SHA-256 checksum hex string from byte stream
  static String computeSha256(List<int> bytes) {
    return sha256.convert(bytes).toString();
  }

  /// Compute SHA-256 checksum directly from file
  static Future<String> computeFileSha256(File file) async {
    final bytes = await file.readAsBytes();
    return computeSha256(bytes);
  }

  /// Save raw media bytes with atomic write and SHA-256 content addressing
  Future<MediaStorageResult> saveMediaBytes({
    required List<int> bytes,
    required String extension,
  }) async {
    await initialize();

    final cleanExt = extension.startsWith('.') ? extension.substring(1) : extension;
    final hash = computeSha256(bytes);
    final fileName = '$hash.$cleanExt';
    final relativePath = p.join(_mediaSubDir, fileName).replaceAll(r'\', '/');
    final permanentFile = File(p.join(mediaDirectory.path, fileName));

    // Media-Level Deduplication (ADR-005 Gate 2):
    // If exact binary file already exists on disk, skip redundant writing
    if (await permanentFile.exists()) {
      final existingSize = await permanentFile.length();
      return MediaStorageResult(
        relativePath: relativePath,
        absolutePath: permanentFile.path,
        sha256: hash,
        fileSize: existingSize,
        isExistingFile: true,
      );
    }

    // Atomic File Write (06-persistent-storage.md Section 5.1):
    // Write to a temporary file first, verify integrity, then rename atomically
    final tempFileName = 'tmp_${const Uuid().v4()}.$cleanExt';
    final tempFile = File(p.join(mediaDirectory.path, tempFileName));

    await tempFile.writeAsBytes(bytes, flush: true);

    // Verify written file checksum
    final writtenHash = await computeFileSha256(tempFile);
    if (writtenHash != hash) {
      if (await tempFile.exists()) await tempFile.delete();
      throw StateError(
        'Checksum verification failed during atomic media write: $writtenHash != $hash',
      );
    }

    // Atomically rename temporary file to content-addressed permanent file
    await tempFile.rename(permanentFile.path);

    return MediaStorageResult(
      relativePath: relativePath,
      absolutePath: permanentFile.path,
      sha256: hash,
      fileSize: bytes.length,
      isExistingFile: false,
    );
  }

  /// Validate file presence, size, and hash integrity against database record
  Future<bool> verifyMediaIntegrity({
    required String relativePath,
    required String expectedSha256,
    required int expectedSize,
  }) async {
    final file = File(p.join(_baseDir.path, relativePath));
    if (!await file.exists()) {
      return false;
    }

    final actualSize = await file.length();
    if (actualSize != expectedSize) {
      return false;
    }

    final actualHash = await computeFileSha256(file);
    return actualHash == expectedSha256;
  }

  /// Retrieve the absolute File handle for a relative media path
  File getFileForRelativePath(String relativePath) {
    return File(p.join(_baseDir.path, relativePath));
  }

  /// Delete a media file from disk
  Future<bool> deleteMediaFile(String relativePath) async {
    final file = getFileForRelativePath(relativePath);
    if (await file.exists()) {
      await file.delete();
      return true;
    }
    return false;
  }
}
