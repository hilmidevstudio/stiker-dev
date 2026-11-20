# StickerDrop Patch 8 — Installation Guide

## Scope

Adds the operator-managed HTTPS source bridge in `backend/authorized_source_adapter.py`, connects it to the adapter factory/status API, adds offline adapter tests, and documents the HTTP contract.

**This is not a TikTok scraper.** It does not make live TikTok requests, does not enable a source automatically, and does not replace the need for an authorized data-acquisition service.

## Install

1. Extract the Patch 8 ZIP.
2. Copy the `stiker-dev` folder contents over your existing `C:\stiker-dev` project, allowing the listed files to be replaced.
3. Do not overwrite your `.env` file. The patch only updates `.env.example`.
4. Keep the current backend environment setting unchanged:

```dotenv
APP_ENV=production
EXTRACTION_PROVIDER=disabled
```

No Railway environment change is required to install Patch 8.

## Verify

From PowerShell:

```powershell
cd C:\stiker-dev

python -m compileall -q backend scripts tests
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected result:

```text
Tests run: 120
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

The new tests use `httpx.MockTransport`; they do not contact TikTok, a source endpoint, ScrapeCreators, or ScrapeSocial.

## What the adapter expects

A separately deployed and authorized source service must implement:

- `POST /v1/comments`
- `POST /v1/replies`

Both endpoints require the bearer token configured in `AUTHORIZED_SOURCE_API_KEY` and return a normalized page with `comments`, `has_more`, and `cursor`. See `docs/19-authorized-source-http-adapter.md` for the request/response contract.

Only after that service exists, is authorized, and passes a live Golden Reference qualification may the operator configure these backend variables:

```dotenv
EXTRACTION_PROVIDER=authorized_source
AUTHORIZED_SOURCE_BASE_URL=https://your-authorized-source.example.com
AUTHORIZED_SOURCE_API_KEY=<server-to-server-secret>
AUTHORIZED_SOURCE_TIMEOUT_SECONDS=20
AUTHORIZED_SOURCE_MAX_RESPONSE_BYTES=2097152
```

Do not put these values in Flutter, a public repository, or a user-visible setting. `GET /v1/extraction-status` checks local configuration only; it does not ping the source or prove extraction works.

## Acceptance gate still outstanding

Patch 8 only establishes connectivity and contract handling. The source is not considered production-ready until it returns the exact target comment ID and actual `cmt_sticker_struct`, and the media gateway obtains valid original WebP bytes. Run the Patch 7 qualification script with the Golden Reference ID/hash before enabling the provider.
