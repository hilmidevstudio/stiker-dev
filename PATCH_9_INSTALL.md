# StickerDrop Patch 9 — Install Guide

## Included changes

- `scripts/live_source_acceptance.py`: end-to-end Golden Reference acceptance via StickerDrop backend.
- `scripts/live_extraction_test.py`: safe compatibility wrapper; no direct ScrapeCreators/ScrapeSocial calls.
- `scripts/test_server_live.py`: safe local smoke test for health and provider status only.
- `tests/backend/test_live_source_acceptance.py`: offline acceptance tests using `httpx.MockTransport`.
- `docs/20-live-source-acceptance.md`: full procedure and safety details.
- `README.md`: updated operational commands and test count.

## Install

1. Extract the Patch 9 ZIP.
2. Copy the `stiker-dev` folder contents over `C:\stiker-dev`, allowing files to be replaced.
3. Do not overwrite `.env`, local databases, or signing material.
4. Keep `EXTRACTION_PROVIDER=disabled` until a real operator-managed source exists and is authorized. Patch 9 does not require a Railway environment change.

## Verify offline

```powershell
cd C:\stiker-dev
python -m compileall -q backend scripts tests
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected:

```text
Tests run: 137
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

## Safe local backend smoke test

```powershell
python scripts/test_server_live.py
```

This checks only `/health` and `/v1/extraction-status`. It does not send a TikTok URL or invoke any provider.

## Live acceptance (only after an authorized source is deployed)

```powershell
$env:STICKERDROP_BACKEND_URL = "https://web-production-96c4e94f.up.railway.app"
python scripts/live_source_acceptance.py
```

The script refuses to send the extraction request unless the backend reports `authorized_source`, `ready=true`, `external_credit_provider=false`, and `billing_model=operator_managed`. With the current safe setting `EXTRACTION_PROVIDER=disabled`, it stops at preflight without making an extraction-provider request.

See `docs/20-live-source-acceptance.md` for Golden Reference details, custom targets, output reports, and failure codes.
