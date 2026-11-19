# Phase C — Media Processing Engine

## 1. Objective & Scope
The Media Processing Engine is responsible for binary inspection, format validation, dimension extraction, animation detection, and WhatsApp compliance verification for all media retrieved from TikTok CDN servers.

---

## 2. WebP & AWEBP Binary Specifications

TikTok delivers animated comment stickers in files titled `.awebp`. Mechanically, these are standard **Extended WebP** format files structured according to the Google WebP Container Specification.

```text
+-------------------------------------------------------------------------+
| 'RIFF' (4 bytes) | File Size - 8 (4 bytes) | 'WEBP' (4 bytes)          |
+-------------------------------------------------------------------------+
| 'VP8X' Chunk (Extended Header, 18 bytes total)                          |
|   - Chunk FourCC: 'VP8X' (4 bytes)                                      |
|   - Chunk Size: 10 (4 bytes, little-endian)                             |
|   - Flags (4 bytes):                                                    |
|       Bit 1: Animation flag (0x02)                                      |
|       Bit 4: Alpha flag (0x10)                                          |
|   - Canvas Width - 1: 3 bytes (little-endian uint24)                    |
|   - Canvas Height - 1: 3 bytes (little-endian uint24)                   |
+-------------------------------------------------------------------------+
| 'ANIM' Chunk (Animation Parameters, 14 bytes total)                     |
|   - Chunk FourCC: 'ANIM' (4 bytes)                                      |
|   - Chunk Size: 6 (4 bytes)                                             |
|   - Background Color: 4 bytes (RGBA)                                    |
|   - Loop Count: 2 bytes (0 = infinite)                                 |
+-------------------------------------------------------------------------+
| 'ANMF' Chunks (Repeated per animation frame)                            |
|   - Chunk FourCC: 'ANMF' (4 bytes)                                      |
|   - Chunk Size: N (4 bytes)                                             |
|   - Frame X: 3 bytes                                                    |
|   - Frame Y: 3 bytes                                                    |
|   - Frame Width - 1: 3 bytes                                            |
|   - Frame Height - 1: 3 bytes                                           |
|   - Frame Duration: 3 bytes (milliseconds, little-endian)               |
|   - Blending & Disposal flags: 1 byte                                   |
|   - Frame Bitstream (VP8 or VP8L sub-chunk)                             |
+-------------------------------------------------------------------------+
```

---

## 3. Pure-Python Binary Parsing

To guarantee extreme performance and zero external native dependencies, StickerDrop implements a native Python RIFF/WebP binary parser:

1. **Header Validation**:
   Checks `file_bytes[0:4] == b'RIFF'` and `file_bytes[8:12] == b'WEBP'`.
2. **Chunk Traversal**:
   Iterates through 4-byte chunk headers and 4-byte little-endian chunk sizes (respecting 2-byte RIFF padding).
3. **Dimensions Extraction**:
   - For `VP8X`: Canvas Width $= 1 + \text{read\_uint24}(12)$, Canvas Height $= 1 + \text{read\_uint24}(15)$.
   - For `VP8 `: Width & Height extracted from 10-byte VP8 keyframe header.
   - For `VP8L`: Width & Height extracted from 5-byte VP8L signature header.
4. **Animation Verification**:
   - Checks `VP8X` flag `(flags & 0x02) != 0`.
   - Counts `ANMF` chunks to determine exact frame count.
   - Sums durations of all `ANMF` chunks to compute total animation duration.

---

## 4. WhatsApp Sticker Constraints Matrix

| Property | WhatsApp Static Spec | WhatsApp Animated Spec | TikTok Sticker Typical Value | Compatibility Action |
| :--- | :--- | :--- | :--- | :--- |
| **Container Format** | WebP (`.webp`) | Animated WebP (`.webp` / `.awebp`) | `.awebp` / `.webp` | Valid (Directly supported) |
| **Canvas Dimensions** | Exactly **512 × 512 px** | Exactly **512 × 512 px** | 300 × 300 px (typical) | Needs padding / scaling to 512×512 |
| **Max File Size** | **100 KB** (102,400 bytes) | **500 KB** (512,000 bytes) | 80 KB – 350 KB | Valid (TikTok stickers are lightweight) |
| **Animation Duration**| N/A | Min 0.1s, Max **6.0s** | 1.0s – 3.5s | Valid |
| **Frame Rate** | N/A | Max **30 fps** | 10 – 20 fps | Valid |
| **Transparency** | Supported (8-bit alpha) | Supported (8-bit alpha) | Transparent backgrounds | Valid |
| **Margin/Padding** | 16 px transparent border | 16 px transparent border | Margined | Valid |

---

## 5. Processing Strategy: Preservation First

> [!IMPORTANT]
> **Cardinal Rule**: Never convert animated stickers into static images. Preserve the original animation whenever possible.

1. If the source sticker is animated (`VP8X` with animation flag):
   - Check file size $\le 500\text{ KB}$ and duration $\le 6.0\text{ s}$.
   - If dimensions are already 512×512, retain file byte-for-byte (bit-exact preservation).
   - If dimensions are not 512×512, pad/rescale preserving aspect ratio to fit the 512×512 canvas.
2. If the source sticker is static:
   - Check file size $\le 100\text{ KB}$.
   - Pad/rescale to 512×512.
3. Generate a SHA-256 hash of the processed media for cryptographic deduplication.
