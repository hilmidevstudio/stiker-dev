"""
Extraction Provider Adapter Interface and Implementations for the StickerDrop backend service.
Manages API key authentication via environment variables (.env) for ScrapeSocial and ScrapeCreators.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple, List
import os
import httpx
from dotenv import load_dotenv

from .schemas import StickerMediaResponse, CommentAuthorResponse

# Load environment variables from .env
load_dotenv()


# Domain Exceptions
class ExtractionException(Exception):
    """Base exception for extraction errors."""
    def __init__(self, message: str, error_code: str = "EXTRACTION_ERROR", status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class ProviderAuthException(ExtractionException):
    """Raised when third-party API credentials are missing, invalid, or unauthorized."""
    def __init__(self, message: str = "Extraction provider authentication failed. Check API key configuration."):
        super().__init__(message, error_code="PROVIDER_AUTH_ERROR", status_code=500)


class CommentNotFoundException(ExtractionException):
    """Raised when the specified comment ID cannot be found in the video comment thread."""
    def __init__(self, comment_id: str):
        super().__init__(
            f"Comment ID '{comment_id}' was not found in the video comments or replies.",
            error_code="COMMENT_NOT_FOUND",
            status_code=404
        )


class StickerNotFoundException(ExtractionException):
    """Raised when the target comment exists, but has no attached sticker."""
    def __init__(self, comment_id: str):
        super().__init__(
            f"Comment '{comment_id}' was found, but does not contain an attached sticker (cmt_sticker_struct is absent).",
            error_code="STICKER_NOT_FOUND",
            status_code=404
        )


class ExtractorAdapter(ABC):
    """
    Abstract interface for TikTok comment extraction providers.
    """

    @abstractmethod
    async def fetch_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Dict[str, Any]:
        """Fetches top-level comments for a video."""
        pass

    @abstractmethod
    async def fetch_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Dict[str, Any]:
        """Fetches replies attached to a specific comment ID."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the extraction service."""
        pass

    def parse_sticker(self, comment_dict: Dict[str, Any]) -> Optional[StickerMediaResponse]:
        """
        Extracts clean sticker metadata from TikTok's internal cmt_sticker_struct.
        """
        sticker_struct = comment_dict.get("cmt_sticker_struct")
        if not sticker_struct or not isinstance(sticker_struct, dict):
            return None

        sticker_id = str(sticker_struct.get("sticker_id", ""))
        sticker_type = int(sticker_struct.get("sticker_type", 1))

        # Extract Static URL
        static_url = None
        static_obj = sticker_struct.get("static_url")
        if isinstance(static_obj, dict):
            url_list = static_obj.get("url_list", [])
            if url_list and isinstance(url_list, list):
                static_url = url_list[0]

        # Extract Animated URL
        animated_url = None
        animated_obj = sticker_struct.get("animated_url")
        if isinstance(animated_obj, dict):
            url_list = animated_obj.get("url_list", [])
            if url_list and isinstance(url_list, list):
                animated_url = url_list[0]

        is_animated = bool(animated_url) or sticker_type == 2

        # Extract Dimensions
        width = None
        height = None
        if static_obj and isinstance(static_obj, dict):
            width = static_obj.get("width")
            height = static_obj.get("height")
        elif animated_obj and isinstance(animated_obj, dict):
            width = animated_obj.get("width")
            height = animated_obj.get("height")

        # Determine best direct media URL
        media_url = animated_url if (is_animated and animated_url) else (static_url or "")
        format_type = "awebp" if is_animated else "webp"

        return StickerMediaResponse(
            sticker_id=sticker_id,
            sticker_type=sticker_type,
            is_animated=is_animated,
            format=format_type,
            media_url=media_url,
            static_url=static_url,
            animated_url=animated_url,
            width=width,
            height=height
        )

    def parse_author(self, comment_dict: Dict[str, Any]) -> CommentAuthorResponse:
        """Constructs normalized CommentAuthorResponse from comment dict."""
        user = comment_dict.get("user") or {}
        avatar_url = None
        avatar_obj = user.get("avatar_thumb")
        if isinstance(avatar_obj, dict):
            urls = avatar_obj.get("url_list", [])
            if urls and isinstance(urls, list):
                avatar_url = urls[0]

        return CommentAuthorResponse(
            uid=str(user.get("uid", "")),
            unique_id=user.get("unique_id", "anonymous"),
            nickname=user.get("nickname", "anonymous"),
            avatar_url=avatar_url
        )


class ScrapeSocialAdapter(ExtractorAdapter):
    """
    Adapter implementation for ScrapeSocial (api.scrapesocial.ai).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0
    ):
        self.api_key = api_key or os.getenv("SCRAPESOCIAL_API_KEY")
        self.base_url = (base_url or os.getenv("SCRAPESOCIAL_BASE_URL", "https://api.scrapesocial.ai")).rstrip("/")
        self.timeout = timeout_seconds

        if not self.api_key:
            # Note: We do not fail immediately in __init__ to allow lazy checking or mock fallback
            pass

    @property
    def provider_name(self) -> str:
        return "ScrapeSocial"

    def _ensure_api_key(self):
        if not self.api_key:
            raise ProviderAuthException(
                "SCRAPESOCIAL_API_KEY is not set in environment or .env file."
            )

    async def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_api_key()
        headers = {
            "x-api-key": self.api_key,
            "User-Agent": "StickerDrop-Backend/1.0",
            "Accept": "application/json"
        }
        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 401 or resp.status_code == 403:
                    raise ProviderAuthException(
                        f"ScrapeSocial authentication rejected (HTTP {resp.status_code}): {resp.text}"
                    )
                if resp.status_code >= 400:
                    raise ExtractionException(
                        f"ScrapeSocial API returned HTTP {resp.status_code}: {resp.text}",
                        status_code=502
                    )
                return resp.json()
        except httpx.TimeoutException:
            raise ExtractionException(
                "Timed out waiting for response from extraction provider.",
                error_code="PROVIDER_TIMEOUT",
                status_code=504
            )
        except (ExtractionException, ProviderAuthException):
            raise
        except Exception as e:
            raise ExtractionException(f"Network error connecting to extraction provider: {str(e)}")

    async def fetch_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Dict[str, Any]:
        params = {"url": video_url, "cursor": cursor, "count": count}
        return await self._get("/v1/tiktok/video/comments", params)

    async def fetch_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Dict[str, Any]:
        params = {"comment_id": comment_id, "url": video_url, "cursor": cursor}
        return await self._get("/v1/tiktok/video/comment/replies", params)


class ScrapeCreatorsAdapter(ScrapeSocialAdapter):
    """
    Adapter implementation for ScrapeCreators (api.scrapecreators.com).
    Shares the identical REST routing structure with ScrapeSocial.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0
    ):
        key = api_key or os.getenv("SCRAPECREATORS_API_KEY")
        url = base_url or os.getenv("SCRAPECREATORS_BASE_URL", "https://api.scrapecreators.com")
        super().__init__(api_key=key, base_url=url, timeout_seconds=timeout_seconds)

    @property
    def provider_name(self) -> str:
        return "ScrapeCreators"

    def _ensure_api_key(self):
        if not self.api_key:
            raise ProviderAuthException(
                "SCRAPECREATORS_API_KEY is not set in environment or .env file."
            )


class MockExtractorAdapter(ExtractorAdapter):
    """
    Deterministic Mock Adapter containing the verified research test case:
    Comment ID: 7708394712596972308 (Author: @crazyolshop1, Prabowo red shirt sticker).
    Ideal for testing and offline development.
    """

    def __init__(self, custom_fixtures: Optional[List[Dict[str, Any]]] = None):
        self.fixtures = custom_fixtures if custom_fixtures is not None else [
            {
                "cid": "7708394712596972308",
                "aweme_id": "7708356144804236564",
                "text": "ngajak ribut kamu? 🗿",
                "create_time": 1731600000,
                "digg_count": 88,
                "user": {
                    "uid": "7435664412436120631",
                    "nickname": "crazyolshop1",
                    "unique_id": "crazyolshop1",
                    "avatar_thumb": {
                        "url_list": [
                            "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/7435664412436120631.webp"
                        ]
                    }
                },
                "cmt_sticker_struct": {
                    "sticker_id": "7421890123456789012",
                    "sticker_type": 2,
                    "static_url": {
                        "url_list": [
                            "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/prabowo_static.webp"
                        ],
                        "width": 300,
                        "height": 300
                    },
                    "animated_url": {
                        "url_list": [
                            "https://p16-sign-useastdict.tiktokcdn.com/tos-maliva-i-photomode-us/prabowo_animated.awebp"
                        ],
                        "width": 300,
                        "height": 300
                    }
                }
            },
            {
                "cid": "7708111111111111111",
                "aweme_id": "7708356144804236564",
                "text": "Komentar teks biasa tanpa stiker",
                "create_time": 1731600100,
                "digg_count": 12,
                "user": {
                    "uid": "9999999999999999999",
                    "nickname": "penonton_setia",
                    "unique_id": "penonton_setia"
                }
            }
        ]

    @property
    def provider_name(self) -> str:
        return "MockProvider"

    async def fetch_comments(
        self, video_url: str, cursor: int = 0, count: int = 50
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "has_more": False,
            "cursor": None,
            "comments": self.fixtures
        }

    async def fetch_replies(
        self, comment_id: str, video_url: str, cursor: int = 0
    ) -> Dict[str, Any]:
        matching = [c for c in self.fixtures if str(c.get("cid")) == str(comment_id)]
        return {
            "success": True,
            "has_more": False,
            "cursor": None,
            "comments": matching
        }


def get_extractor_adapter(provider_name: Optional[str] = None) -> ExtractorAdapter:
    """
    Factory function to instantiate the appropriate adapter based on environment
    or explicit parameter override.
    """
    target = (provider_name or os.getenv("EXTRACTION_PROVIDER") or "").lower().strip()

    if target == "mock":
        return MockExtractorAdapter()
    elif target == "scrapecreators":
        return ScrapeCreatorsAdapter()
    elif target == "scrapesocial":
        return ScrapeSocialAdapter()
    else:
        # Default: check if ScrapeSocial or ScrapeCreators key exists
        if os.getenv("SCRAPESOCIAL_API_KEY"):
            return ScrapeSocialAdapter()
        elif os.getenv("SCRAPECREATORS_API_KEY"):
            return ScrapeCreatorsAdapter()
        else:
            # If no API key configured, use MockExtractorAdapter so the backend remains testable
            return MockExtractorAdapter()
