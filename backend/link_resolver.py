"""
TikTok Link Cleaner & Resolver for the StickerDrop backend service.
Handles short links (vt.tiktok.com, vm.tiktok.com), canonicalization,
and extraction of video_id and comment_id.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import re
import urllib.parse
import httpx


@dataclass
class ResolvedTarget:
    original_input: str
    canonical_url: str
    video_id: str
    comment_id: Optional[str]
    author_id: Optional[str]
    is_comment_link: bool
    query_params: Dict[str, str]


# Domain Exceptions
class LinkResolverException(Exception):
    """Base exception for link resolution errors."""
    def __init__(self, message: str, error_code: str = "LINK_RESOLVER_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class InvalidUrlException(LinkResolverException):
    """Raised when the input string contains no valid HTTP/HTTPS URL."""
    def __init__(self, message: str = "The provided string does not contain a valid URL."):
        super().__init__(message, error_code="INVALID_URL", status_code=400)


class VideoIdNotFoundException(LinkResolverException):
    """Raised when a valid TikTok Video ID cannot be extracted."""
    def __init__(self, message: str = "Could not extract a valid TikTok Video ID from the link."):
        super().__init__(message, error_code="VIDEO_ID_NOT_FOUND", status_code=422)


class MissingCommentIdException(LinkResolverException):
    """Raised when the link is a valid TikTok video link, but does not point to a specific comment."""
    def __init__(
        self,
        message: str = "The link points to a TikTok video, but no comment identifier was found. Please long-press the comment and copy its specific link."
    ):
        super().__init__(message, error_code="MISSING_COMMENT_ID", status_code=422)


class TikTokLinkResolver:
    """
    Cleans, resolves redirects, and extracts identifiers from TikTok URLs.
    """

    SHORT_DOMAINS = {
        "vt.tiktok.com",
        "vm.tiktok.com",
        "v.tiktok.com",
        "m.tiktok.com",
    }

    # Matches /video/7708356144804236564 or /v/7708356144804236564.html
    VIDEO_PATH_REGEX = re.compile(r"/video/(\d+)|/v/(\d+)")
    URL_FINDER_REGEX = re.compile(r"(https?://[^\s\"'<>]+)")

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
    )

    def __init__(self, timeout_seconds: float = 10.0, user_agent: Optional[str] = None):
        self.timeout = timeout_seconds
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    def extract_url(self, raw_text: str) -> str:
        """
        Extracts the first HTTP/HTTPS URL from freeform text, stripping surrounding noise.
        Automatically normalizes missing protocols or truncated schemes (e.g. 'vt.tiktok.com' or 's://...').
        """
        if not raw_text or not raw_text.strip():
            raise InvalidUrlException("Empty input string provided.")

        cleaned = raw_text.strip()
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            if "tiktok.com" in cleaned:
                cleaned = "https://" + re.sub(r"^[a-zA-Z0-9]*://", "", cleaned).lstrip("/")

        match = self.URL_FINDER_REGEX.search(cleaned)
        if not match:
            raise InvalidUrlException(f"No HTTP or HTTPS URL detected in input: '{raw_text[:60]}'")

        return match.group(1).strip().rstrip("'\">),.;]")

    async def resolve_short_url(self, url: str) -> str:
        """
        Asynchronously follows HTTP redirects (301/302) to discover the canonical destination URL.
        """
        headers = {"User-Agent": self.user_agent}

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                headers=headers
            ) as client:
                response = await client.head(url)
                # If HEAD fails or is not supported by edge server, try GET
                if response.status_code >= 400:
                    response = await client.get(url)
                return str(response.url)
        except httpx.TimeoutException:
            raise LinkResolverException(
                "Timed out while resolving short URL redirect. Please check your network or try again.",
                error_code="RESOLUTION_TIMEOUT",
                status_code=504
            )
        except Exception as e:
            # If network resolution fails, return original url and attempt parsing
            return url

    async def resolve(self, raw_input: str, follow_redirects: bool = True) -> ResolvedTarget:
        """
        Full asynchronous link cleansing, redirect resolution, and parameter extraction.
        """
        clean_url = self.extract_url(raw_input)
        parsed = urllib.parse.urlparse(clean_url)

        # Check if URL belongs to short domains or /t/ path
        is_short_link = (
            parsed.netloc.lower() in self.SHORT_DOMAINS or
            parsed.path.startswith("/t/")
        )

        canonical_url = clean_url
        if is_short_link and follow_redirects:
            canonical_url = await self.resolve_short_url(clean_url)
            parsed = urllib.parse.urlparse(canonical_url)

        query_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        # 1. Extract Video ID (from path or fallback query parameters)
        video_id = None
        path_match = self.VIDEO_PATH_REGEX.search(parsed.path)
        if path_match:
            video_id = path_match.group(1) or path_match.group(2)
        elif "share_item_id" in query_params:
            video_id = query_params["share_item_id"]
        elif "item_id" in query_params:
            video_id = query_params["item_id"]

        if not video_id:
            raise VideoIdNotFoundException(
                f"Could not extract a valid TikTok Video ID from resolved URL: {canonical_url}"
            )

        # 2. Extract Comment ID (from share_comment_id, comment_id, or cid)
        comment_id = None
        for key in ["share_comment_id", "comment_id", "cid"]:
            val = query_params.get(key)
            if val and val.isdigit():
                comment_id = val
                break

        author_id = query_params.get("comment_author_id")

        # Extract authentic creator handle if present in path, else fallback to @tiktok
        path_parts = parsed.path.strip("/").split("/")
        author_handle = next((p for p in path_parts if p.startswith("@")), None)
        if author_handle:
            clean_canonical_url = f"https://www.tiktok.com/{author_handle}/video/{video_id}"
        else:
            clean_canonical_url = f"https://www.tiktok.com/@tiktok/video/{video_id}"

        return ResolvedTarget(
            original_input=raw_input,
            canonical_url=clean_canonical_url,
            video_id=video_id,
            comment_id=comment_id,
            author_id=author_id,
            is_comment_link=comment_id is not None,
            query_params=query_params
        )
