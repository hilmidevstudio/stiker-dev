"""
Pydantic v2 schemas for the StickerDrop backend service.
Defines input payloads, clean sticker output responses, and error contracts.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl


class ResolveAndExtractRequest(BaseModel):
    """Input payload for POST /v1/resolve-and-extract."""
    url: str = Field(
        ...,
        description="TikTok comment short link (e.g. vt.tiktok.com) or canonical comment URL",
        examples=["https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/"]
    )
    download_media: bool = Field(
        default=False,
        description="Whether the backend should also download and verify media bytes"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional provider override: 'scrapesocial', 'scrapecreators', or 'mock'"
    )


class CommentAuthorResponse(BaseModel):
    """Normalized comment author metadata."""
    uid: str
    unique_id: str
    nickname: str
    avatar_url: Optional[str] = None


class StickerMediaResponse(BaseModel):
    """Clean, client-facing sticker metadata extracted from cmt_sticker_struct."""
    sticker_id: str
    sticker_type: int = Field(description="1 = static, 2 = animated")
    is_animated: bool
    format: str = Field(description="awebp, webp, or png")
    media_url: str = Field(description="Highest quality direct CDN media URL")
    static_url: Optional[str] = None
    animated_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ResolveAndExtractResponse(BaseModel):
    """Successful extraction response."""
    success: bool = True
    message: str = "Sticker extracted successfully"
    video_id: str
    comment_id: str
    canonical_url: str
    comment_text: str
    create_time: int
    digg_count: int
    author: CommentAuthorResponse
    sticker: StickerMediaResponse
    provider_used: str
    sha256: Optional[str] = None


class ErrorDetail(BaseModel):
    """Structured error payload for global exception handling."""
    success: bool = False
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
