# Patch 8 — Operator-Managed Authorized Source HTTP Adapter

**Status:** implemented and tested with offline HTTP fixtures. It is a transport adapter, not a TikTok scraper. No TikTok requests or provider-credit calls are made by the test suite.

## What Patch 8 adds

`backend/authorized_source_adapter.py` implements the existing `ExtractorAdapter` contract using an operator-managed HTTPS JSON service. It allows StickerDrop to connect a separately operated source without embedding source-acquisition logic in the main application.

The adapter:

- Uses server-to-server `Authorization: Bearer ...` authentication.
- Requires HTTPS in production. Plain HTTP is permitted only for localhost during `APP_ENV=test|development|local`.
- Disables HTTP redirects.
- Applies a configurable timeout and a hard response-size limit (1 KiB–10 MiB; default 2 MiB).
- Does not include request URLs, bearer tokens, or raw upstream bodies in errors.
- Normalizes comment/reply pages through the shared provider normalizer.
- Leaves top-level and reply pagination to `CommentDiscoveryEngine`.
- Does not download sticker media. The existing allowlisted media gateway owns that step and validates the returned CDN URL and WebP bytes.

## Configuration

Set these only on the backend deployment, never in Flutter or a client-visible config:

```dotenv
EXTRACTION_PROVIDER=authorized_source
AUTHORIZED_SOURCE_BASE_URL=https://your-authorized-source.example.com
AUTHORIZED_SOURCE_API_KEY=<server-to-server-secret>
AUTHORIZED_SOURCE_TIMEOUT_SECONDS=20
AUTHORIZED_SOURCE_MAX_RESPONSE_BYTES=2097152
```

The provider is still disabled by default. An API key or base URL alone never enables it. `GET /v1/extraction-status` reports safe configuration status without making a source request. It does not prove that the service is reachable or capable of returning TikTok sticker metadata.

`billing_model=operator_managed` means StickerDrop does not call the built-in ScrapeCreators or ScrapeSocial credit APIs through this adapter. It does **not** guarantee that the operator-managed source has zero hosting, bandwidth, proxy, or other costs.

## Source service contract

The configured service must implement two POST endpoints relative to the base URL.

### `POST /v1/comments`

Request:

```json
{
  "video_url": "https://www.tiktok.com/@creator/video/123",
  "cursor": 0,
  "count": 50
}
```

Response:

```json
{
  "comments": [
    {
      "cid": "exact-comment-id",
      "text": "[Sticker]",
      "create_time": 1731600000,
      "digg_count": 12,
      "reply_comment_total": 0,
      "user": {
        "uid": "author-id",
        "unique_id": "creator",
        "nickname": "Creator"
      },
      "cmt_sticker_struct": {
        "sticker_id": "real-sticker-id",
        "sticker_type": 1,
        "static_url": {
          "url_list": ["https://approved-tiktok-cdn-host.example/sticker.webp"],
          "width": 512,
          "height": 512
        }
      }
    }
  ],
  "has_more": true,
  "cursor": "opaque-next-cursor"
}
```

### `POST /v1/replies`

Request:

```json
{
  "comment_id": "parent-comment-id",
  "video_url": "https://www.tiktok.com/@creator/video/123",
  "cursor": 0
}
```

Response uses the same page shape as `/v1/comments`.

Requirements:

- Send the exact original comment IDs and preserve opaque cursor values.
- Return an empty `comments` array only when the page is genuinely empty.
- Set `has_more` and `cursor` accurately. Never report an incomplete search as a completed empty page.
- Include the actual `cmt_sticker_struct` when the target comment has a sticker. A textual `[Sticker]` marker is insufficient.
- Return the original media URL inside the sticker struct. Do not fabricate a media URL or replace the original asset with a screenshot/placeholder.
- Use only a data acquisition path authorized for the intended use. The bridge cannot grant permission to scrape TikTok or access private endpoints.
- Ensure your source service does not log bearer tokens, full TikTok share URLs, or signed media URLs.

## Security behavior

The base URL and API secret are backend environment settings. The app user cannot override the source URL, path, authentication headers, or provider selection. Redirect responses are rejected rather than followed, preventing the bearer token from being forwarded to a redirect destination. The response body is streamed into a bounded buffer before JSON parsing.

The media gateway independently validates media URLs against its CDN allowlist. A valid comment response does not bypass that media-host check.

## Verification

Run:

```powershell
python -W error::RuntimeWarning scripts/run_tests.py
```

Tests use `httpx.MockTransport` and do not contact the configured source. They cover comment/reply requests, bearer authentication, normalization, pagination cursors, redirects, auth errors, rate limiting, malformed JSON, unexpected content types, body-size limits, timeouts, URL configuration validation, factory opt-in, and safe status reporting.

Passing these tests verifies the adapter bridge. It does not establish that any configured service is authorized, live, or capable of returning the Golden Reference sticker. Keep `EXTRACTION_PROVIDER=disabled` until a real source is deployed and passes Patch 7 qualification against the exact target comment and WebP bytes.
