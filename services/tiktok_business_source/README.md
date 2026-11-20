# StickerDrop TikTok Business Source

A read-only source service that implements StickerDrop's `/v1/comments` and
`/v1/replies` HTTP contract using TikTok API for Business.

## Hard scope limit

TikTok documents this API for comments on an **owned TikTok video** belonging
to the TikTok account that authorized the developer app. It is not a public
comment-search API for arbitrary TikTok URLs. The source accepts canonical
`/video/<id>` URLs only. It does not accept `/photo/<id>` posts.

The API may return `image_url` for a comment that is itself an image. This
service maps that field to StickerDrop's existing `comment_pics` media shape.
It does not claim that `image_url` is the same as TikTok's internal
`cmt_sticker_struct`, and it never fabricates that structure. The existing
StickerDrop media pipeline accepts WebP bytes only; a comment image that is
JPEG/PNG or otherwise not valid WebP will not qualify as an exportable sticker.

## Environment variables

- `TIKTOK_BUSINESS_ACCESS_TOKEN`: short-term account access token.
- `TIKTOK_BUSINESS_ID`: the account `open_id` returned by TikTok's account OAuth flow.
- `STICKERDROP_SOURCE_API_KEY`: strong random secret shared with StickerDrop backend.
- `TIKTOK_BUSINESS_TIMEOUT_SECONDS`: optional, default `20`.

The current implementation expects a valid short-term token supplied through
the environment. TikTok documents a one-day lifetime for this token and a
refresh-token endpoint. Automatic token refresh is not implemented in this
patch; this service is an integration/proof stage, not a hands-off production
OAuth installation.

## Run locally

From this directory:

```powershell
python -m pip install -r requirements.txt
$env:TIKTOK_BUSINESS_ACCESS_TOKEN = "<short-lived-token>"
$env:TIKTOK_BUSINESS_ID = "<open_id>"
$env:STICKERDROP_SOURCE_API_KEY = "<long-random-secret>"
uvicorn app:app --host 127.0.0.1 --port 8001
```

`GET /health` is a public liveness endpoint. `GET /v1/status`, `POST /v1/comments`,
and `POST /v1/replies` require `Authorization: Bearer <STICKERDROP_SOURCE_API_KEY>`.

## StickerDrop backend connection

After the source service has real TikTok authorization and has passed a live
read test on a video owned by that account, set these variables on the
StickerDrop backend deployment:

```env
EXTRACTION_PROVIDER=authorized_source
AUTHORIZED_SOURCE_BASE_URL=https://<this-service-host>
AUTHORIZED_SOURCE_API_KEY=<same-STICKERDROP_SOURCE_API_KEY>
```

Keep `EXTRACTION_PROVIDER=disabled` until the source is configured and tested.
