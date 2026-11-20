# Patch 9 — Live Source Acceptance Gate

## Purpose

Patch 9 adds an end-to-end acceptance tool for a separately deployed, operator-managed source connected through StickerDrop's existing `authorized_source` adapter. It exercises the production backend path:

1. Backend health check.
2. Provider status preflight.
3. TikTok share-link resolution through `POST /v1/resolve-link`.
4. Exact post/comment ID comparison.
5. Sticker extraction through `POST /v1/resolve-and-extract`.
6. Provider identity and media-host verification.
7. Media download through StickerDrop's `POST /v1/media-proxy`.
8. RIFF/WebP validation, SHA-256 comparison, and reuse of Patch 7's source-qualification gate.

The tool never calls ScrapeCreators, ScrapeSocial, or the source service directly. It only calls the configured StickerDrop backend. The backend's extraction status must explicitly report `provider=authorized_source`, `ready=true`, `external_credit_provider=false`, and `billing_model=operator_managed` before the extraction request is sent. A provider status of `disabled`, `scrapecreators`, `scrapesocial`, `mock`, or anything else is rejected before extraction.

## Golden Reference defaults

- Share link: `https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/`
- Post ID: `7700924470206156050`
- Comment ID: `7700946321838818056`
- Expected media SHA-256: `b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878`

The share URL and signed CDN URL are never printed or included in the JSON report. The report records the backend origin and approved CDN hostname only.

## Run against the backend

PowerShell:

```powershell
cd C:\stiker-dev
$env:STICKERDROP_BACKEND_URL = "https://web-production-96c4e94f.up.railway.app"
python scripts/live_source_acceptance.py
```

To save the media bytes after the entire Golden Reference gate passes:

```powershell
python scripts/live_source_acceptance.py --media-out .\artifacts\golden-sticker.webp
```

The safe JSON report defaults to `artifacts/live-acceptance-report.json`. It contains check results, provider/billing classification, CDN hostname, file size, media metadata, and SHA-256. It does not contain signed URLs, bearer keys, raw upstream payloads, or the share URL.

For another comment, supply all matching identifiers and either the correct expected hash or `none` to skip only the Golden byte hash comparison:

```powershell
python scripts/live_source_acceptance.py `
  --comment-url "https://www.tiktok.com/@creator/video/123?comment_id=456" `
  --expected-post-id 123 `
  --expected-comment-id 456 `
  --expected-sha256 none
```

Local development may use plain HTTP only for localhost when explicitly enabled:

```powershell
python scripts/live_source_acceptance.py `
  --backend-url http://127.0.0.1:8000 `
  --allow-insecure-localhost
```

All non-localhost backend URLs must use HTTPS. Embedded credentials, URL query strings, and fragments in the backend base URL are rejected.

## Safety behavior

- Provider preflight happens before the extraction request. Paid provider names are rejected.
- `provider_called` must be `false` on the status endpoint.
- The extraction response must identify `provider_used=authorized_source` and exactly match the expected post and comment IDs.
- Media URLs are validated locally against the backend media allowlist before the media-proxy request.
- The media response is streamed with a 5,000,000-byte client-side ceiling and must have a WebP content type.
- The actual bytes must pass the WebP parser and Patch 7's qualification check.
- The expected Golden SHA-256 must match by default.
- HTTP redirects are not followed by the acceptance client.
- Error reports use stable issue codes; response bodies and signed URLs are omitted.

The check is an operational safety gate, not a proof of legal authorization. The operator remains responsible for ensuring the source service and data-acquisition path are authorized for the intended use.

## Legacy harness retirement

The previous `scripts/live_extraction_test.py` directly instantiated legacy ScrapeSocial/ScrapeCreators adapters using whichever API key happened to be present. That behavior is retired. The script is now a compatibility wrapper to this acceptance gate and cannot invoke the legacy paid adapters.

The previous `scripts/test_server_live.py` also submitted mock-provider extraction requests and printed media URLs. It is now a local smoke test that checks only `/health` and `/v1/extraction-status`; it makes no TikTok, source-service, or provider requests.

## Test coverage

The new tests use `httpx.MockTransport`; they do not contact TikTok, the configured source service, or any paid provider. They cover:

- Full authorized-source flow and report redaction.
- Disabled, paid, unready, and incorrectly billed provider configurations.
- Exact post/comment ID mismatches.
- Extraction provider and extracted comment mismatches.
- Media host rejection before proxy use.
- Media proxy HTTP failure and malformed WebP bytes.
- Golden SHA mismatch.
- HTTPS-only backend URL validation and explicit localhost exception.

Run the full offline suite:

```powershell
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected result after Patch 9: **137 tests, 0 failures, 0 errors**.

Passing the offline suite tests the acceptance harness, not a live TikTok source. A live result is qualified only when the connected authorized source returns the exact Golden target and original media bytes.
