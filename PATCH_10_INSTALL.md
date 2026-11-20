# StickerDrop Patch 10 — Install Guide

## Contents

- `services/tiktok_business_source/`: separate, read-only service using TikTok API for Business.
- `tests/business_source/`: offline tests for the source microservice.
- `docs/21-tiktok-business-api-source.md`: architecture, scope, setup, and limitations.
- `PATCH_10_TEST_LOG.txt`: reproducible test output.

## Install source files

Extract the ZIP and merge its `stiker-dev` folder into `C:\stiker-dev`. Do not overwrite `.env`, `.git`, signing files, local databases, or Flutter build outputs. This patch is additive.

## Run tests

```powershell
cd C:\stiker-dev
python -m compileall -q backend scripts services tests
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected result:

```text
Tests run: 154
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

## Important: do not enable it blindly

Patch 10 does not include TikTok OAuth approval, an access token, account `open_id`, or a video owned by that account. It also does not establish that TikTok comment stickers are always represented as `image_url` or that the returned media is WebP.

Keep production backend setting:

```env
EXTRACTION_PROVIDER=disabled
```

until an authorized account has completed a live read against one of its own videos and the target comment media has passed StickerDrop's WebP validation.

## Deploy the source service

Deploy `services/tiktok_business_source` as a separate Railway service. Set its root directory to that path, use the included Dockerfile, and configure:

```env
TIKTOK_BUSINESS_ACCESS_TOKEN=<short-lived-account-access-token>
TIKTOK_BUSINESS_ID=<open_id-from-TikTok-OAuth>
STICKERDROP_SOURCE_API_KEY=<strong-random-secret>
```

Test `/health` and authenticated `/v1/status`. The status endpoint does not expose credentials.

After the service is validated, set on the StickerDrop backend:

```env
EXTRACTION_PROVIDER=authorized_source
AUTHORIZED_SOURCE_BASE_URL=https://<source-service-host>
AUTHORIZED_SOURCE_API_KEY=<same-strong-random-secret>
```

The short-term TikTok account access token is documented as valid for one day. Patch 10 does not automatically refresh it; refresh handling is a remaining production task.
