# Unresolved Technical Questions & Investigation Tracker

## 1. Tracked Research Questions

| ID | Question | Current Status | Investigation Strategy |
| :--- | :--- | :--- | :--- |
| **Q-01** | Does ScrapeSocial's `/v1/tiktok/video/comments` return the target comment `7708394712596972308` on page 1, or does it require cursor pagination? | **Pending Live Key** | Prepared test harness `scripts/live_extraction_test.py` with multi-page pagination loop (up to 5 pages) and fallback to `/comment/replies`. |
| **Q-02** | Is comment `7708394712596972308` a top-level comment or a nested reply to an earlier comment? | **Hypothesis: Likely Top-Level or First-Order Reply** | If not found in `/video/comments`, script automatically queries `/video/comment/replies` using `comment_id`. |
| **Q-03** | Does WhatsApp require exact 512×512 resolution for animated stickers, or does it tolerate non-square aspect ratios if padded? | **Verified** | WhatsApp strictly requires exact **512×512 pixels**. Any non-512px WebP is rejected by WhatsApp during pack import. |
| **Q-04** | Can Android's native `ImageDecoder` decode `.awebp` files directly into animated drawables? | **Verified** | Yes, on Android 9.0+ (API level 28+), `ImageDecoder.createSource` and `AnimatedImageDrawable` natively support Extended Animated WebP. |
| **Q-05** | Does TikTok CDN rotate or expire signed URL tokens? | **Verified** | Yes, `x-expires` query parameter specifies expiration (typically 24–72 hours). Therefore, StickerDrop must download and persist the raw bytes immediately upon extraction rather than storing only the transient CDN URL. |
