# StickerDrop Patch 4 — Provider Normalization & Secure Media Pipeline

**Purpose:** make the existing adapter contract usable with real provider response envelopes and move sticker-byte downloading behind a bounded backend media gateway. This patch does **not** implement or claim an independent TikTok scraper.

## What changed

1. `backend/provider_normalization.py` maps common provider response envelopes (`data`, `result`, `response`) and comment collection aliases (`comments`, `comment_list`, `reply_list`, `replies`, `items`) into the exact `comments / has_more / cursor` contract used by `CommentDiscoveryEngine`.
2. Both `ScrapeSocialAdapter` and `ScrapeCreatorsAdapter` now normalize their raw comment and reply responses before the discovery engine sees them.
3. Unrecognized or malformed response shapes raise `UPSTREAM_INVALID_RESPONSE` (HTTP 502). They are never silently treated as an empty page, preventing false `COMMENT_NOT_FOUND` results.
4. Common source fields are normalized: `id` / `comment_id` to `cid`, `reply_count` to `reply_comment_total`, and author display/user aliases to `user`. Unknown fields such as `cmt_sticker_struct` are preserved.
5. New `POST /v1/media-proxy` fetches a media URL only when its HTTPS host matches the approved CDN suffix allowlist. Redirect destinations are revalidated, redirects are capped, and non-standard ports/IP literal hosts are rejected.
6. Media download is bounded by a configurable byte limit (default 2,000,000 bytes, hard maximum 5,000,000), has a timeout, and validates RIFF/WebP chunk structure before returning bytes.
7. Flutter now sends the signed CDN URL to `/v1/media-proxy` in a POST JSON body. The signed URL no longer appears in the request path/query string. The client still performs its own WebP inspection before storage.
8. Request-validation logs now omit input values, which can include signed CDN URLs. The backend version is `1.2.0`.

## Verification in the build environment

```text
Python suite: 74 tests
Failures: 0
Errors: 0
Python bytecode compilation: passed
```

Flutter/Dart SDK is not installed in the build environment. The edited Flutter client and E2E test must be verified on the Windows development machine.

## Important boundaries

- `EXTRACTION_PROVIDER` remains `disabled` by default. Do not turn on ScrapeCreators or ScrapeSocial unless you explicitly accept their credit costs.
- The media proxy is not a scraper. It only retrieves an HTTPS WebP URL after a real adapter has supplied it.
- Default CDN allowlist includes TikTok/ByteDance media domains used by known TikTok CDN URLs. If a legitimate authorized source uses a different CDN root, add that root with `STICKERDROP_MEDIA_ALLOWED_HOSTS`; do not use `*` or broad unrestricted host matching.
- Research API comment metadata does not include a comment-sticker asset URL. The app still requires a real source that returns the exact target comment and sticker media object.
- The Golden Naruto reference remains the first media acceptance fixture: SHA-256 `b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878`. Patch 4 has not downloaded that live asset and makes no claim that the end-to-end TikTok extraction gate has passed.

## Apply on Windows

1. Back up `C:\stiker-dev`. Close the Flutter app first. Keep `.git`, `.env`, keystores, and signing files.
2. Extract this ZIP and merge the contents of `stiker-dev-main` into `C:\stiker-dev`, replacing matching source files.
3. Run the backend tests from the project root:

```powershell
cd C:\stiker-dev
python -m pip install -r requirements.txt
python scripts/run_tests.py
```

Expected: 74 tests, 0 failures, 0 errors.

4. Verify Python compilation:

```powershell
python -m compileall backend
```

5. Verify Flutter on Windows:

```powershell
cd C:\stiker-dev\client
dart format lib/features/extraction/services/extraction_service.dart test/integration/e2e_extraction_to_whatsapp_test.dart
flutter clean
flutter pub get
flutter analyze
flutter test
```

Expected analyzer result: `No issues found!`. The existing Flutter suite should retain its current passing tests; the E2E media step now expects a POST to `/v1/media-proxy`.

## Railway configuration

Keep the existing safe extraction state:

```text
APP_ENV=production
EXTRACTION_PROVIDER=disabled
STICKERDROP_MAX_COMMENT_PAGES=10
STICKERDROP_MAX_REPLY_PARENTS=10
STICKERDROP_MAX_REPLY_PAGES=5
STICKERDROP_MEDIA_MAX_BYTES=2000000
```

`STICKERDROP_MEDIA_ALLOWED_HOSTS` is optional. Add only an exact additional CDN root domain when a real authorized provider requires it. Do not add a wildcard. Keep the start command:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Commit and push the merged source to the GitHub branch connected to Railway, then deploy. Verify `/health`, `/v1/extraction-status`, and the API documentation at `/docs`. Extraction status should still report `provider=disabled`; `/v1/resolve-and-extract` should still fail closed with `503 EXTRACTION_SOURCE_NOT_CONFIGURED`.

## Release gate

Patch 4 improves the transport and media pipeline, not TikTok data acquisition. Do not distribute a public APK until a permitted live adapter has returned the Golden Naruto comment, its downloaded bytes match the exact SHA-256, multiple other link cases pass, and WhatsApp device export is verified.
