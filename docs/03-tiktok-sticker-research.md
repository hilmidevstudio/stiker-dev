# Phase B — TikTok Sticker Extraction Research

## 1. Structure of TikTok Comment Stickers
In TikTok's internal data model (the `aweme` short-video service architecture), comment attachments are represented within the comment dictionary under specialized struct keys:

```json
{
  "cid": "7708394712596972308",
  "aweme_id": "7708356144804236564",
  "text": "ngajak ribut kamu? 🗿",
  "create_time": 1731600000,
  "digg_count": 42,
  "status": 1,
  "user": {
    "uid": "7435664412436120631",
    "nickname": "crazyolshop1",
    "unique_id": "crazyolshop1",
    "avatar_thumb": {
      "url_list": [
        "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/avatar.webp?..."
      ]
    }
  },
  "cmt_sticker_struct": {
    "sticker_id": "7421890123456789012",
    "sticker_type": 2,
    "static_url": {
      "uri": "tos-maliva-i-photomode-us/sticker_static_xxx.webp",
      "url_list": [
        "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/sticker_static_xxx.webp?x-expires=...",
        "https://p19-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/sticker_static_xxx.webp?x-expires=..."
      ],
      "width": 300,
      "height": 300
    },
    "animated_url": {
      "uri": "tos-maliva-i-photomode-us/sticker_animated_xxx.awebp",
      "url_list": [
        "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/sticker_animated_xxx.awebp?x-expires=...",
        "https://p19-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/sticker_animated_xxx.awebp?x-expires=..."
      ],
      "width": 300,
      "height": 300
    }
  }
}
```

---

## 2. Comparison of Comment Varieties

| Comment Variant | Text Field | `cmt_sticker_struct` | `comment_pics` | Media Format | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Plain Text** | Contains text | Absent or `null` | Absent or `null` | None | Standard comment |
| **Static Sticker** | May have text or empty | Present (`sticker_type: 1`) | Absent | `.webp` / `.png` | Only `static_url` populated |
| **Animated Sticker** | May have text or empty | Present (`sticker_type: 2`) | Absent | `.awebp` (Animated WebP) | Both `static_url` & `animated_url` populated |
| **Image Attachment** | May have text | Absent | Present (`comment_pics: [...]`) | `.jpeg` / `.webp` | Photo comment in regions supporting photo replies |
| **Nested Reply** | May have text | Present if sticker attached | Varies | Varies | Nested under `reply_comment` or fetched via reply endpoint |

---

## 3. CDN & Format Investigation: `.awebp`

1. **Naming Convention**: TikTok uses the extension `.awebp` (Animated WebP) for animated stickers.
2. **Binary Reality**: Despite the custom extension, an `.awebp` file is a valid standard **RIFF / Extended WebP (`WEBP VP8X`)** binary file containing:
   - `RIFF` magic header + `WEBP` fourcc.
   - `VP8X` chunk with the Animation flag (`ANIMATION_FLAG = 0x02`) set.
   - `ANIM` chunk defining background color and animation loop count.
   - Sequential `ANMF` chunks defining each frame's coordinates, dimensions, duration in milliseconds, and frame image bitstreams.
3. **CDN Accessibility**:
   - TikTok CDN domains: `p16-sign-useastdict.tiktokcdn.com`, `p16-sign-va.tiktokcdn.com`, `v16m-default.akamaized.net`.
   - The URLs contain cryptographic query tokens (`x-expires`, `x-signature`).
   - They are directly downloadable via standard HTTP GET with standard headers (`User-Agent`, `Accept`). No login or session cookies are required to fetch the media once the CDN URL is known.

---

## 4. The Direct Web Scraping Blocker: Slardar WAF

Empirical testing on `www.tiktok.com` demonstrated that direct unauthenticated HTTP requests are intercepted by ByteDance's Web Application Firewall:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <script id="slardar-config" type="application/json">
      {
        "slardarClient": "SlardarWAF",
        "sdkUrl": "https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/slardar/fe/sdk-web/browser.sg.js",
        "bid": "slardar_us_waf",
        "pid": "js-50"
      }
    </script>
  </head>
  <body>
    Please wait...
    <p id="wci" class="_wafchallengeid"></p>
    <script src="https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/obj/waf-aiso/dd9808.js"></script>
  </body>
</html>
```

Direct requests to `https://www.tiktok.com/api/comment/list/` without active web cookies return `{"comments": null, "status_code": 0}`.
Mobile endpoints (`/aweme/v1/comment/list/`) require proprietary signatures (`X-Gorgon`, `X-Khronos`).

**Conclusion**: Direct scraping from the client or from an unmanaged server is fragile and actively blocked. A reliable extraction engine must utilize a provider that solves device signatures and WAF challenges at scale.
