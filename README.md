# StickerDrop — Research, Reverse Engineering & System Engineering

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
│   ├── extractor_adapter.py            # ScrapeSocial/ScrapeCreators/Mock provider adapters
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
│   └── test/                           # 45 Automated unit and E2E integration tests (100% Pass)
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

## 3. Quickstart & Verification

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

### Run All Unit & Integration Tests (100% Offline / Sandboxed)
```powershell
python scripts/run_tests.py
```

### Run Live End-to-End Extraction Test (Requires API Key)
```powershell
# 1. Set environment variable
$env:SCRAPESOCIAL_API_KEY="your_api_key_here"

# 2. Execute live test harness against target comment 7708394712596972308
python scripts/live_extraction_test.py
```
