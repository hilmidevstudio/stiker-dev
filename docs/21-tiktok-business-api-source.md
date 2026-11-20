# Patch 10 — TikTok Business API Owned-Video Source

## 1. Why this patch exists

Patch 9 returned `AUTHORIZED_SOURCE_NOT_SELECTED` because the production backend
was correctly left in its fail-closed `disabled` state. The backend has an
HTTP source contract, but no live source service had been configured.

Patch 10 adds an operator-managed source microservice using TikTok's documented
TikTok API for Business comments endpoints. It is a legitimate, scoped source
for content the connected TikTok account owns.

## 2. Official API boundary

TikTok documents `GET /open_api/v1.3/business/comment/list/` for comments on an
owned video. Its required inputs include `business_id` and `video_id`, with
cursor pagination and a maximum page size of 30. The API's `business_id` is the
`open_id` returned by the TikTok account token flow. The documented response may
include `image_url` when a comment is an image.

The related replies endpoint is
`GET /open_api/v1.3/business/comment/reply/list/`, scoped to a comment on an
owned video and paginated by cursor.

The Research API is not a substitute for sticker media: its documented comment
object exposes IDs, text, video ID, parent ID, likes/reply counts, create time,
and display name, not a comment image URL or sticker media object.

## 3. Service behavior

Location: `services/tiktok_business_source/`

Endpoints:

- `GET /health` — basic liveness only.
- `GET /v1/status` — authenticated, non-secret config status.
- `POST /v1/comments` — fetch one official comment page for the video ID in `video_url`.
- `POST /v1/replies` — fetch one official reply page for an exact parent comment ID.

The service:

- uses the fixed TikTok Business API host over HTTPS;
- uses `Access-Token` only on server-side requests;
- uses a separate Bearer key between StickerDrop backend and this source service;
- rejects non-canonical URLs and non-video paths;
- limits official API page sizes to 30;
- disables redirects and caps upstream JSON responses at 2 MiB;
- sanitizes upstream errors and never returns the access token;
- maps `image_url` to `comment_pics` while preserving `source_media_kind=comment_image`;
- does not create or pretend to have `cmt_sticker_struct` when the official API has not returned it.

## 4. What this does not prove

This does **not** turn StickerDrop into a universal public TikTok comment scraper.

A TikTok video must belong to the TikTok account that authorized the app. A
random public share URL from another creator is outside this official endpoint's
scope. The connector currently rejects `/photo/<id>` routes because the official
comments endpoint is documented for owned videos.

`image_url` means an image comment in the official API. TikTok's documentation
does not state that every comment sticker will be represented there, nor that
all returned images are WebP. StickerDrop's current media validation/export
pipeline requires valid WebP bytes. We must test this on a real sticker-bearing
comment on an owned video before treating this source as accepted.

The service uses a short-term TikTok account access token supplied by the
operator. TikTok's Business API authentication documentation states that this
token is valid for one day and can be renewed using
`/tt_user/oauth2/refresh_token/`. Automatic refresh and OAuth onboarding are
not included in Patch 10.

## 5. Required TikTok setup

1. Register a developer app in TikTok for Business.
2. Configure TikTok account-holder authorization and the public redirect URL.
3. Request the read permission for comments (`comment.list`) and any account/video
   scopes needed by the app workflow.
4. Have the TikTok account owner authorize the app.
5. Obtain the current account access token and the `open_id`; use the latter as
   `TIKTOK_BUSINESS_ID`.
6. Choose a public video actually owned by that connected account and confirm it
   has a comment containing an image/sticker.

The authorization flow and permission approval are controlled by TikTok. Code
in this patch does not manufacture credentials or bypass app review.

## 6. Environment and deployment

Deploy the `services/tiktok_business_source` directory as a separate Railway
service. Use its Dockerfile or run command:

```sh
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Set service variables:

```env
TIKTOK_BUSINESS_ACCESS_TOKEN=<short-lived-account-access-token>
TIKTOK_BUSINESS_ID=<open_id>
STICKERDROP_SOURCE_API_KEY=<strong-random-secret>
```

Set `STICKERDROP_SOURCE_API_KEY` to the same value on the StickerDrop backend as
`AUTHORIZED_SOURCE_API_KEY`. After `/v1/status` reports ready and a real owned-
video source read has succeeded, configure the StickerDrop backend:

```env
EXTRACTION_PROVIDER=authorized_source
AUTHORIZED_SOURCE_BASE_URL=https://<railway-source-host>
AUTHORIZED_SOURCE_API_KEY=<same-strong-random-secret>
```

Do not enable the provider until those conditions are met. This service is a
proof/integration stage while automatic token refresh is still absent.

## 7. Test status

Patch 10 tests use `httpx.MockTransport`; no live TikTok API call is made during
the automated suite. The tests validate authentication, URL ownership scope,
request parameters, pagination, image mapping, replies, sanitization, redirects,
invalid responses, and upstream rate limiting.

A successful mock test is not a live-source acceptance. Live acceptance still
requires an authorized account, an owned video, a target comment, and real media
bytes that pass the WebP and SHA-256 checks.
