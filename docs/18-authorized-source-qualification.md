# Patch 7 — Authorized Source Qualification & Golden Reference Gate

**Status:** implemented as an offline qualification tool. No new TikTok scraper or network adapter is enabled.

## Why this patch exists

The current adapter interface can connect a source, but an interface alone does not prove that the source can extract TikTok comment stickers. A source that returns ordinary comment text, IDs, and reply counts is not sufficient. StickerDrop needs all of the following for the exact target comment:

1. The exact `comment_id` from the shared TikTok link.
2. A real `cmt_sticker_struct` object.
3. An actual HTTPS CDN URL inside that object, on an approved media host.
4. The exact downloaded bytes, passing the RIFF/WebP parser.
5. A matching SHA-256 when a known reference hash is supplied.

Patch 7 adds `backend/source_qualification.py` and `scripts/qualify_adapter_source.py` to check those requirements against a captured JSON response and media file. It runs offline: no TikTok requests, provider requests, account cookies, or API credits are used. Signed CDN URL query parameters are never included in the report.

## Important source research result (20 Nov 2026)

TikTok's documented Research API comment endpoint is:

`POST https://open.tiktokapis.com/v2/research/video/comment/list/`

It requires the `research.data.basic` scope and a client access token. The documented comment fields are `id`, `video_id`, `text`, `like_count`, `reply_count`, `parent_comment_id`, and `create_time`. The response schema does **not** document `cmt_sticker_struct`, sticker IDs, or sticker-media URLs.

TikTok describes Research Tools as access for independent and academic researchers conducting non-profit research. Its Research API FAQ explicitly says creators, advertisers, and commercial users are not eligible for Research Tools. A normal developer account by itself does not grant access; applicants must meet eligibility criteria, apply, and be approved for a project.

Therefore the Research API may help eligible researchers inspect comment metadata, but it is not a usable general-purpose StickerDrop sticker-media source. It also does not establish unrestricted or free access for this app.

The cited TikTok Terms of Service page includes restrictions on automated extraction without written approval. That page is the US version; confirm the current Indonesia-applicable terms and obtain written authorization for the intended use before deploying an automated source. This engineering note is not legal advice.

Official references:

- Research API — Query Video Comments: https://developers.tiktok.com/docs/en/research-api-specs-query-video-comments
- About Research Tools: https://developers.tiktok.com/docs/en/about-research-api
- Research API FAQ and eligibility: https://developers.tiktok.com/docs/en/research-api-faq/
- TikTok Terms of Service (US version): https://t.tiktok.com/legal/page/us/terms-of-service/en?lang=en

## Usage

From the project root, prepare two local files obtained through a source authorized for the intended use:

- `source-response.json`: a captured normalized comment page containing the exact comment or reply and its `cmt_sticker_struct`.
- `sticker.webp`: the exact media bytes downloaded from the URL returned in that sticker struct.

Run:

```powershell
python scripts/qualify_adapter_source.py `
  --fixture .\source-response.json `
  --comment-id 7700946321838818056 `
  --media-file .\sticker.webp `
  --expected-sha256 b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878
```

Exit code `0` means the captured source and exact media file passed the full qualification gate. Exit code `2` means it is not qualified. The output includes a machine-readable list of checks and safe issue codes. It reports the media host only, never the signed URL or its query parameters.

For a newly captured source without the downloaded file, the result is `metadata_only`, not `qualified`. This distinction is intentional: a comment object or URL alone does not prove that the media can actually be retrieved and used.

The source fixture may be a normalized page such as:

```json
{
  "comments": [
    {
      "cid": "7700946321838818056",
      "text": "[Sticker]",
      "cmt_sticker_struct": {
        "sticker_id": "example-id",
        "static_url": {
          "url_list": ["https://approved-cdn.example/sticker.webp"]
        }
      }
    }
  ],
  "has_more": false,
  "cursor": null
}
```

Do not commit raw signed CDN URLs, cookies, bearer tokens, API keys, or unredacted provider payloads into Git. Treat captured user content as sensitive. Use a local fixture and delete or sanitize it after qualification.

## Qualification statuses

- `qualified`: exact comment, sticker struct, approved HTTPS CDN host, valid RIFF/WebP media bytes, and optional SHA-256 all pass.
- `metadata_only`: comment and sticker metadata/URL are present and host is allowed, but exact media bytes were not supplied for validation.
- `comment_only`: exact comment exists but has no sticker struct. A text label such as `[Sticker]` is not proof of an attached media object.
- `not_qualified`: exact comment is missing, media URL is missing/disallowed, media is invalid, or the reference hash does not match.

The tool does not fetch media itself. It validates bytes already obtained by an authorized acquisition path, avoiding hidden network requests and unexpected provider charges.

## Tests and limitations

Patch 7 adds deterministic tests for top-level and nested replies, exact ID matching, absent sticker structs, URL allowlisting, invalid WebP bytes, missing bytes, hash mismatch, and animated URL selection. The test runner remains offline and uses synthetic fixtures. Passing these tests validates the qualification tool, not a live TikTok data source.

The independent TikTok sticker-source adapter remains **not implemented**. `EXTRACTION_PROVIDER=disabled` must stay unchanged until a source is both authorized for the intended use and passes this qualification gate with the Golden Reference.
