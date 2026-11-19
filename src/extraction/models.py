"""
Data models for TikTok comment and sticker extraction.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class CommentAuthor:
    uid: str
    nickname: str
    unique_id: str
    avatar_url: Optional[str] = None


@dataclass
class StickerMedia:
    sticker_id: str
    sticker_type: int  # 1 = static, 2 = animated
    is_animated: bool
    static_url: Optional[str] = None
    animated_url: Optional[str] = None
    best_url: str = ""
    width: Optional[int] = None
    height: Optional[int] = None

    def __post_init__(self):
        if not self.best_url:
            if self.is_animated and self.animated_url:
                self.best_url = self.animated_url
            elif self.static_url:
                self.best_url = self.static_url


@dataclass
class CommentRecord:
    cid: str
    aweme_id: str
    text: str
    create_time: int
    digg_count: int
    author: CommentAuthor
    sticker: Optional[StickerMedia] = None
    reply_id: Optional[str] = None
    reply_comment_total: int = 0
    raw_dict: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    success: bool
    target_comment_id: str
    video_id: str
    comment: Optional[CommentRecord] = None
    has_sticker: bool = False
    provider: str = "unknown"
    error_message: Optional[str] = None
    media_bytes: Optional[bytes] = None
    media_format: Optional[str] = None
    sha256: Optional[str] = None
