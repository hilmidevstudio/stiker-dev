"""Safe, bounded WebP media fetcher used by the mobile client's media proxy."""

from __future__ import annotations

import ipaddress
import os
import urllib.parse
from typing import Iterable, Optional, Tuple

import httpx

from .extractor_adapter import ExtractionException


_DEFAULT_ALLOWED_HOSTS = (
    "tiktokcdn.com",
    "tiktokcdn-us.com",
    "tiktokcdn-eu.com",
    "tiktokcdn-uk.com",
    "byteoversea.com",
    "ibytedtos.com",
    "byteimg.com",
    "tiktok.com",
)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class WebPValidationError(ValueError):
    pass


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def validate_webp_container(data: bytes) -> None:
    """Validate RIFF/WebP chunk boundaries and static/animated payload consistency."""
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise WebPValidationError("Downloaded media is not a RIFF/WebP file.")
    riff_end = _u32(data, 4) + 8
    if riff_end != len(data) or riff_end < 20:
        raise WebPValidationError("WebP RIFF size does not match the downloaded file.")

    offset = 12
    has_vp8x = False
    animation_flag = False
    has_anim = False
    frame_count = 0
    has_static_payload = False

    while offset < riff_end:
        if riff_end - offset < 8:
            raise WebPValidationError("WebP chunk header is truncated.")
        chunk_type = data[offset:offset + 4]
        chunk_size = _u32(data, offset + 4)
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        padded_end = payload_end + (chunk_size & 1)
        if payload_end > riff_end or padded_end > riff_end:
            raise WebPValidationError("WebP chunk exceeds the RIFF container boundary.")

        if chunk_type == b"VP8X":
            if chunk_size != 10:
                raise WebPValidationError("Invalid VP8X chunk length.")
            has_vp8x = True
            animation_flag = (data[payload_start] & 0x02) != 0
        elif chunk_type == b"ANIM":
            if chunk_size != 6:
                raise WebPValidationError("Invalid ANIM chunk length.")
            has_anim = True
        elif chunk_type == b"ANMF":
            if chunk_size < 16:
                raise WebPValidationError("Invalid ANMF frame header.")
            frame_count += 1
        elif chunk_type in {b"VP8 ", b"VP8L"}:
            has_static_payload = True

        offset = padded_end

    if offset != riff_end:
        raise WebPValidationError("WebP chunk parsing did not end at the RIFF boundary.")
    if not has_vp8x and not has_static_payload:
        raise WebPValidationError("WebP contains no recognized image payload.")
    animated = animation_flag or has_anim or frame_count > 0
    if animated and not (has_vp8x and animation_flag and has_anim and frame_count > 0):
        raise WebPValidationError("WebP animation flags and frame chunks are inconsistent.")
    if not animated and not has_static_payload:
        raise WebPValidationError("Static WebP contains no VP8/VP8L image payload.")


class MediaGatewayError(ExtractionException):
    def __init__(self, message: str, error_code: str, status_code: int):
        super().__init__(message, error_code=error_code, status_code=status_code)


class MediaGateway:
    """Download only approved HTTPS CDN URLs, enforce size/time caps, validate WebP."""

    def __init__(
        self,
        *,
        allowed_hosts: Optional[Iterable[str]] = None,
        max_bytes: Optional[int] = None,
        timeout_seconds: float = 20.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        max_redirects: int = 3,
    ):
        if allowed_hosts is None:
            configured = os.getenv("STICKERDROP_MEDIA_ALLOWED_HOSTS", "")
            allowed_hosts = _DEFAULT_ALLOWED_HOSTS + tuple(
                item.strip().lower() for item in configured.replace(";", ",").split(",") if item.strip()
            )
        self.allowed_hosts = tuple(dict.fromkeys(h.lower().lstrip(".") for h in allowed_hosts if h))

        raw_max = max_bytes if max_bytes is not None else int(os.getenv("STICKERDROP_MEDIA_MAX_BYTES", "2000000"))
        if raw_max < 1024 or raw_max > 5_000_000:
            raise ValueError("STICKERDROP_MEDIA_MAX_BYTES must be between 1024 and 5000000")
        self.max_bytes = raw_max
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.max_redirects = max_redirects

    def validate_url(self, raw_url: str) -> str:
        try:
            parsed = urllib.parse.urlsplit(raw_url)
            host = (parsed.hostname or "").rstrip(".").lower()
            port = parsed.port
        except (ValueError, AttributeError):
            host, port = "", None
            parsed = urllib.parse.urlsplit("")

        if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
            raise MediaGatewayError(
                "Media URL must be an absolute HTTPS URL without embedded credentials.",
                "MEDIA_URL_NOT_ALLOWED", 403,
            )
        if port not in (None, 443):
            raise MediaGatewayError("Media URL uses a non-standard port.", "MEDIA_URL_NOT_ALLOWED", 403)
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
        if is_ip or not any(host == suffix or host.endswith("." + suffix) for suffix in self.allowed_hosts):
            raise MediaGatewayError(
                "Media host is not in StickerDrop's approved CDN allowlist.",
                "MEDIA_URL_NOT_ALLOWED", 403,
            )
        return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))

    async def fetch(self, raw_url: str) -> bytes:
        current_url = self.validate_url(raw_url)
        client_options = {
            "timeout": self.timeout_seconds,
            "follow_redirects": False,
        }
        if self.transport is not None:
            client_options["transport"] = self.transport

        try:
            async with httpx.AsyncClient(**client_options) as client:
                for redirect_count in range(self.max_redirects + 1):
                    async with client.stream(
                        "GET",
                        current_url,
                        headers={"Accept": "image/webp, application/octet-stream;q=0.8", "User-Agent": "StickerDrop-Media/1.0"},
                    ) as response:
                        if response.status_code in _REDIRECT_STATUSES:
                            if redirect_count >= self.max_redirects:
                                raise MediaGatewayError(
                                    "Media source exceeded the redirect limit.", "MEDIA_REDIRECT_LIMIT", 502
                                )
                            location = response.headers.get("location")
                            if not location:
                                raise MediaGatewayError(
                                    "Media source returned a redirect without a destination.", "MEDIA_FETCH_FAILED", 502
                                )
                            current_url = self.validate_url(urllib.parse.urljoin(current_url, location))
                            continue

                        if response.status_code != 200:
                            raise MediaGatewayError(
                                f"Media source returned HTTP {response.status_code}.",
                                "MEDIA_FETCH_FAILED", 502,
                            )

                        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        if content_type and content_type not in {
                            "image/webp", "image/x-webp", "image/awebp", "application/octet-stream"
                        }:
                            raise MediaGatewayError(
                                "Media source did not return a WebP-compatible content type.",
                                "INVALID_MEDIA_FILE", 502,
                            )

                        declared_size = response.headers.get("content-length")
                        if declared_size:
                            try:
                                if int(declared_size) > self.max_bytes:
                                    raise MediaGatewayError(
                                        "Sticker media exceeds the configured size limit.", "MEDIA_TOO_LARGE", 413
                                    )
                            except ValueError:
                                raise MediaGatewayError(
                                    "Media source returned an invalid content length.", "MEDIA_FETCH_FAILED", 502
                                )

                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > self.max_bytes:
                                raise MediaGatewayError(
                                    "Sticker media exceeds the configured size limit.", "MEDIA_TOO_LARGE", 413
                                )
                        body = bytes(chunks)
                        try:
                            validate_webp_container(body)
                        except WebPValidationError as exc:
                            raise MediaGatewayError(
                                str(exc), "INVALID_MEDIA_FILE", 502
                            ) from exc
                        return body

            raise MediaGatewayError("Media source did not produce a response.", "MEDIA_FETCH_FAILED", 502)
        except MediaGatewayError:
            raise
        except httpx.TimeoutException as exc:
            raise MediaGatewayError("Timed out while fetching sticker media.", "MEDIA_TIMEOUT", 504) from exc
        except httpx.HTTPError as exc:
            raise MediaGatewayError("Could not fetch sticker media from its CDN.", "MEDIA_FETCH_FAILED", 502) from exc
