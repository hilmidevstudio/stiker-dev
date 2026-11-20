"""Pure-Python RIFF / WebP / AWEBP binary parser and WhatsApp validator."""

from dataclasses import dataclass, field
from typing import List
import hashlib
import struct


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
    """Parse WebP container chunks; animation is derived from binary structure."""

    WHATSAPP_MAX_STATIC_BYTES = 100 * 1024
    WHATSAPP_MAX_ANIMATED_BYTES = 500 * 1024
    WHATSAPP_MAX_DURATION_MS = 6000
    WHATSAPP_REQUIRED_DIMENSION = 512

    @staticmethod
    def _read_uint24_le(data: bytes, offset: int) -> int:
        b0, b1, b2 = struct.unpack_from("<BBB", data, offset)
        return b0 | (b1 << 8) | (b2 << 16)

    @staticmethod
    def _invalid(raw_bytes: bytes, issue: str, chunks: List[str] | None = None) -> WebPMetadata:
        return WebPMetadata(
            is_valid_webp=False,
            is_animated=False,
            width=0,
            height=0,
            file_size=len(raw_bytes),
            frame_count=0,
            duration_ms=0,
            has_alpha=False,
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            chunks=chunks or [],
            whatsapp_compliant=False,
            compliance_issues=[issue],
        )

    def parse(self, raw_bytes: bytes) -> WebPMetadata:
        file_size = len(raw_bytes)
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        if file_size < 20:
            return self._invalid(raw_bytes, "File is shorter than the minimum WebP RIFF container.")
        if raw_bytes[:4] != b"RIFF" or raw_bytes[8:12] != b"WEBP":
            return self._invalid(
                raw_bytes,
                f"Invalid magic bytes: header is {raw_bytes[:4]!r}, container is {raw_bytes[8:12]!r}.",
            )

        declared_size = struct.unpack_from("<I", raw_bytes, 4)[0] + 8
        if declared_size != file_size:
            return self._invalid(
                raw_bytes,
                f"RIFF size mismatch: header declares {declared_size} bytes, actual file has {file_size}.",
            )

        offset = 12
        chunks_found: List[str] = []
        animation_flag = False
        has_anim_chunk = False
        has_anmf_chunks = False
        has_alpha = False
        has_image_payload = False
        width = 0
        height = 0
        frame_count = 0
        total_duration_ms = 0

        while offset < file_size:
            if offset + 8 > file_size:
                return self._invalid(raw_bytes, "Truncated WebP chunk header.", chunks_found)

            chunk_bytes = raw_bytes[offset:offset + 4]
            chunk_fourcc = chunk_bytes.decode("latin-1", errors="replace")
            chunk_size = struct.unpack_from("<I", raw_bytes, offset + 4)[0]
            chunk_data_offset = offset + 8
            chunk_end = chunk_data_offset + chunk_size
            padded_end = chunk_end + (chunk_size % 2)
            chunks_found.append(chunk_fourcc)

            if chunk_end > file_size or padded_end > file_size:
                return self._invalid(
                    raw_bytes,
                    f"Chunk {chunk_fourcc!r} exceeds RIFF container boundary.",
                    chunks_found,
                )

            if chunk_fourcc == "VP8X":
                if chunk_size != 10:
                    return self._invalid(raw_bytes, "Invalid VP8X chunk length.", chunks_found)
                flags = raw_bytes[chunk_data_offset]
                animation_flag = bool(flags & 0x02)
                has_alpha = bool(flags & 0x10)
                width = self._read_uint24_le(raw_bytes, chunk_data_offset + 4) + 1
                height = self._read_uint24_le(raw_bytes, chunk_data_offset + 7) + 1

            elif chunk_fourcc == "ALPH":
                has_alpha = True

            elif chunk_fourcc == "ANIM":
                if chunk_size != 6:
                    return self._invalid(raw_bytes, "Invalid ANIM chunk length.", chunks_found)
                has_anim_chunk = True

            elif chunk_fourcc == "ANMF":
                if chunk_size < 16:
                    return self._invalid(raw_bytes, "Invalid ANMF frame header.", chunks_found)
                has_anmf_chunks = True
                has_image_payload = True
                frame_count += 1
                total_duration_ms += self._read_uint24_le(raw_bytes, chunk_data_offset + 12)

            elif chunk_fourcc == "VP8 ":
                has_image_payload = True
                if chunk_size >= 10 and width == 0:
                    if raw_bytes[chunk_data_offset + 3:chunk_data_offset + 6] == b"\x9d\x01\x2a":
                        w_raw = struct.unpack_from("<H", raw_bytes, chunk_data_offset + 6)[0]
                        h_raw = struct.unpack_from("<H", raw_bytes, chunk_data_offset + 8)[0]
                        width = w_raw & 0x3fff
                        height = h_raw & 0x3fff

            elif chunk_fourcc == "VP8L":
                has_image_payload = True
                if chunk_size >= 5 and width == 0 and raw_bytes[chunk_data_offset] == 0x2f:
                    b1, b2, b3, b4 = struct.unpack_from("<BBBB", raw_bytes, chunk_data_offset + 1)
                    width = 1 + (b1 | ((b2 & 0x3f) << 8))
                    height = 1 + ((b2 >> 6) | (b3 << 2) | ((b4 & 0x0f) << 10))

            offset = padded_end

        if offset != file_size or not has_image_payload:
            return self._invalid(raw_bytes, "WebP RIFF container is incomplete or contains no image payload.", chunks_found)

        has_frames = frame_count > 0
        if animation_flag != has_anim_chunk or animation_flag != has_frames:
            return self._invalid(
                raw_bytes,
                "WebP animation flag, ANIM chunk, and ANMF frames are inconsistent.",
                chunks_found,
            )
        is_animated = animation_flag and has_anim_chunk and has_frames
        if not is_animated:
            frame_count = 1
            total_duration_ms = 0

        issues: List[str] = []
        if width != self.WHATSAPP_REQUIRED_DIMENSION or height != self.WHATSAPP_REQUIRED_DIMENSION:
            issues.append(f"Dimensions {width}x{height} do not match required WhatsApp 512x512 pixels.")

        if is_animated:
            if file_size > self.WHATSAPP_MAX_ANIMATED_BYTES:
                issues.append(f"Animated sticker size ({file_size} bytes) exceeds WhatsApp 500 KB limit.")
            if total_duration_ms > self.WHATSAPP_MAX_DURATION_MS:
                issues.append(f"Animation duration ({total_duration_ms} ms) exceeds WhatsApp 6000 ms limit.")
        elif file_size > self.WHATSAPP_MAX_STATIC_BYTES:
            issues.append(f"Static sticker size ({file_size} bytes) exceeds WhatsApp 100 KB limit.")

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
            whatsapp_compliant=not issues,
            compliance_issues=issues,
        )
