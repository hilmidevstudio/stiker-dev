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

Default allowed roots are TikTok/ByteDance CDN roots (`tiktokcdn.com`, `tiktokcdn-us.com`, `tiktokcdn-eu.com`, `tiktokcdn-uk.com`, `byteoversea.com`, `ibytedtos.com`, and `byteimg.com`). The general `tiktok.com` website root is intentionally excluded. `STICKERDROP_MEDIA_ALLOWED_HOSTS` may add comma- or semicolon-separated exact CDN roots. It does not replace the defaults. Never use wildcard matching.

`STICKERDROP_MEDIA_MAX_BYTES` defaults to 2,000,000 bytes and cannot exceed a hard ceiling of 5,000,000 bytes. The gateway requires a WebP RIFF container, valid declared container length, valid chunk boundaries, recognized image payload, and consistent animation flags/chunks. Flutter independently inspects the returned bytes before local storage.

### Public-use resource guards (Patch 6)

The FastAPI worker reuses one `MediaGateway` instance. By default it allows at most 120 proxy calls per rolling minute and 6 simultaneous upstream downloads per process. If all concurrent slots are occupied for more than 100 ms, a new upstream request receives `503 MEDIA_GATEWAY_BUSY`; the rolling-window guard returns `429 MEDIA_RATE_LIMITED`. These are **process-local circuit breakers**, not individual-user quotas. They prevent unbounded upstream concurrency in a single worker but do not provide fair per-user limits or shared quotas across multiple Railway replicas. A multi-replica public deployment still needs an edge/WAF or shared rate-limit store.

A small in-memory LRU cache defaults to a 300-second TTL and a 16 MiB total payload budget. Cache keys are SHA-256 hashes of normalized URLs; the signed CDN URL itself is not stored as the cache key. Cached data is still validated before its first insertion. All cache entries expire or are evicted when the memory budget is reached. The cache is per worker and is cleared on process restart.

Settings:

- `STICKERDROP_MEDIA_MAX_REQUESTS_PER_MINUTE=120` (10–10,000)
- `STICKERDROP_MEDIA_MAX_CONCURRENT=6` (1–32)
- `STICKERDROP_MEDIA_CACHE_TTL_SECONDS=300` (0 disables TTL cache; maximum 3,600)
- `STICKERDROP_MEDIA_CACHE_MAX_BYTES=16777216` (0 disables cache; maximum 64 MiB)

The gateway rejects URL strings longer than 4,096 characters and caps redirect count at five (default three). These controls reduce accidental or opportunistic resource abuse; they do not replace a production DDoS/WAF layer.

## Limitations

- The proxy does not locate comments and does not scrape TikTok. It only downloads a URL already returned by a configured adapter.
- The proxy does not cache files or provide durable backend media storage. The client stores validated bytes locally and uses SHA-256 deduplication.
- A CDN not on the allowlist must be reviewed before adding.
- The endpoint does not authenticate a user session; keep byte limits and host allowlists strict and monitor usage in production. Consider adding an app/user authentication and rate-limit layer before broad public launch.
- A real adapter must be authorized for its intended use and must provide an exact comment match plus the real sticker media object/URL.
