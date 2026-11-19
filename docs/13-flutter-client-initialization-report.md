## 13. Flutter Client Module — Initialization Report

---

### Status: ✅ COMPLETE — Foundation Phase

**Date**: 2026-11-17  
**Module**: `client/` — Flutter Android Application  
**Package Name**: `com.stickerdrop.app`

---

### Deliverables Created

#### `pubspec.yaml` — Dependencies
| Package | Version | Purpose |
|---|---|---|
| `sqflite` | ^2.3.0 | SQLite relational persistence |
| `sqflite_common_ffi` | ^2.3.0 | Desktop/test SQLite FFI factory |
| `path_provider` | ^2.1.1 | Cross-platform filesystem paths |
| `http` | ^1.1.0 | HTTP client for Backend Proxy |
| `crypto` | ^3.0.3 | SHA-256 hashing |
| `uuid` | ^4.2.1 | UUIDv4 internal sticker IDs |
| `test` | ^1.24.0 | Pure-Dart unit test runner |

---

#### `lib/core/` — Foundation Layer

| File | Responsibility |
|---|---|
| `constants/api_constants.dart` | Backend URL, endpoint paths, timeouts |
| `constants/db_constants.dart` | All SQLite table/column name constants |
| `database/tables.dart` | DDL CREATE TABLE + CREATE INDEX statements (exact spec from `06-persistent-storage.md`) |
| `database/database_helper.dart` | sqflite open helper, FK PRAGMA, migration runner, injectable factory for tests |
| `network/api_client.dart` | HTTP client wrapping `POST /v1/resolve-and-extract` and `GET /health` |
| `network/api_exceptions.dart` | Full exception hierarchy mirroring backend error taxonomy (ADR-009) |

---

#### `lib/features/` — Domain Feature Modules

| Feature | Files | Key Responsibilities |
|---|---|---|
| `extraction/` | `extraction_request.dart`, `extraction_response.dart`, `extraction_service.dart` | Backend proxy consumer; normalizes `AuthorInfo`, `StickerMetadata`, `ExtractionResponse` |
| `collection/` | `sticker_model.dart`, `pack_model.dart`, `pack_item_model.dart`, `sticker_repository.dart`, `pack_repository.dart`, `sha256_storage_manager.dart` | SQLite CRUD; ADR-005 two-tier deduplication; atomic SHA-256 media storage |
| `whatsapp_export/` | `intent_bridge.dart`, `whatsapp_content_provider.dart` | Android `ENABLE_STICKER_PACK` Intent dispatch stub; `contents.json` builder |

---

#### `android/` — Platform Configuration

| File | Key Configuration |
|---|---|
| `app/build.gradle` | `applicationId "com.stickerdrop.app"`, `minSdkVersion 21`, `targetSdkVersion 34` |
| `app/src/main/AndroidManifest.xml` | `WhatsAppStickerContentProvider` exported with `com.whatsapp.sticker.READ` permission; `<queries>` block for WhatsApp + WA Business |
| `kotlin/.../MainActivity.kt` | FlutterActivity entry point |
| `kotlin/.../WhatsAppStickerContentProvider.kt` | ContentProvider stub — full implementation in Phase E |

---

#### `test/` — Unit Test Suite

| Test File | Tests | Coverage |
|---|---|---|
| `sqlite_repository_test.dart` | 20 tests | Schema creation, CRUD, ADR-005 Gate 1 & Gate 2 deduplication, cascade delete, library integrity scanner |
| `api_client_test.dart` | 10 tests | HTTP mock client for all 6 error codes + success response deserialization |
| `model_serialization_test.dart` | 10 tests | `StickerModel`, `PackModel`, `PackItemModel` round-trip serialization, UUID generation, emoji JSON |

**Total unit tests authored: 40**

---

### ADR Compliance Matrix

| ADR | Status | Implementation |
|---|---|---|
| ADR-001 Hybrid Architecture | ✅ | `ApiClient` connects to backend only; no TikTok direct calls |
| ADR-002 SQLite Persistence | ✅ | `DatabaseHelper` + exact DDL from `06-persistent-storage.md` |
| ADR-005 Two-Tier Deduplication | ✅ | Gate 1 (`source_comment_id`) + Gate 2 (`sha256`) in `StickerRepository.insertSticker()` |
| ADR-006 Pack Partitioning | ✅ | `PackRepository` CRUD supports virtual pack chunking |
| ADR-007 Static/Animated Isolation | ✅ | `getAllPacks(isAnimated:)` strict filter |
| ADR-009 FastAPI Backend | ✅ | Full error taxonomy mapped in `api_exceptions.dart` + `api_client.dart` |

---

### Next Phase Requirements

- [ ] **Phase E**: Implement `WhatsAppStickerContentProvider.kt` full cursor response
- [ ] **Phase E**: Implement `IntentBridge` native method channel in Kotlin
- [ ] **UI Layer**: Sticker input screen, collection browser, pack export screen
- [ ] **Integration**: Wire `ExtractionService` → `StickerRepository` → `Sha256StorageManager`
- [ ] **Flutter pub get**: Run `flutter pub get` once Flutter SDK is available on PATH
