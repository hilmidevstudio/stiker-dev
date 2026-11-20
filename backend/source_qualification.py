"""Offline qualification of a candidate StickerDrop extraction source.

This module never contacts TikTok or a provider. It validates a captured,
normalized comment payload and (optionally) the exact media bytes obtained by an
authorized source. Signed media URLs are deliberately excluded from reports.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

from .media_gateway import MediaGateway, MediaGatewayError, _DEFAULT_ALLOWED_HOSTS
from src.media.validator import WebPBinaryParser


_COMMENT_CONTAINER_KEYS = (
    "comments",
    "comment_list",
    "reply_comment",
    "replies",
    "reply_list",
    "items",
)
_WRAPPER_KEYS = ("data", "result", "response")


def _comment_id(comment: Dict[str, Any]) -> Optional[str]:
    for key in ("cid", "comment_id", "id"):
        value = comment.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _iter_comments(node: Any, visited: Optional[set[int]] = None) -> Iterator[Dict[str, Any]]:
    """Walk only known comment containers; avoid scanning arbitrary user payloads."""
    if visited is None:
        visited = set()
    if isinstance(node, (dict, list)):
        node_identity = id(node)
        if node_identity in visited:
            return
        visited.add(node_identity)

    if isinstance(node, list):
        for child in node:
            yield from _iter_comments(child, visited)
        return

    if not isinstance(node, dict):
        return

    if _comment_id(node) is not None:
        yield node

    for key in _COMMENT_CONTAINER_KEYS + _WRAPPER_KEYS:
        child = node.get(key)
        if isinstance(child, (dict, list)):
            yield from _iter_comments(child, visited)


def _first_url(media_object: Any) -> Optional[str]:
    if not isinstance(media_object, dict):
        return None
    urls = media_object.get("url_list")
    if isinstance(urls, list):
        for url in urls:
            if isinstance(url, str) and url.strip():
                return url.strip()
    for resolution_key in ("high_resolution_url", "mid_resolution_url", "low_resolution_url"):
        nested = _first_url(media_object.get(resolution_key))
        if nested:
            return nested
    return None


def _extract_media_candidate(sticker_struct: Dict[str, Any]) -> tuple[Optional[str], bool]:
    """Return selected media URL and whether it came from animated_url."""
    animated_url = _first_url(sticker_struct.get("animated_url"))
    static_url = _first_url(sticker_struct.get("static_url"))
    if animated_url:
        return animated_url, True
    if static_url:
        return static_url, False
    return None, False


def qualify_sticker_source(
    payload: Any,
    target_comment_id: str,
    *,
    media_bytes: Optional[bytes] = None,
    expected_sha256: Optional[str] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Assess whether captured source data meets StickerDrop's real-media contract.

    A metadata-only result is never reported as fully qualified. Full qualification
    requires an exact comment match, a real sticker struct, an approved HTTPS media
    host, and valid RIFF/WebP bytes. No network request is made here.
    """
    target = str(target_comment_id).strip()
    result: Dict[str, Any] = {
        "status": "not_qualified",
        "target_comment_id": target,
        "checks": {
            "exact_comment_found": False,
            "sticker_struct_present": False,
            "media_url_present": False,
            "media_url_allowed": False,
            "media_bytes_provided": media_bytes is not None,
            "media_file_valid": False if media_bytes is not None else None,
            "expected_sha256_match": None,
        },
        "issues": [],
    }

    if not target:
        result["issues"].append("TARGET_COMMENT_ID_REQUIRED")
        return result

    matched = next((item for item in _iter_comments(payload) if _comment_id(item) == target), None)
    if matched is None:
        result["issues"].append("EXACT_COMMENT_NOT_FOUND")
        return result

    result["checks"]["exact_comment_found"] = True
    sticker_struct = matched.get("cmt_sticker_struct")
    if not isinstance(sticker_struct, dict) or not sticker_struct:
        result["issues"].append("STICKER_STRUCT_MISSING")
        result["status"] = "comment_only"
        return result

    result["checks"]["sticker_struct_present"] = True
    sticker_id = sticker_struct.get("sticker_id") or sticker_struct.get("id")
    media_url, selected_animated = _extract_media_candidate(sticker_struct)
    result["sticker_id"] = str(sticker_id) if sticker_id is not None else None
    result["source_media_hint"] = "animated" if selected_animated else "static"

    if not media_url:
        result["issues"].append("STICKER_MEDIA_URL_MISSING")
        return result

    result["checks"]["media_url_present"] = True
    effective_hosts = None if allowed_hosts is None else (*_DEFAULT_ALLOWED_HOSTS, *tuple(allowed_hosts))
    gateway = MediaGateway(allowed_hosts=effective_hosts)
    try:
        normalized_url = gateway.validate_url(media_url)
        from urllib.parse import urlsplit
        result["media_host"] = urlsplit(normalized_url).hostname
        result["checks"]["media_url_allowed"] = True
    except MediaGatewayError:
        result["issues"].append("MEDIA_HOST_OR_URL_NOT_ALLOWED")

    if media_bytes is None:
        result["issues"].append("MEDIA_BYTES_NOT_PROVIDED")
        result["status"] = "metadata_only" if result["checks"]["media_url_allowed"] else "not_qualified"
        return result

    metadata = WebPBinaryParser().parse(media_bytes)
    result["checks"]["media_file_valid"] = bool(metadata.is_valid_webp)
    result["media"] = {
        "file_size": metadata.file_size,
        "sha256": metadata.sha256,
        "is_animated": metadata.is_animated,
        "width": metadata.width,
        "height": metadata.height,
        "frame_count": metadata.frame_count,
        "duration_ms": metadata.duration_ms,
        "whatsapp_compliant": metadata.whatsapp_compliant,
        "compliance_issues": metadata.compliance_issues,
    }

    if not metadata.is_valid_webp:
        result["issues"].append("MEDIA_FILE_INVALID_WEBP")
    if expected_sha256:
        expected = expected_sha256.strip().lower()
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            result["issues"].append("EXPECTED_SHA256_INVALID")
            result["checks"]["expected_sha256_match"] = False
        else:
            matched_hash = metadata.sha256.lower() == expected
            result["checks"]["expected_sha256_match"] = matched_hash
            if not matched_hash:
                result["issues"].append("SHA256_MISMATCH")

    required_checks = (
        result["checks"]["exact_comment_found"],
        result["checks"]["sticker_struct_present"],
        result["checks"]["media_url_present"],
        result["checks"]["media_url_allowed"],
        result["checks"]["media_file_valid"],
    )
    hash_ok = result["checks"]["expected_sha256_match"] is not False
    if all(required_checks) and hash_ok and "EXPECTED_SHA256_INVALID" not in result["issues"]:
        result["status"] = "qualified"
    return result


def qualify_sticker_source_file(
    fixture_path: str | Path,
    target_comment_id: str,
    *,
    media_path: Optional[str | Path] = None,
    expected_sha256: Optional[str] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """File-oriented helper used by the CLI and offline acceptance tests."""
    import json

    fixture_path = Path(fixture_path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "status": "not_qualified",
            "target_comment_id": str(target_comment_id),
            "checks": {},
            "issues": ["FIXTURE_FILE_UNREADABLE_OR_INVALID_JSON", type(exc).__name__],
        }

    media_bytes = None
    if media_path is not None:
        try:
            media_bytes = Path(media_path).read_bytes()
        except OSError as exc:
            return {
                "status": "not_qualified",
                "target_comment_id": str(target_comment_id),
                "checks": {"media_bytes_provided": False},
                "issues": ["MEDIA_FILE_UNREADABLE", type(exc).__name__],
            }

    return qualify_sticker_source(
        payload,
        target_comment_id,
        media_bytes=media_bytes,
        expected_sha256=expected_sha256,
        allowed_hosts=allowed_hosts,
    )
