# Backend Implementation Report & Technical Audit Handover

## 1. Document Control
- **Document Version**: 1.0.0
- **Target Audience**: Lead Technical Architect (Gemini / External Auditor)
- **Author**: Senior Backend & Systems Engineer
- **Date**: 2026-11-17
- **Project**: StickerDrop — Core Backend Microservice
- **Status**: Ready for Architectural Review & Security Audit

---

## 2. Objective & Context
In accordance with the project roadmap (ADR-001: Hybrid Backend Architecture), client mobile applications must **never** hold third-party scraping credentials or directly attempt to scrape TikTok due to device-level Web Application Firewall (Slardar WAF) blocks.

This implementation establishes the **StickerDrop Backend Microservice** under the `backend/` directory using **FastAPI (Python)**, providing a secure, high-performance gateway that:
1. Cleans and resolves TikTok short URLs (`vt.tiktok.com`, `vm.tiktok.com`).
2. Dispatches extraction requests to external providers (ScrapeSocial, ScrapeCreators, or local deterministic Mock).
3. Parses raw TikTok `cmt_sticker_struct` into normalized, client-ready JSON payloads.
4. Provides standard CORS and a unified global exception taxonomy.

---

## 3. Implemented File Tree

```text
c:\stiker-dev\
├── backend/
│   ├── __init__.py                 # Package exports
│   ├── main.py                     # FastAPI entry point, CORS middleware, global error handlers, route handlers
│   ├── link_resolver.py            # Async TikTok short link cleaner & parameter extractor
│   ├── extractor_adapter.py        # Abstract adapter interface & concrete providers (ScrapeSocial, ScrapeCreators, Mock)
│   └── schemas.py                  # Pydantic v2 schemas for requests, responses, and error structures
│
├── tests/backend/
│   ├── __init__.py
│   └── test_api.py                 # 9 automated integration & API endpoint tests
│
├── scripts/
│   ├── run_tests.py                # Unified test runner (discovers all 33 system tests)
│   └── test_server_live.py         # Subprocess live Uvicorn startup & smoke test harness
│
└── requirements.txt                # Frozen Python virtual environment dependencies
```

---

## 4. Architectural Component Breakdown

### 4.1 Entry Point & Error Handling (`backend/main.py`)
- **Framework**: FastAPI with asynchronous lifespan event management.
- **CORS Policy**: Configured via `CORSMiddleware` with `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, and `allow_headers=["*"]`. (Note: In compliance with W3C CORS standards, Starlette dynamically mirrors the incoming request `Origin` when credentials are permitted).
- **Global Error Taxonomy**:
  | Exception Class | HTTP Status | Error Code | Description |
  | :--- | :--- | :--- | :--- |
  | `InvalidUrlException` | 400 Bad Request | `INVALID_URL` | Non-URL text or malformed string provided. |
  | `CommentNotFoundException` | 404 Not Found | `COMMENT_NOT_FOUND` | Comment ID not present in video or reply threads. |
  | `StickerNotFoundException` | 404 Not Found | `STICKER_NOT_FOUND` | Comment located, but has no attached sticker. |
  | `MissingCommentIdException` | 422 Unprocessable | `MISSING_COMMENT_ID` | Link is a video link, but contains no comment ID. |
  | `RequestValidationError` | 422 Unprocessable | `VALIDATION_ERROR` | Request payload fails Pydantic validation rules. |
  | `ProviderAuthException` | 500 Server Error | `PROVIDER_AUTH_ERROR` | Missing or invalid API key for external provider. |
  | `ExtractionException` | 502 Bad Gateway | `EXTRACTION_ERROR` | Upstream scraping API failure or network failure. |
  | `Exception` (catch-all) | 500 Server Error | `INTERNAL_SERVER_ERROR` | Unhandled runtime exception; returns clean JSON. |

### 4.2 TikTok Link Resolver (`backend/link_resolver.py`)
- **Conversational Text Stripping**: Regex matches the first valid HTTP/HTTPS URL within conversational copy-paste text.
- **Asynchronous Redirect Tracing**: Uses `httpx.AsyncClient` with a modern browser User-Agent header to follow HTTP `301/302` hops from `vt.tiktok.com` to canonical `www.tiktok.com/@user/video/:video_id`.
- **Parameter Extraction**:
  - `video_id`: Extracted from path `/video/(\d+)` or query params (`share_item_id`, `item_id`).
  - `comment_id`: Extracted from query params (`share_comment_id`, `comment_id`, `cid`).
  - `author_id`: Extracted from query param `comment_author_id`.

### 4.3 Extraction Adapter & Secret Management (`backend/extractor_adapter.py`)
- **Environment Isolation**: API secrets are strictly loaded from `.env` via `python-dotenv`:
  - `SCRAPESOCIAL_API_KEY`, `SCRAPESOCIAL_BASE_URL`
  - `SCRAPECREATORS_API_KEY`, `SCRAPECREATORS_BASE_URL`
  - `EXTRACTION_PROVIDER` (determines active provider: `scrapesocial`, `scrapecreators`, or `mock`)
- **Abstract Base Class `ExtractorAdapter`**: Enforces `fetch_comments()` and `fetch_replies()`.
- **`cmt_sticker_struct` Extraction Logic**:
  - Identifies `sticker_type`: `1` (static) or `2` (animated).
  - Selects highest quality CDN asset: prioritizes `animated_url.url_list[0]` over `static_url.url_list[0]`.
  - Determines format: `.awebp` for animated, `.webp` for static.
  - Extracts width and height constraints.
- **Multi-Tier Search Strategy**:
  1. Searches top-level comments (with cursor pagination up to 5 pages).
  2. If missing, automatically checks comment replies thread via `/v1/tiktok/video/comment/replies`.
- **Deterministic Mock Provider**: Includes verified fixture for the primary test case (`7708394712596972308`, author `@crazyolshop1`, child Prabowo red shirt sticker) allowing 100% offline unit/integration test execution without consuming API quota.

---

## 5. Clean Client API Contracts (`schemas.py`)

### 5.1 Request Contracts
Both `POST` and `GET` are supported at `/v1/resolve-and-extract`:
- **POST**: Body `{"url": "https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/", "provider": "mock"}`
- **GET**: Query `?url=https%3A%2F%2Fvt.tiktok.com%2FZS9f3yqSf57UR-naeU1%2F&provider=mock`

### 5.2 Success Response Schema (HTTP 200)
```json
{
  "success": true,
  "message": "Sticker extracted successfully",
  "video_id": "7708356144804236564",
  "comment_id": "7708394712596972308",
  "canonical_url": "https://www.tiktok.com/@nyariprompt/video/7708356144804236564?share_comment_id=7708394712596972308",
  "comment_text": "ngajak ribut kamu? 🗿",
  "create_time": 1731600000,
  "digg_count": 88,
  "author": {
    "uid": "7435664412436120631",
    "unique_id": "crazyolshop1",
    "nickname": "crazyolshop1",
    "avatar_url": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/7435664412436120631.webp"
  },
  "sticker": {
    "sticker_id": "7421890123456789012",
    "sticker_type": 2,
    "is_animated": true,
    "format": "awebp",
    "media_url": "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/prabowo_animated.awebp",
    "static_url": "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/prabowo_static.webp",
    "animated_url": "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/prabowo_animated.awebp",
    "width": 300,
    "height": 300
  },
  "provider_used": "MockProvider",
  "sha256": null
}
```

### 5.3 Error Response Schema (HTTP 4xx / 5xx)
```json
{
  "success": false,
  "error_code": "MISSING_COMMENT_ID",
  "message": "The link points to a TikTok video, but no comment identifier was found. Please long-press the comment and copy its specific link.",
  "details": {
    "path": "/v1/resolve-and-extract"
  }
}
```

---

## 6. Verification & Test Evidence

### 6.1 Unified Test Suite Execution (`scripts/run_tests.py`)
- **Total Test Cases**: **33** (24 Core Research & Media tests + 9 Backend API tests)
- **Pass Rate**: **100% (33 PASS, 0 FAIL, 0 ERROR)**
- **Execution Time**: **0.45 seconds**

```text
======================================================================
Tests run: 33 | Failures: 0 | Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
======================================================================
```

### 6.2 Live Server Smoke Test Execution (`scripts/test_server_live.py`)
A standalone script launches Uvicorn on port 8000, probes `GET /health`, `POST /v1/resolve-and-extract`, and `GET /v1/resolve-and-extract`, verifies assertions, and terminates the subprocess cleanly:
```text
1. Testing GET /health ...
   -> Status: 200 {'status': 'ok', 'service': 'StickerDrop Backend', 'cors_enabled': True}
2. Testing POST /v1/resolve-and-extract ...
   -> Status: 200 (Extracted Video 7708356144804236564, Comment 7708394712596972308, Format awebp)
3. Testing GET /v1/resolve-and-extract ...
   -> Status: 200 (Success: True)
ALL FASTAPI SERVER ENDPOINTS TESTED SUCCESSFULLY!
```

---

## 7. Decisions for the Lead Technical Architect

The following architectural questions are prepared for Lead Architect audit:

1. **Caching Architecture for Viral Stickers**:
   - *Proposal*: Add a Redis caching middleware keyed by `comment_id`. If multiple users request the same viral sticker, the server returns the cached JSON metadata without invoking ScrapeSocial ($0.001 per call saved).
   - *Decision needed*: Confirm whether Redis or local disk/SQLite caching is preferred for MVP deployment.
2. **Client-to-Backend Authentication**:
   - *Proposal*: Currently the API is public (loginless). To prevent unauthorized third parties from using our backend proxy as a free scraper, should we issue an HMAC app token or dynamic client secret embedded in the mobile build?
3. **Containerization & Deployment Strategy**:
   - *Proposal*: Package `backend/` into a multi-stage `Dockerfile` with Gunicorn + Uvicorn workers and deploy to Cloud Run / Railway / VPS.
   - *Decision needed*: Approve containerization specifications.
