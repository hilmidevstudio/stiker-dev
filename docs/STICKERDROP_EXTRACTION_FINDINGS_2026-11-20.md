# StickerDrop: Findings from user-provided TikTok links (20 November 2026)

## Confirmed from redirect metadata

- The supplied list contains 21 URLs.
- There are 20 distinct short-link codes because one input is repeated exactly.
- Those redirects identify 19 distinct comment IDs; two different short links point to the same comment.
- They identify 15 distinct TikTok post IDs.
- The set includes both `/video/{id}` and `/photo/{id}` destinations.
- Each resolved share URL contains `share_comment_id`, `share_item_id` (or the same post ID in the path), and `comment_author_id`.

The full index-to-ID mapping is in `research/stickerdrop-user-link-corpus-2026-11-20.json` and `.csv`. This dataset verifies URL resolution metadata only. It does **not** prove that every target comment still exists, contains a sticker, or that its media URL is returned by a given data source.

## Code defect fixed in this patch

`backend/link_resolver.py` previously recognized `/video/{id}` and `/v/{id}` only. It did not recognize `/photo/{id}`. It also rebuilt every canonical URL as `/video/{id}`, even when the original redirect was a photo-mode post. This caused photo comment links to be sent to the extraction provider with the wrong post route. The resolver now recognizes `/photo/{id}`, records `post_type`, and preserves the correct route.

Short-link resolution previously used `HEAD` first. TikTok's short-link redirect should be resolved using `GET`; the resolver now uses a streamed GET and fails explicitly if the short host remains unresolved, instead of silently returning the original short URL.

The legacy resolver under `src/link_resolver/` is aligned to avoid two code paths behaving differently.

## New no-credit diagnostic route

`POST /v1/resolve-link` resolves a short/canonical TikTok URL and returns `post_id` (currently exposed as `video_id` for API compatibility), `post_type`, `comment_id`, `author_id`, and `canonical_url`. It does not instantiate or call an extraction provider and therefore does not spend provider credits.

This endpoint diagnoses only Stage 1 (URL resolution). It does not fetch comments or sticker media.

## Remaining extraction blockers

1. The production extractor searches at most five comment pages.
2. If the comment is a reply and is not included in a parent's reply preview, it searches only the first four parent threads and only one replies page for each. This is incomplete and can miss a valid target.
3. The extractor requires `cmt_sticker_struct` or `comment_pics` to obtain an asset URL. ScrapeCreators' published example response for comments/replies does not document `cmt_sticker_struct`; a live raw response is needed to prove whether the field is actually present for these links.
4. ScrapeCreators documents 1 credit for each comment page containing comments and 1 credit per replies request. The current bounded lookup can therefore spend credits before a target is found.
5. There is no verified, authorized, public TikTok API documented for retrieving arbitrary users' comment-sticker binary URLs from all comments. TikTok Research Tools describe comment text/count/time for approved non-profit research; their published field list does not advertise sticker-media URLs.

## Important boundary

This patch makes URL resolution correct for the observed video/photo share formats and adds a no-provider diagnostic. It does not claim that a self-hosted scraper can obtain arbitrary TikTok comment-sticker media without provider credits. TikTok's published terms currently prohibit automated extraction unless authorized in writing, and its Research Tools require application/approval and are limited to eligible research use. Do not implement bypasses for WAF, private app endpoints, device signatures, or access controls as a production foundation.

## Verification

`python scripts/run_tests.py` passes 42 tests after the resolver changes and the user-link corpus regression test. These are local unit/integration tests; no live extraction API was called and no sticker bytes were downloaded in this validation run.
