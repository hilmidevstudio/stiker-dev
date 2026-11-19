# StickerDrop — Product Requirements Document (PRD)

## 1. Document Control
- **Document Version**: 1.0.0
- **Status**: Technically Validated & Engineering Ready
- **Date**: 2026-11-17
- **Target Platform**: Android (Eventual Mobile Implementation) / Backend Extraction Microservice

---

## 2. Executive Summary & Vision
StickerDrop solves a frictionless content extraction problem: TikTok users frequently encounter high-quality animated and static stickers attached to comments, but TikTok provides no native export mechanism to messaging platforms like WhatsApp.

The core product promise is:
$$\text{Copy Comment Link} \longrightarrow \text{Paste} \longrightarrow \text{Extract} \longrightarrow \text{Save} \longrightarrow \text{Export to WhatsApp}$$

- **Zero-Friction Authentication**: The end-user is **never** required to log into TikTok, provide credentials, or expose session cookies.
- **Single Persistent Collection**: All collected stickers are maintained in a permanent local storage repository across application launches.
- **Automated WhatsApp Pack Orchestration**: The local library automatically partitions stickers into WhatsApp-compliant virtual sticker packs (3 to 30 stickers per pack, 512×512 WebP, max 500 KB animated / 100 KB static).

---

## 3. User Personas & Use Cases

### Primary Persona: The Social Meme Curator ("Rian", 22)
- Discovers hilarious reaction stickers in TikTok comment sections.
- Wants to use those exact stickers in group chats on WhatsApp immediately.
- Frustrated by screenshots that lose transparency and animation.
- Unwilling to create new accounts or install complex scraping tools.

### Core User Journey
1. **Discovery**: User browses TikTok, sees comment with an animated sticker (e.g., child Prabowo in red shirt).
2. **Share**: User long-presses comment or clicks share -> "Copy link" (`https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/`).
3. **Extraction**: User opens StickerDrop, link is auto-detected from clipboard or pasted manually.
4. **Resolution**: System resolves the link to Video ID (`7708356144804236564`) and Comment ID (`7708394712596972308`).
5. **Retrieval**: System queries the extraction engine, retrieves the sticker CDN asset (`.awebp`), validates its frames and dimensions.
6. **Persistence**: Sticker and metadata are saved to local SQLite database with SHA-256 deduplication.
7. **Export**: User views their collection, selects a generated pack, and taps "Add to WhatsApp".

---

## 4. Functional Requirements

| Req ID | Capability | Description | Priority |
| :--- | :--- | :--- | :--- |
| **FR-01** | URL Resolution | System must resolve short TikTok URLs (`vt.tiktok.com`, `vm.tiktok.com`) to canonical URLs and extract both `video_id` and `comment_id`. | P0 |
| **FR-02** | Loginless Extraction | System must retrieve comment sticker media without requesting TikTok user credentials or session cookies. | P0 |
| **FR-03** | Format Preservation | System must preserve original animation (`.awebp` / animated WebP) and never convert animated stickers into static images accidentally. | P0 |
| **FR-04** | Deduplication | System must reject duplicate extractions of the same comment or identical media hash (SHA-256). | P0 |
| **FR-05** | Persistent Storage | System must store sticker media files locally with SQLite metadata, remaining persistent across application restarts. | P0 |
| **FR-06** | Data Integrity | System must verify file existence and SHA-256 integrity on startup, detecting missing or corrupt files. | P1 |
| **FR-07** | Pack Partitioning | System must group the single library into valid WhatsApp packs containing between 3 and 30 stickers. | P0 |
| **FR-08** | Tray Icon Generation | System must generate a 96×96 pixel tray icon (< 50 KB) for each generated sticker pack. | P0 |
| **FR-09** | WhatsApp Provider | System must generate `contents.json` metadata conforming to the official WhatsApp Android Stickers API specification. | P0 |
| **FR-10** | Offline Resiliency | Saved stickers must be fully browseable, manageable, and exportable without an internet connection. | P1 |

---

## 5. Non-Functional Requirements

- **Performance**: Link resolution and metadata extraction response under 3.0 seconds on standard 4G/WiFi connections.
- **Security**: Third-party API keys (e.g. ScrapeSocial) must **never** be shipped in the client APK; they must reside on a secured backend proxy.
- **Reliability**: If an extraction provider fails, the system must gracefully return a clear diagnostic message without crashing.
- **Storage Footprint**: SQLite database schema must use lightweight normalized tables; media files must be stored directly on filesystem with relative paths in the DB.
- **Compliance**: Adhere strictly to WhatsApp sticker size constraints (static <= 100 KB, animated <= 500 KB, 512×512 px) to prevent WhatsApp import rejections.
