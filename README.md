# StickerDrop — Research, Reverse Engineering & System Engineering

> **Current engineering status — Patch 8 (20 Nov 2026):** the backend suite passes **120/120** tests with runtime warnings treated as errors. Patch 8 adds an operator-managed HTTPS source bridge with bearer authentication, bounded JSON responses, redirect rejection, and normalized comment/reply pagination. The bridge is a connector, not a TikTok scraper. No authorized live source has been deployed or qualified against the Golden Reference, so production extraction must remain disabled. This is an engineering foundation, not a public-release build.

StickerDrop is an Android application concept engineered to extract stickers attached to TikTok comments and export them directly into WhatsApp sticker packs.

This repository hosts the **technical validation, reverse engineering, underlying system architecture, data models, processing engine, storage layer, and WhatsApp pack generator** for StickerDrop prior to mobile client development.

---

## 1. Product Principle

$$\text{Copy Link} \longrightarrow \text{Paste} \longrightarrow \text{Extract} \longrightarrow \text{Save (Persistent)} \longrightarrow \text{Export to WhatsApp}$$

- **Zero-Login User Experience**: Does not require users to log into TikTok, provide credentials, or bypass security mechanisms.
- **Single Persistent Collection**: User extracts stickers across arbitrary sessions; stickers accumulate in a local SQLite library.
- **Automated Virtual Pack Generation**: Automatically partitions the persistent library into WhatsApp-compliant packs (3–30 stickers, 512×512 WebP, tray icon).

---

## 2. Directory Structure

```text
c:\stiker-dev\
├── README.md                           # Project overview, test instructions & status
├── .env.example                        # Template for API credentials and test config
├── .gitignore                          # Version control exclusions
│
├── backend/                            # FastAPI Backend Microservice
│   ├── main.py                         # App entry point, CORS & global error handling
│   ├── link_resolver.py                # Asynchronous TikTok short URL cleaner & resolver
│   ├── extractor_adapter.py            # Pluggable adapters; safe default is disabled
│   ├── authorized_source_adapter.py     # Operator-managed HTTPS source bridge
│   ├── comment_discovery.py             # Provider-neutral cursor/reply discovery engine
│   └── schemas.py                      # Pydantic v2 schemas for requests & responses
│
├── docs/                               # Comprehensive Technical Specifications
│   ├── 01-product-requirements.md      # Detailed PRD & system contracts
│   ├── 02-tiktok-link-analysis.md      # Short URL resolution, redirect behavior & schema
│   ├── 03-tiktok-sticker-research.md   # cmt_sticker_struct schema, AWEBP, CDN behavior
│   ├── 04-extraction-provider-comparison.md # Empirical comparison: ScrapeSocial, Apify, TikWM
│   ├── 05-media-processing.md          # WebP/AWEBP validation, RIFF parsing & WhatsApp specs
│   ├── 06-persistent-storage.md        # SQLite schema, deduplication, migrations & integrity
│   ├── 07-whatsapp-integration.md      # WhatsApp ContentProvider specs, pack partitioning
│   ├── 08-system-architecture.md       # Hybrid architecture, threat model & component contracts
│   ├── 09-security-and-privacy.md      # API key protection, copyright & data isolation
│   ├── 10-technical-decisions.md       # Decision Register (ADR 001 - ADR 009)
│   ├── 11-testing-report.md            # Comprehensive test execution & verification report
│   ├── 12-backend-implementation-report.md # Backend Microservice implementation & audit report
│   ├── 13-flutter-client-initialization-report.md # Flutter client initialization report
│   └── 14-ui-and-whatsapp-native-implementation-report.md # UI Layer & WhatsApp Native integration report
│
├── client/                             # Flutter Android Application (com.stickerdrop.app)
│   ├── android/                        # Android Native with WhatsApp ContentProvider & MethodChannel
│   ├── lib/                            # UI Layer (Input, Collection, Export) & Domain Features
│   └── test/                           # Flutter unit/E2E tests; run `flutter test` on the development machine
│
├── research/                           # Research Artifacts & Live Traces
│   ├── api-responses/                  # Raw and sanitized API responses
│   ├── sample-metadata/                # Verified metadata structures
│   ├── source-references.md            # Literature, API docs & reverse-engineering citations
│   └── unresolved-questions.md         # Open questions and tracked investigation items
│
├── src/                                # Core Engine Modules (Production Quality)
│   ├── link_resolver/                  # URL resolution & parameter extraction
│   ├── extraction/                     # Provider adapters (ScrapeSocial, ScrapeCreators, Apify)
│   ├── media/                          # Pure-Python RIFF/WebP parser, validator & processor
│   ├── storage/                        # SQLite storage, repository, deduplication & integrity
│   └── whatsapp_export/                # Virtual pack partitioner, tray icon & manifest generator
│
├── tests/                              # Automated Unit & Integration Test Suites
│   ├── link_resolver/                  # Tests for short URLs, redirects, normalization
│   ├── extraction/                     # Provider adapter tests with fixtures
│   ├── media/                          # WebP parser tests (static, animated, dimensions, limits)
│   ├── storage/                        # SQLite persistence, deduplication, corrupt file checks
│   └── whatsapp_export/                # WhatsApp pack rule validation tests
│
├── samples/                            # Sample inputs & generated output packs
│   ├── input/
│   └── output/
│
└── scripts/                            # Operational & Diagnostic Scripts
    ├── run_tests.py                    # Unified test runner
    └── live_extraction_test.py         # Live end-to-end extraction harness
```

---

## 3. Current extraction safety state

The backend now defaults to `EXTRACTION_PROVIDER=disabled`. This is deliberate: a leftover API key must not silently activate a billable provider. Link resolution remains available at `POST /v1/resolve-link`; sticker extraction returns `503 EXTRACTION_SOURCE_NOT_CONFIGURED` until an authorized adapter is connected. Check `GET /v1/extraction-status` to inspect the current adapter state without making an upstream request.

The provider-neutral `CommentDiscoveryEngine` handles top-level cursor pagination, reply previews, prioritization using comment-author hints, and paginated reply threads. If configured limits are reached, the API returns `503 COMMENT_SEARCH_INCOMPLETE`, not a misleading `404`.

The mobile client inspects the downloaded RIFF/WebP bytes before saving. Static vs animated classification, extension, frame count, duration, and dimensions are derived from the media binary rather than provider metadata.

See `PATCH_3_ENGINE_FOUNDATION.md` and `docs/16-independent-extraction-adapter-contract.md` before deployment or when connecting a future data source.

## 4. Quickstart & Verification

### Run FastAPI Backend Server
```powershell
# Start Uvicorn development server
.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8000 --reload
# Interactive Swagger Documentation: http://localhost:8000/docs
```

### Run Live Server Smoke Test
```powershell
.venv\Scripts\python.exe scripts/test_server_live.py
```

### Run All Python Unit & Integration Tests (offline fixtures)
```powershell
python scripts/run_tests.py
```
The current backend/core suite passes 120 tests. Flutter tests must also be run from `client/` on a machine with the Flutter SDK installed.

### Provider opt-in

Do not run live extraction or set a paid provider unless you intentionally authorize the associated cost. A paid legacy adapter is enabled only by explicitly setting `EXTRACTION_PROVIDER=scrapecreators` or `scrapesocial` on the backend. The default is `disabled`. The future independent adapter must implement the contract in `docs/16-independent-extraction-adapter-contract.md` and must be authorized for the intended use.


## Patch 4 — Provider Normalization & Secure Media Pipeline

See `PATCH_4_PROVIDER_MEDIA_PIPELINE.md` and `docs/17-provider-normalization-and-media-gateway.md`. Patch 4 normalizes upstream comment/reply payloads and fetches sticker WebP through a bounded, allowlisted backend media proxy. It does not add a TikTok scraper or enable paid providers.


## Patch 5 — Test Integrity, Log Hygiene & Safe Source Bundles

Patch 5 fixes async adapter tests so they execute under `unittest.IsolatedAsyncioTestCase`, removes raw URLs and upstream response bodies from normal API errors/logs, and adds a source-bundle script that excludes `.env`, `.git`, virtual environments, generated builds, local databases, and Android signing material. See `PATCH_5_TEST_INTEGRITY_LOG_HYGIENE.md`.


## Patch 6 — Media Gateway Abuse Guards

Patch 6 reuses one media gateway per backend worker, adds a process-local rolling request guard, a concurrency cap, and a bounded in-memory LRU cache. It also removes the general `tiktok.com` website domain from the default media allowlist; only the known CDN roots remain. These are per-worker protections, not a shared per-user quota or a replacement for an edge/WAF rate limiter. Configuration and limitations are documented in `docs/17-provider-normalization-and-media-gateway.md` and `.env.example`.


## Patch 7 — Authorized Source Qualification & Golden Reference Gate

Patch 7 adds `backend/source_qualification.py` and `scripts/qualify_adapter_source.py`. The CLI validates a captured normalized comment response and the exact media bytes without making network requests or spending API credits. It distinguishes a metadata-only source from one that has actually delivered valid WebP bytes. See `docs/18-authorized-source-qualification.md` for documented TikTok Research API limitations, source eligibility, usage, and the Golden Reference procedure. The backend suite now contains 98 tests. This patch does not implement or enable an independent TikTok scraper.


## Patch 8 — Operator-Managed Authorized Source HTTP Adapter

Patch 8 adds `backend/authorized_source_adapter.py`, an HTTP bridge for a separately operated extraction source. It uses backend-only bearer credentials, requires HTTPS in production, disables redirects, bounds response size, and normalizes the two comment/reply endpoints. It does not scrape TikTok or make any provider call during tests. The source service must implement the contract in `docs/19-authorized-source-http-adapter.md` and be authorized for the intended use. Keep `EXTRACTION_PROVIDER=disabled` until a real service is deployed and passes the Patch 7 qualification gate with the Golden Reference. See `PATCH_8_INSTALL.md`.
