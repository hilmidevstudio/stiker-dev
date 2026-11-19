# Technical Decision Register (ADRs)

## ADR-001: Hybrid Backend-Assisted Architecture vs Local Client Scraping
- **Status**: Accepted
- **Context**: Evaluating whether the mobile application should extract comment stickers directly from TikTok or utilize a backend proxy service.
- **Evidence**:
  1. Direct unauthenticated HTTP requests to `tiktok.com` trigger ByteDance `SlardarWAF` bot-challenges.
  2. Mobile endpoints (`/aweme/v1/comment/list/`) require dynamic cryptographic signing (`X-Gorgon`, `X-Khronos`) which breaks rapidly upon app updates.
  3. Third-party scraping APIs (ScrapeSocial/Apify) require API keys that cannot be securely stored in client APKs without risk of decompilation.
- **Decision**: Adopt a **Hybrid Architecture**:
  - Backend Proxy handles link resolution, scraper orchestration, caching, and API key protection.
  - Client Application handles local storage, offline viewing, and WhatsApp ContentProvider export.
- **Consequences**:
  - *Positive*: High reliability, complete API key protection, dramatic cost reduction via server-side caching of viral stickers.
  - *Negative*: Requires hosting and maintaining a lightweight backend microservice.

---

## ADR-002: SQLite for Persistent Storage Layer
- **Status**: Accepted
- **Context**: Choosing the persistent storage engine for the client library.
- **Alternatives Considered**: Flat JSON files, SharedPreferences / Hive, SQLite.
- **Evidence**:
  - StickerDrop requires relational queries (stickers grouped into packs, filtering by animated status, indexing by SHA-256 and comment ID).
  - Flat JSON files lack atomic ACID transactions and risk data corruption upon application crash.
- **Decision**: Use **SQLite** (via native Android `SQLiteOpenHelper` or `sqflite` in Flutter) with media stored as relative filesystem files.
- **Consequences**:
  - *Positive*: Full ACID compliance, fast indexing on `source_comment_id` and `sha256`, zero risk of corrupted whole-catalog JSON files.
  - *Negative*: Slightly higher setup code than flat JSON.

---

## ADR-003: Bit-Exact Retention of Original AWEBP Media Files
- **Status**: Accepted
- **Context**: Determining whether to convert `.awebp` files into GIF, APNG, or re-encode WebP.
- **Evidence**:
  - Re-encoding animated WebP degrades image quality, strips transparency, increases file size, and introduces CPU latency.
  - WhatsApp natively accepts Animated WebP format up to 500 KB.
  - TikTok `.awebp` files are already Extended WebP (`VP8X`) files with standard `ANMF` frame chunks.
- **Decision**: **Retain original `.awebp` byte-for-byte** whenever file size $\le 500\text{ KB}$ and canvas dimensions meet constraints. Never convert animated stickers to static images.
- **Consequences**:
  - *Positive*: Pristine visual fidelity, 0ms re-encoding latency, minimal CPU usage on mobile devices.
  - *Negative*: Must validate canvas dimensions and pad if non-512×512.

---

## ADR-004: Provider Adapter Pattern for Extraction
- **Status**: Accepted
- **Context**: Choosing how to integrate external scraping APIs.
- **Alternatives Considered**: Hardcoding one service (e.g. ScrapeSocial).
- **Decision**: Implement an **Abstract Base Class `ExtractionProviderAdapter`** supporting multiple interchangeable backends:
  - `ScrapeSocialAdapter`
  - `ScrapeCreatorsAdapter`
  - `ApifyAdapter`
  - `MockExtractionAdapter` (for automated unit and offline testing)
- **Consequences**:
  - *Positive*: High resilience. If ScrapeSocial experiences downtime or price changes, the system can failover to ScrapeCreators or Apify with zero code changes.
  - *Negative*: Requires maintaining interface normalization across provider schemas.

---

## ADR-005: Two-Tier Deduplication Strategy (Comment ID & SHA-256)
- **Status**: Accepted
- **Context**: Preventing duplicate stickers in the user's permanent collection.
- **Decision**: Implement two distinct deduplication gates:
  1. **Gate 1 (`source_comment_id`)**: Rejects duplicate extraction of the exact same TikTok comment.
  2. **Gate 2 (`sha256`)**: Rejects duplicate storage of identical media files shared across different comments or videos.
- **Consequences**:
  - *Positive*: Saves device storage; avoids cluttering user sticker collections.
  - *Negative*: Must handle informative UI messaging when duplicate is detected.

---

## ADR-006: Dynamic Virtual Pack Partitioning (3 to 30 Stickers)
- **Status**: Accepted
- **Context**: Bridging the mismatch between StickerDrop's "single continuous collection" and WhatsApp's "3 to 30 stickers per pack" rule.
- **Decision**: Implement a **Virtual Pack Partitioner** that automatically chunks the continuous collection into discrete WhatsApp packs (e.g. "StickerDrop Pack 1", "StickerDrop Pack 2" with up to 30 stickers each).
- **Consequences**:
  - *Positive*: User never has to manually manage pack bookkeeping; packs are auto-balanced.
  - *Negative*: If user has only 1 or 2 stickers, pack export must wait until 3 stickers are collected.

---

## ADR-007: Strict Separation of Static and Animated WhatsApp Packs
- **Status**: Accepted
- **Context**: WhatsApp Stickers API strictly rejects packs that contain a mixture of static and animated stickers.
- **Decision**: StickerDrop partitions the collection into two separate streams:
  - **Animated Packs** (`is_animated = 1`)
  - **Static Packs** (`is_animated = 0`)
- **Consequences**:
  - *Positive*: 100% compliance with WhatsApp import validation; zero runtime import crashes.
  - *Negative*: User sees two pack categories if they collect both static and animated stickers.

---

## ADR-008: Zero-Dependency Pure-Python WebP/RIFF Binary Parser
- **Status**: Accepted
- **Context**: Inspecting and validating WebP/AWEBP files in Python without native C-library binding dependencies (such as heavy Pillow / libwebp builds).
- **Decision**: Write a lightweight, self-contained binary parser (`src/media/validator.py`) using Python's standard `struct` library to traverse RIFF chunks, read canvas dimensions, verify animation flags, count frames, and calculate duration.
- **Consequences**:
  - *Positive*: Fast, portable, runs anywhere (standard library only), zero build/installation issues.
  - *Negative*: Does not perform pixel re-encoding; separate pipeline handles image resizing if needed.

---

## ADR-009: FastAPI Backend Microservice & Provider Adapter Pattern
- **Status**: Accepted
- **Context**: Exposing the TikTok link resolver, extraction engine, and media validation to external mobile clients (Flutter / Android) without shipping third-party API keys inside the APK.
- **Decision**: Implement an asynchronous **FastAPI backend microservice** under `backend/`:
  - `main.py`: ASGI entry point, CORS middleware, global exception handlers mapping domain exceptions to standard HTTP error codes.
  - `link_resolver.py`: Asynchronous short link resolver and parameter extractor.
  - `extractor_adapter.py`: Provider adapter interface with `.env` secret management, supporting ScrapeSocial, ScrapeCreators, and a deterministic Mock adapter.
  - `schemas.py`: Pydantic v2 schemas providing a clean, client-facing contract for `/v1/resolve-and-extract`.
- **Consequences**:
  - *Positive*: Third-party API keys remain 100% server-side; unified error responses; high-throughput asynchronous execution; instant testing via automatic `/docs` OpenAPI swagger.
  - *Negative*: Adds operational requirement for backend server hosting and deployment.
