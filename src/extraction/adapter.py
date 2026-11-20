"""
Extraction Provider Adapters for StickerDrop.
Implements the Provider Adapter pattern for external scraping services.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
import urllib.request
import urllib.parse
import json

from .models import CommentRecord, CommentAuthor, StickerMedia


class ExtractionProviderAdapter(ABC):
    """Abstract base class for TikTok comment extraction providers."""

    @abstractmethod
    def fetch_video_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        """
        Fetches top-level comments for a video.
        Returns (comments_list, next_cursor, has_more).
        """
        pass

    @abstractmethod
    def fetch_comment_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        """
        Fetches replies attached to a specific comment.
        Returns (comments_list, next_cursor, has_more).
        """
        pass

    def parse_sticker(self, comment_dict: Dict[str, Any]) -> Optional[StickerMedia]:
        """
        Parses TikTok's cmt_sticker_struct if present in the comment dictionary.
        """
        sticker_struct = comment_dict.get("cmt_sticker_struct")
        if not sticker_struct or not isinstance(sticker_struct, dict):
            return None

        sticker_id = str(sticker_struct.get("sticker_id", ""))
        sticker_type = int(sticker_struct.get("sticker_type", 1))

        static_url = None
        static_obj = sticker_struct.get("static_url")
        if isinstance(static_obj, dict):
            url_list = static_obj.get("url_list", [])
            if url_list and isinstance(url_list, list):
                static_url = url_list[0]

        animated_url = None
        animated_obj = sticker_struct.get("animated_url")
        if isinstance(animated_obj, dict):
            url_list = animated_obj.get("url_list", [])
            if url_list and isinstance(url_list, list):
                animated_url = url_list[0]

        is_animated = bool(animated_url)

        width = None
        height = None
        if static_obj and isinstance(static_obj, dict):
            width = static_obj.get("width")
            height = static_obj.get("height")
        elif animated_obj and isinstance(animated_obj, dict):
            width = animated_obj.get("width")
            height = animated_obj.get("height")

        return StickerMedia(
            sticker_id=sticker_id,
            sticker_type=sticker_type,
            is_animated=is_animated,
            static_url=static_url,
            animated_url=animated_url,
            width=width,
            height=height
        )

    def parse_comment_record(self, item: Dict[str, Any]) -> CommentRecord:
        """Constructs a normalized CommentRecord from raw API dictionary."""
        cid = str(item.get("cid") or item.get("id") or "")
        aweme_id = str(item.get("aweme_id") or "")
        text = item.get("text", "")
        create_time = int(item.get("create_time", 0))
        digg_count = int(item.get("digg_count", 0))

        user_data = item.get("user") or {}
        author = CommentAuthor(
            uid=str(user_data.get("uid", "")),
            nickname=user_data.get("nickname", "anonymous"),
            unique_id=user_data.get("unique_id", "anonymous"),
            avatar_url=user_data.get("avatar_thumb", {}).get("url_list", [None])[0] if isinstance(user_data.get("avatar_thumb"), dict) else None
        )

        sticker = self.parse_sticker(item)
        reply_id = str(item.get("reply_id", "0"))
        reply_total = int(item.get("reply_comment_total", 0))

        return CommentRecord(
            cid=cid,
            aweme_id=aweme_id,
            text=text,
            create_time=create_time,
            digg_count=digg_count,
            author=author,
            sticker=sticker,
            reply_id=reply_id,
            reply_comment_total=reply_total,
            raw_dict=item
        )


class ScrapeSocialAdapter(ExtractionProviderAdapter):
    """
    Adapter for ScrapeSocial (api.scrapesocial.ai) REST API.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.scrapesocial.ai"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _execute_get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query_string = urllib.parse.urlencode(params)
        url = f"{self.base_url}{endpoint}?{query_string}"
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": self.api_key,
                "User-Agent": "StickerDrop-Core/1.0",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)

    def fetch_video_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        params = {"url": video_url, "cursor": cursor, "count": count}
        data = self._execute_get("/v1/tiktok/video/comments", params)
        raw_comments = data.get("comments") or []
        records = [self.parse_comment_record(c) for c in raw_comments]
        has_more = bool(data.get("has_more", False))
        next_cursor = data.get("cursor")
        return records, next_cursor, has_more

    def fetch_comment_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        params = {"comment_id": comment_id, "url": video_url, "cursor": cursor}
        data = self._execute_get("/v1/tiktok/video/comment/replies", params)
        raw_comments = data.get("comments") or []
        records = [self.parse_comment_record(c) for c in raw_comments]
        has_more = bool(data.get("has_more", False))
        next_cursor = data.get("cursor")
        return records, next_cursor, has_more


class ScrapeCreatorsAdapter(ScrapeSocialAdapter):
    """
    Adapter for ScrapeCreators (api.scrapecreators.com).
    Shares the identical REST routing structure with ScrapeSocial.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.scrapecreators.com"):
        super().__init__(api_key=api_key, base_url=base_url)


class MockExtractionAdapter(ExtractionProviderAdapter):
    """
    Deterministic mock adapter used for test suites and offline verification.
    """

    def __init__(self, fixture_comments: Optional[List[Dict[str, Any]]] = None):
        self.fixture_comments = fixture_comments or []

    def fetch_video_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        records = [self.parse_comment_record(c) for c in self.fixture_comments]
        return records, None, False

    def fetch_comment_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Tuple[List[CommentRecord], Optional[int], bool]:
        matching = [c for c in self.fixture_comments if str(c.get("cid")) == str(comment_id) or str(c.get("reply_id")) == str(comment_id)]
        records = [self.parse_comment_record(c) for c in matching]
        return records, None, False
