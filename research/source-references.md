# Research References & Literature Citations

## 1. Official Documentation & Specifications
1. **Google WebP Container Specification**:
   - URL: `https://developers.google.com/speed/webp/docs/riff_container`
   - Covers: RIFF structure, `VP8 `, `VP8L`, `VP8X` chunks, `ANIM` and `ANMF` animation frame chunks.
2. **WhatsApp Stickers Android API Reference**:
   - Repository: `https://github.com/WhatsApp/stickers`
   - Architecture: `StickerContentProvider`, `contents.json` schema, 512×512 resolution, 500 KB animated / 100 KB static limits, 3–30 count limits.
3. **ByteDance Aweme API & Slardar WAF Literature**:
   - WAF: Slardar WAF challenge structure (`slardar_us_waf`, `dd9808.js`, `_wafchallengeid`).
   - Aweme Comment List: `/aweme/v1/comment/list/`, `/aweme/v1/comment/list/reply/`, `cmt_sticker_struct`.

---

## 2. Extraction APIs & Services
1. **ScrapeSocial API**:
   - URL: `https://scrapesocial.ai/docs`
   - Endpoints: `GET /v1/tiktok/video/comments`, `GET /v1/tiktok/video/comment/replies`
   - Auth: `x-api-key`
2. **ScrapeCreators API**:
   - URL: `https://scrapecreators.com/docs`
   - Endpoints: Compatible with ScrapeSocial path structures.
3. **Apify Actor `rainminer/tiktok-comments-images-scraper`**:
   - URL: `https://apify.com/rainminer/tiktok-comments-images-scraper`
   - Target: Extraction of comment photos and sticker URLs.

---

## 3. Empirical Test Traces
- **Short URL**: `https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/`
- **Redirect Response**: HTTP 301 to `https://www.tiktok.com/@nyariprompt/video/7708356144804236564` with parameters:
  - `share_comment_id = 7708394712596972308`
  - `share_item_id = 7708356144804236564`
  - `comment_author_id = 7435664412436120631`
  - `panel_source_v2 = long_press_comment`
