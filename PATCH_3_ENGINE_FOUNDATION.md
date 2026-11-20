# StickerDrop Patch 3 — Extraction Engine Foundation

**Purpose:** stabilize the backend/client pipeline before implementing or connecting an independent, authorized TikTok data adapter. This patch does not claim that live TikTok sticker extraction is complete.

## What changed

1. `EXTRACTION_PROVIDER` now defaults to `disabled`. An API key present in Railway no longer silently activates ScrapeCreators or ScrapeSocial.
2. `GET /v1/extraction-status` reports the configured provider, readiness, and whether an external-credit provider is selected. It makes no provider request and reveals no secret.
3. `POST /v1/resolve-and-extract` returns `503 EXTRACTION_SOURCE_NOT_CONFIGURED` when disabled. It does not make an extraction-provider request.
4. A provider-neutral `CommentDiscoveryEngine` now traverses top-level cursor pages, checks reply previews, prioritizes parent threads using reply counts and author hints, and paginates replies.
5. A bounded/incomplete search is reported as `503 COMMENT_SEARCH_INCOMPLETE`, not incorrectly as `404 COMMENT_NOT_FOUND`.
6. Mock extraction is accepted only when `APP_ENV=test`, `development`, or `local`.
7. The Flutter client now inspects the actual RIFF/WebP bytes before saving. Static/animated classification, extension, dimensions, frame count, and duration come from the file, not provider metadata.
8. Python WebP parsing validates the RIFF size, chunk boundaries, and consistency of VP8X/ANIM/ANMF animation signals.
9. HTTPX INFO request logging is suppressed so full TikTok share URLs and their query parameters are not written into Railway logs.

## Verification completed in the build environment

```text
Python suite: 55 tests
Failures: 0
Errors: 0
```

The build environment does not have Flutter/Dart installed. The new Dart inspector tests and Flutter changes must be verified on the Windows development computer with the Flutter SDK.

## Step 1 — Back up the working folder

Close the running Flutter application and create a backup of `C:\stiker-dev` first. Do not overwrite or delete `.git`, your local `.env`, signing files, or keystores.

## Step 2 — Apply the source

Extract `StickerDrop_Patch_3_Extraction_Engine_Foundation.zip`. Copy the contents of its `stiker-dev-main` folder into `C:\stiker-dev`, merging folders and replacing source files. The archive intentionally does not contain `.env`, `.git`, `key.properties`, or a keystore.

## Step 3 — Verify Python/backend locally

From PowerShell:

```powershell
cd C:\stiker-dev
python -m pip install -r requirements.txt
python scripts/run_tests.py
```

Expected:

```text
Tests run: 55
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

## Step 4 — Make Railway safe before deploying

In Railway → StickerDrop backend service → Variables:

```text
APP_ENV=production
EXTRACTION_PROVIDER=disabled
STICKERDROP_MAX_COMMENT_PAGES=10
STICKERDROP_MAX_REPLY_PARENTS=10
STICKERDROP_MAX_REPLY_PAGES=5
```

Remove `SCRAPECREATORS_API_KEY` and `SCRAPESOCIAL_API_KEY` from the service if you do not need the legacy paid adapters. Even if an API key remains, `EXTRACTION_PROVIDER=disabled` prevents automatic activation; deleting unused keys is an extra safeguard.

Do not set `EXTRACTION_PROVIDER=scrapecreators` during this phase. That explicitly re-enables a provider that may consume credits. The mock adapter is restricted to `APP_ENV=test`, `development`, or `local`; do not run the mock adapter in production.

Keep the backend start command:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Commit/push the merged source to the repository connected to Railway, then deploy the backend service.

## Step 5 — Verify deployment without provider credits

Open:

- `https://YOUR-RAILWAY-DOMAIN/health`
- `https://YOUR-RAILWAY-DOMAIN/v1/extraction-status`

Expected extraction status:

```json
{
  "provider": "disabled",
  "configured": false,
  "ready": false,
  "provider_called": false,
  "external_credit_provider": false
}
```

Test `POST /v1/resolve-link` with the known TikTok comment links. It should continue to resolve post/comment IDs and report `provider_called: false`.

**Expected while no extraction source is connected:** `POST /v1/resolve-and-extract` returns HTTP 503 with `EXTRACTION_SOURCE_NOT_CONFIGURED`. This is intentional and protects your credits. It does not mean the link resolver is broken.

## Step 6 — Verify Flutter on Windows

From PowerShell:

```powershell
cd C:\stiker-dev\client

dart format lib/features/extraction/services/webp_inspector.dart lib/features/extraction/services/extraction_service.dart lib/ui/screens/input_screen.dart test/features/extraction/webp_inspector_test.dart test/integration/e2e_extraction_to_whatsapp_test.dart
flutter clean
flutter pub get
flutter analyze
flutter test
```

Expected analyzer result: `No issues found!`.

The new WebP inspector test file adds four tests. The full Flutter suite should therefore be at least four tests higher than the previous 45-test result, assuming the rest of the local suite is unchanged. Use the actual result from your computer as the verification record.

Build a debug APK for safe on-device verification (the same debug signing certificate must be used to update the installed debug APK):

```powershell
flutter build apk --debug
adb install -r .\build\app\outputs\flutter-apk\app-debug.apk
```

Do not uninstall the existing app or clear its storage. The patch does not need to alter the database schema.

## Step 7 — Future adapter connection

The next source implementation only needs to satisfy `ExtractorAdapter` and return normalized comment pages. See `docs/16-independent-extraction-adapter-contract.md`.

The independent adapter must supply the exact comment ID and a real sticker media object/URL. If the source only returns `[Sticker]` with no media URL, it is not sufficient. The Golden Reference acceptance case is:

- Post ID: `7700924470206156050`
- Comment ID: `7700946321838818056`
- Expected SHA-256: `b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878`

Do not claim the adapter is ready until the returned media downloads and its SHA-256 matches the reference, then verify multiple independent comment links.

## Release gate

This patch is an engine foundation, not a public release. Do not distribute an APK to users while `EXTRACTION_PROVIDER=disabled`; the Extract action will correctly report that no source is connected. Public release requires a working authorized adapter, live extraction tests, media tests, WhatsApp device tests, and production signing.
