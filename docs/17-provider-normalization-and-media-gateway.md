# Provider Normalization & Media Gateway (Patch 4)

## Data path

```text
Provider wire response
        |
        v
normalize_provider_page()
        |  comments / has_more / cursor
        v
CommentDiscoveryEngine
        | exact comment ID
        v
ExtractorAdapter.parse_sticker()
        | HTTPS candidate URL
        v
Flutter POST /v1/media-proxy {url}
        |
        v
MediaGateway: allowlist -> redirect checks -> byte limit -> WebP container validation
        |
        v
Flutter WebPInspector -> SHA-256 storage -> WhatsApp pack
```

## Normalization policy

Accepted wrappers: `data`, `result`, `response` (up to three levels). Accepted comment list keys: `comments`, `comment_list`, `reply_list`, `replies`, `items`. Accepted pagination keys: `has_more`, `hasMore`, `has_more_pages`, `hasMorePages`, plus `cursor`, `next_cursor`, `nextCursor`, `cursor_next`, `cursorNext`.

If pagination metadata is unrecognized and no cursor is present, the normalizer fails with `UPSTREAM_INVALID_RESPONSE`. This avoids turning a provider schema change into a false “comment not found”. It normalizes known comment/author aliases while preserving raw fields, including `cmt_sticker_struct`.

## Media gateway security

`POST /v1/media-proxy` accepts the CDN URL in a JSON body rather than a query string. This keeps signed URL parameters out of ordinary access-log request lines. Only HTTPS hosts that exactly match or are subdomains of an allowlisted root are accepted. IP literals, embedded credentials, non-443 ports, and redirect destinations outside the allowlist are rejected. Redirects are limited to three.

Default allowed roots are TikTok/ByteDance CDN roots (`tiktokcdn.com`, `tiktokcdn-us.com`, `tiktokcdn-eu.com`, `tiktokcdn-uk.com`, `byteoversea.com`, `ibytedtos.com`, `byteimg.com`, and `tiktok.com`). `STICKERDROP_MEDIA_ALLOWED_HOSTS` may add comma- or semicolon-separated exact CDN roots. It does not replace the defaults. Never use wildcard matching.

`STICKERDROP_MEDIA_MAX_BYTES` defaults to 2,000,000 bytes and cannot exceed a hard ceiling of 5,000,000 bytes. The gateway requires a WebP RIFF container, valid declared container length, valid chunk boundaries, recognized image payload, and consistent animation flags/chunks. Flutter independently inspects the returned bytes before local storage.

## Limitations

- The proxy does not locate comments and does not scrape TikTok. It only downloads a URL already returned by a configured adapter.
- The proxy does not cache files or provide durable backend media storage. The client stores validated bytes locally and uses SHA-256 deduplication.
- A CDN not on the allowlist must be reviewed before adding.
- The endpoint does not authenticate a user session; keep byte limits and host allowlists strict and monitor usage in production. Consider adding an app/user authentication and rate-limit layer before broad public launch.
- A real adapter must be authorized for its intended use and must provide an exact comment match plus the real sticker media object/URL.
