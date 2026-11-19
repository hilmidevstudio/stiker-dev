# StickerDrop Flutter Client Module

Flutter (Android) client application for StickerDrop — TikTok comment sticker extractor and WhatsApp pack exporter.

## Module Status

This module contains the **foundation layer only** (Phase 1):
- ✅ SQLite local database (sqflite) — full DDL schema per `docs/06-persistent-storage.md`
- ✅ HTTP Client layer connected to Backend Proxy microservice
- ✅ Two-tier deduplication (ADR-005)
- ✅ SHA-256 content-addressed storage manager
- ✅ WhatsApp ContentProvider stub (Android Manifest registered)
- ✅ Intent Bridge stub for WhatsApp sticker pack import
- ✅ Unit tests for all repository, storage, and network layers

## Project Structure

```
client/
├── android/                    # Android platform configuration
│   └── app/
│       ├── build.gradle        # applicationId: com.stickerdrop.app
│       ├── src/main/
│       │   ├── AndroidManifest.xml         # WhatsApp queries + ContentProvider
│       │   └── kotlin/com/stickerdrop/app/
│       │       ├── MainActivity.kt
│       │       └── WhatsAppStickerContentProvider.kt  # Stub
│
├── lib/
│   ├── main.dart               # Bootstrap entry point (minimal UI)
│   ├── client.dart             # Barrel export
│   │
│   ├── core/
│   │   ├── constants/
│   │   │   ├── api_constants.dart          # Backend URL, endpoints, timeouts
│   │   │   └── db_constants.dart           # SQLite table/column name constants
│   │   ├── database/
│   │   │   ├── database_helper.dart        # sqflite open/migration helper
│   │   │   └── tables.dart                 # DDL CREATE TABLE statements
│   │   └── network/
│   │       ├── api_client.dart             # HTTP client for Backend Proxy
│   │       └── api_exceptions.dart         # Domain exception hierarchy
│   │
│   ├── features/
│   │   ├── extraction/
│   │   │   ├── models/
│   │   │   │   ├── extraction_request.dart
│   │   │   │   └── extraction_response.dart   # AuthorInfo, StickerMetadata
│   │   │   └── services/
│   │   │       └── extraction_service.dart
│   │   │
│   │   ├── collection/
│   │   │   ├── models/
│   │   │   │   ├── sticker_model.dart
│   │   │   │   ├── pack_model.dart
│   │   │   │   └── pack_item_model.dart
│   │   │   ├── repositories/
│   │   │   │   ├── sticker_repository.dart    # Insert, query, deduplicate, integrity
│   │   │   │   └── pack_repository.dart       # Pack & PackItem CRUD
│   │   │   └── storage/
│   │   │       └── sha256_storage_manager.dart  # Atomic write, content addressing
│   │   │
│   │   └── whatsapp_export/
│   │       ├── intent_bridge.dart             # Android Intent dispatcher (stub)
│   │       └── whatsapp_content_provider.dart # contents.json builder
│
└── test/
    ├── core/network/
    │   └── api_client_test.dart     # 10 HTTP layer tests (mock client)
    └── features/collection/
        ├── sqlite_repository_test.dart  # 20 SQLite + deduplication tests
        └── model_serialization_test.dart  # 10 model round-trip tests
```

## Running Tests

```bash
# Install dependencies first
flutter pub get

# Run all unit tests (pure-Dart, no device required)
flutter test test/

# Run specific test file
flutter test test/features/collection/sqlite_repository_test.dart
flutter test test/core/network/api_client_test.dart
```

## Backend Proxy Connection

The HTTP client connects to the FastAPI microservice (`backend/`) defined in ADR-009.

| Environment          | Base URL                  |
|---------------------|---------------------------|
| Android Emulator     | `http://10.0.2.2:8000`    |
| Physical Device / Desktop | `http://127.0.0.1:8000` |

Change via `ApiConstants.activeBaseUrl` at runtime.

## Key ADR Implementations

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-001 | Hybrid Backend Architecture | `ApiClient` → Backend Proxy only, no direct TikTok calls |
| ADR-002 | SQLite Persistent Storage | `DatabaseHelper` + `tables.dart` DDL exact spec |
| ADR-005 | Two-Tier Deduplication | `StickerRepository.insertSticker()` Gate 1 (comment_id) + Gate 2 (sha256) |
| ADR-006 | Virtual Pack Partitioning | `PackRepository` supports chunked pack management |
| ADR-007 | Static/Animated Isolation | `PackRepository.getAllPacks(isAnimated:)` filter |
