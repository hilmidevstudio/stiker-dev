# Phase F — Security, Privacy & Compliance Architecture

## 1. Zero-Credential Architecture
StickerDrop is fundamentally engineered around a **zero-credential user model**:
- **No TikTok Passwords**: The application never prompts for, stores, or transmits TikTok usernames or passwords.
- **No Session Cookie Scraping**: The app does not steal or inspect private TikTok browser cookies or session tokens.
- **No Private Content Access**: The system only operates on publicly accessible comment attachments shared via public TikTok URLs.

---

## 2. API Key Protection & Threat Modeling

### Threat: Mobile Client Reverse Engineering
- **Vulnerability**: If an API key for ScrapeSocial, ScrapeCreators, or Apify is bundled within the Flutter or Android APK, an adversary can decompile the APK (via `jadx` or `apktool`) in under 60 seconds and extract the cleartext secret.
- **Consequence**: Unauthorized third parties could drain the developer's API quota, run arbitrary scraping jobs, and run up immense cloud bills.
- **Enforced Countermeasure**:
  - All third-party extraction API keys reside **strictly on the backend proxy server**.
  - The mobile client communicates exclusively with the StickerDrop backend proxy via authenticated app-token or rate-limited endpoints.
  - The client binary contains zero third-party secrets.

---

## 3. Storage Security & User Privacy
- **Local Isolation**: All sticker metadata and media files are stored within the application's internal sandboxed directory (`/data/data/com.stickerdrop.app/files/` or equivalent).
- **No Unsolicited Tracking**: StickerDrop does not report the user's saved sticker catalog to external servers. What the user saves remains on their personal device.
- **WhatsApp ContentProvider Sandboxing**: Media shared to WhatsApp is exposed strictly through standard Android `ContentProvider` URIs requiring `com.whatsapp.sticker.READ` permission, preventing other rogue apps from tampering with the sticker files.

---

## 4. Platform Policy & Copyright Compliance
- **Fair Use & Personal Messaging**: Stickers are extracted for private personal communication between end-users on WhatsApp.
- **Watermarking & Authorship Preservation**: The database permanently records `source_author`, `source_video_id`, and `source_comment_id` ensuring provenance is retained for all media.
- **No Commercial Redistribution**: StickerDrop acts as a personal transfer utility (like a clipboard or downloader tool) and does not host a public commercial sticker marketplace.
