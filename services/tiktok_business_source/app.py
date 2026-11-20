"""Read-only TikTok API for Business source bridge.

This service implements the HTTP contract consumed by StickerDrop's
AuthorizedSourceAdapter. It only reads comments and replies on videos owned by
the TikTok account that authorized the Business API application. It does not
scrape public pages, reverse-engineer private endpoints, or bypass access checks.

The official API may expose an `image_url` for image comments. That is preserved
as a comment image; this service never fabricates `cmt_sticker_struct` metadata.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


TIKTOK_API_ORIGIN = "https://business-api.tiktok.com"
COMMENTS_PATH = "/open_api/v1.3/business/comment/list/"
REPLIES_PATH = "/open_api/v1.3/business/comment/reply/list/"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PAGE_SIZE = 30
MAX_REQUESTS_PER_MINUTE = 60
VIDEO_ID_PATTERN = re.compile(r"^[0-9]{8,24}$")

app = FastAPI(
    title="StickerDrop TikTok Business Source",
    version="1.0.0",
    description=(
        "Read-only bridge to TikTok API for Business comments on videos owned "
        "by the connected account."
    ),
)


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_url: str = Field(min_length=12, max_length=2048)
    cursor: int = Field(default=0, ge=0)
    count: int = Field(default=30, ge=1, le=100)

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value: str) -> str:
        extract_video_id(value)
        return value


class ReplyRequest(SourceRequest):
    comment_id: str = Field(min_length=1, max_length=64)


class TikTokBusinessSourceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


_request_times: Deque[float] = deque()
_http_transport: Optional[httpx.AsyncBaseTransport] = None


def extract_video_id(video_url: str) -> str:
    """Extract a canonical video/photo ID; never fetch or resolve the URL."""
    if not isinstance(video_url, str) or len(video_url) > 2048:
        raise ValueError("video_url is invalid")
    try:
        parsed = urlsplit(video_url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ValueError("video_url is invalid") from exc

    if (
        parsed.scheme.lower() != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not (host == "tiktok.com" or host.endswith(".tiktok.com"))
    ):
        raise ValueError("video_url must be a canonical HTTPS TikTok URL")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 3 or segments[-2] != "video":
        raise ValueError("TikTok Business comments connector currently supports /video/<id> posts only")
    video_id = segments[-1]
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError("video_url contains an invalid video ID")
    return video_id


def _settings() -> Tuple[str, str, str]:
    token = os.getenv("TIKTOK_BUSINESS_ACCESS_TOKEN", "").strip()
    business_id = os.getenv("TIKTOK_BUSINESS_ID", "").strip()
    source_key = os.getenv("STICKERDROP_SOURCE_API_KEY", "")
    return token, business_id, source_key


def _require_source_key(authorization: Optional[str] = Header(default=None)) -> None:
    _, _, expected = _settings()
    if not expected:
        raise HTTPException(status_code=503, detail={"error_code": "SOURCE_NOT_CONFIGURED"})
    supplied = authorization or ""
    prefix = "Bearer "
    if not supplied.startswith(prefix):
        raise HTTPException(status_code=401, detail={"error_code": "SOURCE_AUTH_REQUIRED"})
    candidate = supplied[len(prefix):]
    if not hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail={"error_code": "SOURCE_AUTH_REJECTED"})


def _consume_rate_limit() -> None:
    now = time.monotonic()
    cutoff = now - 60.0
    while _request_times and _request_times[0] <= cutoff:
        _request_times.popleft()
    if len(_request_times) >= MAX_REQUESTS_PER_MINUTE:
        raise TikTokBusinessSourceError(
            "SOURCE_RATE_LIMITED", "The source bridge is temporarily rate limited.", 429
        )
    _request_times.append(now)


def _normalize_comment(row: Dict[str, Any]) -> Dict[str, Any]:
    comment_id = str(row.get("comment_id") or row.get("id") or "")
    image_url = row.get("image_url")
    user: Dict[str, Any] = {
        "uid": str(row.get("unique_identifier") or row.get("user_id") or ""),
        "unique_id": str(row.get("username") or "anonymous"),
        "nickname": str(row.get("display_name") or row.get("username") or "anonymous"),
    }
    profile_image = row.get("profile_image")
    if isinstance(profile_image, str) and profile_image.startswith("https://"):
        user["avatar_thumb"] = {"url_list": [profile_image]}

    result: Dict[str, Any] = {
        "cid": comment_id,
        "id": comment_id,
        "text": str(row.get("text") or ""),
        "create_time": row.get("create_time") or 0,
        "digg_count": row.get("likes") or 0,
        "reply_comment_total": row.get("replies") or 0,
        "user": user,
        "source": "tiktok_business_api",
    }
    parent_id = row.get("parent_comment_id")
    if parent_id not in (None, ""):
        result["parent_comment_id"] = str(parent_id)

    # The official API documents image_url for comments that are images.
    # Preserve it as a comment picture only. Do not invent sticker metadata.
    if isinstance(image_url, str) and image_url.startswith("https://"):
        result["comment_pics"] = [{"uri": comment_id, "url_list": [image_url]}]
        result["source_media_kind"] = "comment_image"

    raw_replies = row.get("reply_list")
    if isinstance(raw_replies, list):
        result["reply_comment"] = [
            _normalize_comment(reply)
            for reply in raw_replies
            if isinstance(reply, dict)
        ]
    return result


async def _call_tiktok(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    token, business_id, _ = _settings()
    if not token or not business_id:
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_NOT_CONFIGURED",
            "TikTok Business access token and business ID are required.",
            503,
        )

    _consume_rate_limit()
    headers = {
        "Access-Token": token,
        "Accept": "application/json",
        "User-Agent": "StickerDrop-TikTok-Business-Source/1.0",
    }
    options: Dict[str, Any] = {
        "timeout": float(os.getenv("TIKTOK_BUSINESS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
        "follow_redirects": False,
    }
    if _http_transport is not None:
        options["transport"] = _http_transport

    try:
        async with httpx.AsyncClient(**options) as client:
            async with client.stream(
                "GET", f"{TIKTOK_API_ORIGIN}{path}", params=params, headers=headers
            ) as response:
                if response.status_code in {401, 403}:
                    raise TikTokBusinessSourceError(
                        "TIKTOK_BUSINESS_AUTH_REJECTED",
                        "TikTok rejected the account authorization or required permission.",
                        502,
                    )
                if response.status_code == 429:
                    raise TikTokBusinessSourceError(
                        "TIKTOK_BUSINESS_RATE_LIMITED",
                        "TikTok Business API rate limit was reached.",
                        503,
                    )
                if 300 <= response.status_code < 400:
                    raise TikTokBusinessSourceError(
                        "TIKTOK_BUSINESS_REDIRECT_REJECTED",
                        "TikTok API returned a redirect; redirects are disabled.",
                        502,
                    )
                if response.status_code >= 400:
                    raise TikTokBusinessSourceError(
                        "TIKTOK_BUSINESS_REQUEST_FAILED",
                        f"TikTok Business API returned HTTP {response.status_code}.",
                        502,
                    )
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type != "application/json" and not content_type.endswith("+json"):
                    raise TikTokBusinessSourceError(
                        "TIKTOK_BUSINESS_INVALID_CONTENT_TYPE",
                        "TikTok Business API did not return JSON.",
                        502,
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise TikTokBusinessSourceError(
                            "TIKTOK_BUSINESS_RESPONSE_TOO_LARGE",
                            "TikTok Business API response exceeded the size limit.",
                            502,
                        )
        payload = json.loads(bytes(body).decode("utf-8"))
    except TikTokBusinessSourceError:
        raise
    except httpx.TimeoutException:
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_TIMEOUT", "TikTok Business API request timed out.", 504
        ) from None
    except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError):
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_NETWORK_ERROR", "Could not read TikTok Business API response.", 502
        ) from None

    if not isinstance(payload, dict):
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_INVALID_RESPONSE", "TikTok Business API response was not an object.", 502
        )
    code = payload.get("code")
    if str(code) != "0":
        # Never include arbitrary upstream message/body in public responses.
        if str(code) in {"40100", "40101", "40102"}:
            err_code = "TIKTOK_BUSINESS_AUTH_REJECTED"
            message = "TikTok rejected the account authorization or required permission."
        else:
            err_code = "TIKTOK_BUSINESS_UPSTREAM_ERROR"
            message = "TikTok Business API reported an upstream error."
        raise TikTokBusinessSourceError(err_code, message, 502)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_INVALID_RESPONSE", "TikTok Business API data was malformed.", 502
        )
    return data


def _normalize_page(data: Dict[str, Any]) -> Dict[str, Any]:
    raw_comments = data.get("comments")
    if raw_comments is None:
        raw_comments = data.get("replies")
    if not isinstance(raw_comments, list):
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_INVALID_RESPONSE", "TikTok Business API comment list was malformed.", 502
        )
    has_more = data.get("has_more")
    if not isinstance(has_more, bool):
        raise TikTokBusinessSourceError(
            "TIKTOK_BUSINESS_INVALID_RESPONSE", "TikTok Business API pagination metadata was missing.", 502
        )
    cursor = data.get("cursor") if has_more else None
    return {
        "comments": [_normalize_comment(row) for row in raw_comments if isinstance(row, dict)],
        "has_more": has_more,
        "cursor": cursor,
    }


def _exception_response(exc: TikTokBusinessSourceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"error_code": exc.code, "message": exc.message},
        headers={"Retry-After": "60"} if exc.status_code in {429, 503} else None,
    )


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"service": "stickerdrop-tiktok-business-source", "healthy": True}


@app.get("/v1/status", dependencies=[Depends(_require_source_key)])
async def status() -> Dict[str, Any]:
    token, business_id, source_key = _settings()
    configured = bool(token and business_id and source_key)
    return {
        "provider": "tiktok_business_api",
        "configured": configured,
        "ready": configured,
        "external_credit_provider": False,
        "access_token_present": bool(token),
        "business_id_present": bool(business_id),
        "source_key_present": bool(source_key),
        "supported_scope": "owned_videos_only",
        "media_semantics": "official_comment_image_url_when_present",
    }


@app.post("/v1/comments", dependencies=[Depends(_require_source_key)])
async def comments(payload: SourceRequest) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(payload.video_url)
        _, business_id, _ = _settings()
        data = await _call_tiktok(
            COMMENTS_PATH,
            {
                "business_id": business_id,
                "video_id": video_id,
                "status": "PUBLIC",
                "sort_field": "create_time",
                "sort_order": "desc",
                "cursor": payload.cursor,
                "max_count": min(payload.count, MAX_PAGE_SIZE),
                "include_replies": "true",
            },
        )
        return _normalize_page(data)
    except TikTokBusinessSourceError as exc:
        raise _exception_response(exc) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "INVALID_TIKTOK_VIDEO_URL", "message": str(exc)}) from None


@app.post("/v1/replies", dependencies=[Depends(_require_source_key)])
async def replies(payload: ReplyRequest) -> Dict[str, Any]:
    if not payload.comment_id.isdigit():
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_COMMENT_ID", "message": "comment_id must contain digits only."},
        )
    try:
        video_id = extract_video_id(payload.video_url)
        _, business_id, _ = _settings()
        data = await _call_tiktok(
            REPLIES_PATH,
            {
                "business_id": business_id,
                "video_id": video_id,
                "comment_id": payload.comment_id,
                "status": "PUBLIC",
                "sort_field": "create_time",
                "sort_order": "desc",
                "cursor": payload.cursor,
                "max_count": MAX_PAGE_SIZE,
            },
        )
        return _normalize_page(data)
    except TikTokBusinessSourceError as exc:
        raise _exception_response(exc) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "INVALID_TIKTOK_VIDEO_URL", "message": str(exc)}) from None
