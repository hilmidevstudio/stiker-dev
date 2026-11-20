# StickerDrop Independent Extraction Adapter Contract

Status: interface defined; no independent TikTok sticker source is implemented yet.

## Goal

The link resolver, comment-discovery engine, media validator, local library, and WhatsApp export must not depend on a particular scraping vendor. A future data adapter should be replaceable without rewriting those components.

## Current production-safe state

- `EXTRACTION_PROVIDER=disabled` is the default.
- The disabled adapter performs no network request and consumes no third-party credits.
- `POST /v1/resolve-link` continues to resolve TikTok short links and identify the post/comment IDs.
- `POST /v1/resolve-and-extract` returns `503 EXTRACTION_SOURCE_NOT_CONFIGURED` until an adapter is explicitly configured.
- Merely setting `SCRAPECREATORS_API_KEY` or `SCRAPESOCIAL_API_KEY` does not enable a paid provider.
- A paid legacy provider requires explicit `EXTRACTION_PROVIDER=scrapecreators` or `scrapesocial`.

## Required adapter interface

A new adapter implements the `ExtractorAdapter` contract in `backend/extractor_adapter.py`:

```python
class MyAuthorizedAdapter(ExtractorAdapter):
    @property
    def provider_name(self) -> str: ...

    async def fetch_comments(self, video_url: str, cursor=0, count=50) -> dict: ...

    async def fetch_replies(self, comment_id: str, video_url: str, cursor=0) -> dict: ...
```

Each fetch method returns the same normalized page shape:

```json
{
  "comments": [],
  "has_more": false,
  "cursor": null
}
```

- `comments` is a list of normalized comment objects.
- `has_more` indicates whether a next page exists.
- `cursor` is the opaque cursor supplied to the next call. It must be stable and must not repeat forever.
- A page fetch must not fabricate missing comments or stickers.

## Normalized comment contract

The discovery engine currently recognizes comment IDs in `cid`, `id`, or `comment_id`. It can use the following reply preview fields:

```json
{
  "cid": "comment-id",
  "text": "comment text",
  "create_time": 0,
  "digg_count": 0,
  "reply_comment_total": 0,
  "reply_comment": [],
  "user": {
    "uid": "author-id",
    "unique_id": "author-handle",
    "nickname": "display name",
    "avatar_thumb": { "url_list": [] }
  },
  "cmt_sticker_struct": {
    "sticker_id": "sticker-id",
    "sticker_type": 1,
    "static_url": {
      "url_list": ["https://approved-cdn.example/sticker.webp"],
      "width": 458,
      "height": 498
    },
    "animated_url": null
  }
}
```

A real adapter may receive a different raw response. It must map that response into this normalized shape before returning it to the engine. If the source only returns text such as `[Sticker]` and no media object/URL, the adapter must return the comment without `cmt_sticker_struct`; it must not invent a URL.

## Discovery engine behavior

`CommentDiscoveryEngine` is provider-neutral and implements:

1. Top-level comment cursor pagination.
2. Exact comment ID matching.
3. Reply preview matching.
4. Candidate parent collection and prioritization using reply count and matching author hints.
5. Reply-thread cursor pagination for each selected parent.
6. Explicit incomplete-search handling when a cap is reached, a cursor repeats, or a reply lookup errors.

Limits are configured on the server:

- `STICKERDROP_MAX_COMMENT_PAGES` (default 10, hard ceiling 100)
- `STICKERDROP_MAX_REPLY_PARENTS` (default 10, hard ceiling 500)
- `STICKERDROP_MAX_REPLY_PAGES` (default 5, hard ceiling 50)

A search budget is a safety ceiling, not a claim that a target is absent. Reaching a ceiling returns `503 COMMENT_SEARCH_INCOMPLETE`, not `404 COMMENT_NOT_FOUND`.

## Media contract

The adapter returns a candidate HTTPS media URL in `cmt_sticker_struct`. The mobile client now posts that URL to `/v1/media-proxy`. The backend checks the CDN allowlist, revalidates redirects, enforces a byte cap, and verifies RIFF/WebP chunk structure before returning the bytes. The mobile client then runs `WebPInspector` against the actual RIFF/WebP contents. The binary inspection is authoritative for:

- static vs animated WebP;
- frame count and animation duration;
- pixel dimensions;
- file extension and MIME type used for local storage.

Provider `sticker_type`, a `.awebp` URL suffix, or a provider MIME hint are not authoritative. The Naruto Golden Reference has no `ANIM` or `ANMF` chunks and is a static WebP even though the earlier database record was marked animated.

## Security and operational requirements

- Never place a provider key in Flutter, APK assets, or committed source.
- Do not infer/auto-select a paid provider from the presence of an API key.
- Do not log complete TikTok share URLs or signed CDN URLs.
- A new source must be authorized for the intended use and reviewed against platform terms before release.
- Tests must use deterministic fixtures and must verify exact comment IDs and media hashes.
- The first live acceptance test is the Naruto Golden Reference: post `7700924470206156050`, comment `7700946321838818056`, expected media SHA-256 `b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878`.

## What is not implemented yet

This contract does not fetch TikTok data by itself. It does not establish that TikTok exposes an unauthenticated public endpoint for comment sticker media, and it does not bypass platform access controls. A future adapter must provide a documented or otherwise authorized source that includes the exact sticker media object/URL.


## Patch 4 response normalization

The concrete ScrapeSocial and ScrapeCreators adapters pass raw responses through `backend/provider_normalization.py`. Supported top-level/nested envelopes and comment list aliases are converted into the page contract. Unknown payload shapes are returned as `UPSTREAM_INVALID_RESPONSE`, not treated as empty pages. See `docs/17-provider-normalization-and-media-gateway.md`.
