# StickerDrop Patch 6 — Media Gateway Abuse Guards

**Status:** Implemented and backend-tested  
**Baseline:** Patch 5 already applied  
**Python tests:** 89 passed, 0 failures, 0 errors (`RuntimeWarning` treated as error)  
**Flutter source changes:** None

## Scope

Patch 6 hardens the existing `POST /v1/media-proxy` endpoint. It does not implement a TikTok scraper, change comment discovery, enable an extraction provider, or alter the Flutter client contract.

### 1. Reuse one gateway per backend worker

`backend.main` now keeps one `MediaGateway` instance. Previously, constructing a fresh instance for every request would have reset any in-memory safety controls and cache.

### 2. Process-local request and concurrency guards

Default values:

| Setting | Default | Accepted range |
|---|---:|---:|
| `STICKERDROP_MEDIA_MAX_REQUESTS_PER_MINUTE` | 120 | 10–10,000 |
| `STICKERDROP_MEDIA_MAX_CONCURRENT` | 6 | 1–32 |

The request guard uses a rolling 60-second window per process. When the budget is exhausted it returns `429 MEDIA_RATE_LIMITED` with `Retry-After: 60`.

The concurrency guard allows no more than the configured number of upstream downloads at once. If a slot is not available within 100 ms, it returns `503 MEDIA_GATEWAY_BUSY` with `Retry-After: 1`.

**Important limitation:** these are per-process circuit breakers, not per-user quotas and not distributed limits. If the service runs multiple Railway replicas or worker processes, each has its own budget. At broader public scale, add an edge/WAF or shared rate-limit store.

### 3. Bounded in-memory cache

| Setting | Default | Accepted range |
|---|---:|---:|
| `STICKERDROP_MEDIA_CACHE_TTL_SECONDS` | 300 seconds | 0–3,600; 0 disables TTL cache |
| `STICKERDROP_MEDIA_CACHE_MAX_BYTES` | 16 MiB | 0–64 MiB; 0 disables cache |

The cache is LRU and bounded by total payload bytes. Keys are SHA-256 hashes of normalized media URLs, not raw signed URLs. Only media that has passed the WebP validation is inserted. Cache is per process and clears on restart.

### 4. Tighter media hostname allowlist

The general `tiktok.com` website domain was removed from default media hosts. Default roots now cover the observed TikTok/ByteDance CDN families:

- `tiktokcdn.com`
- `tiktokcdn-us.com`
- `tiktokcdn-eu.com`
- `tiktokcdn-uk.com`
- `byteoversea.com`
- `ibytedtos.com`
- `byteimg.com`

A new CDN root must be reviewed and added explicitly through `STICKERDROP_MEDIA_ALLOWED_HOSTS`. Do not add wildcards or the general TikTok website domain merely to make a failing URL pass.

### 5. Input and redirect bounds

Media URL strings are capped at 4,096 characters. The redirect count constructor accepts 0–5 and remains at 3 by default. HTTPS, CDN allowlist, no IP literals, no embedded credentials, port 443 only, response size, MIME hint, RIFF boundaries, and WebP frame consistency remain enforced.

## Apply

1. Back up `C:\stiker-dev`.
2. Extract the Patch 6 ZIP to a temporary directory.
3. Merge the `stiker-dev` folder from the extracted ZIP into `C:\stiker-dev`, replacing only matching source files. Do **not** overwrite your actual `.env`, Android signing files, or local database.
4. From PowerShell:

```powershell
cd C:\stiker-dev
python -m compileall -q backend scripts tests
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected result:

```text
Tests run: 89
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

5. Commit and push the updated project to the branch connected to Railway. Redeploy after the test run succeeds.

## Railway configuration

The defaults work without adding environment variables. To make the deployment explicit, set:

```text
STICKERDROP_MEDIA_MAX_BYTES=2000000
STICKERDROP_MEDIA_MAX_REQUESTS_PER_MINUTE=120
STICKERDROP_MEDIA_MAX_CONCURRENT=6
STICKERDROP_MEDIA_CACHE_TTL_SECONDS=300
STICKERDROP_MEDIA_CACHE_MAX_BYTES=16777216
```

Keep the existing safe extraction configuration unchanged:

```text
APP_ENV=production
EXTRACTION_PROVIDER=disabled
```

Do not re-enable ScrapeCreators or ScrapeSocial just to test the media gateway. The paid-provider state and the independent adapter remain unchanged.

## Deployment smoke checks

- `GET /health` must return `200`.
- `GET /v1/extraction-status` must continue to report `provider=disabled`, `ready=false`, and `external_credit_provider=false` while no authorized source is connected.
- A `POST /v1/media-proxy` attempt using `https://attacker.example/sticker.webp` must return `403 MEDIA_URL_NOT_ALLOWED` without making an upstream request.
- A genuine sticker CDN URL from an authorized adapter must still pass the allowlist and WebP checks. Do not use a fabricated media URL as proof of live extraction.

## What this patch does not prove

- It does not provide a distributed per-user rate limit.
- It does not replace a WAF/DDoS layer.
- It does not make the proxy a trusted authentication boundary.
- It does not implement the independent TikTok comment/sticker data source.
- It does not prove end-to-end live extraction until a valid adapter and genuine media URL are connected.
