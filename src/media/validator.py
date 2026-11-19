"""
Pure-Python RIFF / WebP / AWEBP Binary Parser and Validator.
Inspects binary chunk structures with zero third-party C-bindings.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import struct
import hashlib


@dataclass
class WebPMetadata:
    is_valid_webp: bool
    is_animated: bool
    width: int
    height: int
    file_size: int
    frame_count: int
    duration_ms: int
    has_alpha: bool
    sha256: str
    chunks: List[str] = field(default_factory=list)
    whatsapp_compliant: bool = False
    compliance_issues: List[str] = field(default_factory=list)


class WebPBinaryParser:
    """
    Parses Google WebP / Extended WebP (VP8X) / Animated WebP (AWEBP) files.
    Reference: https://developers.google.com/speed/webp/docs/riff_container
    """

    WHATSAPP_MAX_STATIC_BYTES = 100 * 1024       # 100 KB
    WHATSAPP_MAX_ANIMATED_BYTES = 500 * 1024     # 500 KB
    WHATSAPP_MAX_DURATION_MS = 6000              # 6.0 seconds
    WHATSAPP_REQUIRED_DIMENSION = 512            # 512 x 512 px

    @staticmethod
    def _read_uint24_le(data: bytes, offset: int) -> int:
        b0, b1, b2 = struct.unpack_from("<BBB", data, offset)
        return b0 | (b1 << 8) | (b2 << 16)

    def parse(self, raw_bytes: bytes) -> WebPMetadata:
        """Parses raw WebP binary data and extracts chunk metadata."""
        issues: List[str] = []
        file_size = len(raw_bytes)
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        if file_size < 12:
            return WebPMetadata(
                is_valid_webp=False,
                is_animated=False,
                width=0,
                height=0,
                file_size=file_size,
                frame_count=0,
                duration_ms=0,
                has_alpha=False,
                sha256=sha256_hash,
                compliance_issues=["File size is less than 12-byte RIFF header minimum."]
            )

        riff_magic = raw_bytes[0:4]
        webp_magic = raw_bytes[8:12]

        if riff_magic != b"RIFF" or webp_magic != b"WEBP":
            return WebPMetadata(
                is_valid_webp=False,
                is_animated=False,
                width=0,
                height=0,
                file_size=file_size,
                frame_count=0,
                duration_ms=0,
                has_alpha=False,
                sha256=sha256_hash,
                compliance_issues=[f"Invalid magic bytes: header is {riff_magic!r}, container is {webp_magic!r}."]
            )

        offset = 12
        chunks_found: List[str] = []
        is_animated = False
        has_alpha = False
        width = 0
        height = 0
        frame_count = 0
        total_duration_ms = 0

        while offset + 8 <= file_size:
            chunk_fourcc = raw_bytes[offset:offset+4].decode("latin-1", errors="replace")
            chunk_size = struct.unpack_from("<I", raw_bytes, offset+4)[0]
            chunk_data_offset = offset + 8
            chunks_found.append(chunk_fourcc)

            if chunk_fourcc == "VP8X":
                if chunk_size >= 10:
                    flags = struct.unpack_from("<I", raw_bytes, chunk_data_offset)[0]
                    # Bit 1 (0x02) = Animation
                    is_animated = bool(flags & 0x02)
                    # Bit 4 (0x10) = Alpha
                    has_alpha = bool(flags & 0x10)
                    # 24-bit canvas width - 1
                    canvas_w = self._read_uint24_le(raw_bytes, chunk_data_offset + 4) + 1
                    # 24-bit canvas height - 1
                    canvas_h = self._read_uint24_le(raw_bytes, chunk_data_offset + 7) + 1
                    width = canvas_w
                    height = canvas_h

            elif chunk_fourcc == "VP8 ":
                # Simple Lossy WebP: keyframe header has dimensions
                if chunk_size >= 10 and width == 0:
                    # Bytes 6, 7, 8: 0x9d, 0x01, 0x2a (VP8 keyframe startcode)
                    if raw_bytes[chunk_data_offset+3:chunk_data_offset+6] == b"\x9d\x01\x2a":
                        w_raw = struct.unpack_from("<H", raw_bytes, chunk_data_offset+6)[0]
                        h_raw = struct.unpack_from("<H", raw_bytes, chunk_data_offset+8)[0]
                        width = w_raw & 0x3fff
                        height = h_raw & 0x3fff

            elif chunk_fourcc == "VP8L":
                # Simple Lossless WebP: 1-byte signature 0x2f, then 14-bit width - 1, 14-bit height - 1
                if chunk_size >= 5 and width == 0 and raw_bytes[chunk_data_offset] == 0x2f:
                    b1, b2, b3, b4 = struct.unpack_from("<BBBB", raw_bytes, chunk_data_offset+1)
                    width = 1 + (b1 | ((b2 & 0x3f) << 8))
                    height = 1 + (((b2 >> 6) | (b3 << 2) | ((b4 & 0x0f) << 10)))

            elif chunk_fourcc == "ANMF":
                is_animated = True
                frame_count += 1
                if chunk_size >= 16:
                    frame_duration = self._read_uint24_le(raw_bytes, chunk_data_offset + 12)
                    total_duration_ms += frame_duration

            # Chunks in RIFF are padded to even 2-byte boundaries
            chunk_padding = chunk_size % 2
            offset = chunk_data_offset + chunk_size + chunk_padding

        if not is_animated:
            frame_count = 1

        # WhatsApp Compliance Checks
        if width != self.WHATSAPP_REQUIRED_DIMENSION or height != self.WHATSAPP_REQUIRED_DIMENSION:
            issues.append(f"Dimensions {width}x{height} do not match required WhatsApp 512x512 pixels.")

        if is_animated:
            if file_size > self.WHATSAPP_MAX_ANIMATED_BYTES:
                issues.append(f"Animated sticker size ({file_size} bytes) exceeds WhatsApp 500 KB limit.")
            if total_duration_ms > self.WHATSAPP_MAX_DURATION_MS:
                issues.append(f"Animation duration ({total_duration_ms} ms) exceeds WhatsApp 6000 ms limit.")
        else:
            if file_size > self.WHATSAPP_MAX_STATIC_BYTES:
                issues.append(f"Static sticker size ({file_size} bytes) exceeds WhatsApp 100 KB limit.")

        whatsapp_compliant = (len(issues) == 0)

        return WebPMetadata(
            is_valid_webp=True,
            is_animated=is_animated,
            width=width,
            height=height,
            file_size=file_size,
            frame_count=frame_count,
            duration_ms=total_duration_ms,
            has_alpha=has_alpha,
            sha256=sha256_hash,
            chunks=chunks_found,
            whatsapp_compliant=whatsapp_compliant,
            compliance_issues=issues
        )
