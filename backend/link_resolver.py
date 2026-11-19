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
    post_type: str = "video"  # TikTok may share either /video/ or /photo/ posts.


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

    # TikTok share links can resolve to both video and photo-mode posts.
    POST_PATH_REGEX = re.compile(r"/(?P<kind>video|photo|v)/(?P<id>\d+)")
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
        """Resolve TikTok short links with GET (not HEAD).

        TikTok's short-link service can treat HEAD differently from GET. Stream the
        response so the final landing page body is not downloaded unnecessarily.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                headers=headers,
            ) as client:
                async with client.stream("GET", url) as response:
                    final_url = str(response.url)
                    final_host = urllib.parse.urlparse(final_url).netloc.lower()
                    if final_host in self.SHORT_DOMAINS:
                        raise LinkResolverException(
                            "TikTok short link did not resolve to a post URL.",
                            error_code="SHORT_LINK_UNRESOLVED",
                            status_code=422,
                        )
                    return final_url
        except LinkResolverException:
            raise
        except httpx.TimeoutException:
            raise LinkResolverException(
                "Timed out while resolving TikTok short link. Please check your network or try again.",
                error_code="RESOLUTION_TIMEOUT",
                status_code=504,
            )
        except Exception as e:
            raise LinkResolverException(
                f"Could not resolve TikTok short link: {type(e).__name__}",
                error_code="SHORT_LINK_RESOLUTION_FAILED",
                status_code=502,
            )

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

        # 1. Extract the TikTok post ID and distinguish video from photo-mode posts.
        post_id = None
        post_type = "photo" if query_params.get("aweme_type") == "150" else "video"
        path_match = self.POST_PATH_REGEX.search(parsed.path)
        if path_match:
            post_id = path_match.group("id")
            post_type = "photo" if path_match.group("kind") == "photo" else "video"
        elif query_params.get("share_item_id", "").isdigit():
            post_id = query_params["share_item_id"]
        elif query_params.get("item_id", "").isdigit():
            post_id = query_params["item_id"]

        if not post_id:
            raise VideoIdNotFoundException(
                f"Could not extract a valid TikTok post ID from resolved URL: {canonical_url}"
            )

        # 2. Extract Comment ID (from share_comment_id, comment_id, or cid)
        comment_id = None
        for key in ["share_comment_id", "comment_id", "cid"]:
            val = query_params.get(key)
            if val and val.isdigit():
                comment_id = val
                break

        author_id = query_params.get("comment_author_id")

        # Keep the post kind in the canonical URL. Rewriting /photo/ to /video/
        # changes the resource being requested and can make comment lookups miss.
        path_parts = parsed.path.strip("/").split("/")
        author_handle = next((p for p in path_parts if p.startswith("@")), None)
        canonical_author = author_handle or "@tiktok"
        clean_canonical_url = f"https://www.tiktok.com/{canonical_author}/{post_type}/{post_id}"

        return ResolvedTarget(
            original_input=raw_input,
            canonical_url=clean_canonical_url,
            video_id=post_id,
            comment_id=comment_id,
            author_id=author_id,
            is_comment_link=comment_id is not None,
            query_params=query_params,
            post_type=post_type,
        )
