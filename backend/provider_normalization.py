"""Normalize supported provider wire payloads into StickerDrop's page contract.

The discovery engine must never interpret an unknown upstream response as an empty
page. Unsupported payload shapes raise a typed error instead of creating false 404s.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple

def _invalid_response(message: str):
    # Import lazily to avoid a module cycle: extractor_adapter uses this normalizer.
    from .extractor_adapter import ExtractionException
    return ExtractionException(
        message,
        error_code="UPSTREAM_INVALID_RESPONSE",
        status_code=502,
    )


_COMMENT_KEYS = ("comments", "comment_list", "reply_list", "replies", "items")
_WRAPPER_KEYS = ("data", "result", "response")
_HAS_MORE_KEYS = ("has_more", "hasMore", "has_more_pages", "hasMorePages")
_CURSOR_KEYS = ("cursor", "next_cursor", "nextCursor", "cursor_next", "cursorNext")


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _find_page_object(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return (page, root) while unwrapping common JSON envelope shapes."""
    page = payload
    for _ in range(3):
        nested = next(
            (page.get(key) for key in _WRAPPER_KEYS if isinstance(page.get(key), dict)),
            None,
        )
        if not isinstance(nested, dict):
            break
        page = nested
    return page, payload


def _find_comment_list(page: Dict[str, Any], root: Dict[str, Any]) -> Optional[List[Any]]:
    for source in (page, root):
        for key in _COMMENT_KEYS:
            if key in source:
                value = source[key]
                if value is None:
                    return []
                if isinstance(value, list):
                    return value
                raise _invalid_response("The extraction source returned a malformed comment collection.")
    return None


def _first_value(sources: Iterable[Dict[str, Any]], keys: Iterable[str]) -> Any:
    for source in sources:
        for key in keys:
            if key in source:
                return source[key]
    return None


def _normalize_user(comment: Dict[str, Any]) -> None:
    """Preserve author information and map common source names to `user` fields."""
    user = comment.get("user")
    if not isinstance(user, dict):
        user = comment.get("author") or comment.get("user_info") or comment.get("author_info")
    if not isinstance(user, dict):
        user = {}

    normalized_user = deepcopy(user)
    aliases = {
        "uid": ("uid", "user_id", "id", "author_id"),
        "unique_id": ("unique_id", "username", "uniqueId", "sec_uid"),
        "nickname": ("nickname", "display_name", "displayName", "name"),
    }
    for target, candidates in aliases.items():
        if normalized_user.get(target) in (None, ""):
            value = next((comment.get(key) for key in candidates if comment.get(key) not in (None, "")), None)
            if value is None:
                value = next((user.get(key) for key in candidates if user.get(key) not in (None, "")), None)
            if value is not None:
                normalized_user[target] = value

    if normalized_user:
        comment["user"] = normalized_user


def _normalize_comment(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise _invalid_response("The extraction source returned a non-object comment entry.")
    comment = deepcopy(value)
    if comment.get("cid") in (None, ""):
        comment_id = comment.get("id") or comment.get("comment_id")
        if comment_id not in (None, ""):
            comment["cid"] = str(comment_id)

    if comment.get("reply_comment_total") in (None, ""):
        reply_count = comment.get("reply_count") or comment.get("total_reply") or comment.get("replyCount")
        if reply_count is not None:
            comment["reply_comment_total"] = reply_count

    if "reply_comment" not in comment:
        previews = comment.get("reply_comments") or comment.get("replies_preview")
        if isinstance(previews, list):
            comment["reply_comment"] = [_normalize_comment(item) for item in previews]

    _normalize_user(comment)
    return comment



def _check_source_error(payload: Dict[str, Any]) -> None:
    """Reject provider error envelopes instead of mistaking them for empty pages."""
    for source in (payload, payload.get("data", {}), payload.get("result", {})):
        if not isinstance(source, dict):
            continue
        error = source.get("error")
        if isinstance(error, dict):
            code = str(error.get("code", "")).strip().lower()
            if code not in {"", "0", "ok", "success", "none"}:
                raise _invalid_response("The extraction source reported an upstream API error.")
        if source.get("success") is False:
            raise _invalid_response("The extraction source reported an unsuccessful response.")


def normalize_provider_page(payload: Any) -> Dict[str, Any]:
    """Normalize a provider's comment/reply page.

    Supported collection aliases: comments, comment_list, reply_list, replies, items.
    Supported envelopes: root, data, result, or response (up to three levels).
    Cursor and pagination state are kept opaque; the discovery engine owns traversal.
    """
    if not isinstance(payload, dict):
        raise _invalid_response("The extraction source returned a non-object page.")

    _check_source_error(payload)
    page, root = _find_page_object(payload)
    raw_comments = _find_comment_list(page, root)
    if raw_comments is None:
        raise _invalid_response("The extraction source response did not contain a recognized comment collection.")

    sources = (page, root)
    raw_has_more = _first_value(sources, _HAS_MORE_KEYS)
    has_more = _as_bool(raw_has_more)
    cursor = _first_value(sources, _CURSOR_KEYS)

    # Fail closed when the source uses an unfamiliar pagination envelope. Assuming
    # end-of-list here would make the engine report a false COMMENT_NOT_FOUND.
    if has_more is None:
        if cursor is None:
            raise _invalid_response("The extraction source response did not contain recognizable pagination metadata.")
        has_more = True

    if not has_more:
        cursor = None

    return {
        "comments": [_normalize_comment(item) for item in raw_comments],
        "has_more": has_more,
        "cursor": cursor,
    }
