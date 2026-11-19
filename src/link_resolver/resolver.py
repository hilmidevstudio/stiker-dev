"""
Link Resolver Module for StickerDrop.
Parses, resolves, normalizes, and extracts identifiers from TikTok URLs.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import re
import urllib.parse
import urllib.request


@dataclass
class ResolvedTarget:
    original_input: str
    canonical_url: str
    video_id: str
    comment_id: Optional[str]
    author_id: Optional[str]
    is_comment_link: bool
    raw_query_params: Dict[str, str]


class LinkResolverError(Exception):
    """Base exception for link resolution errors."""
    pass


class InvalidUrlError(LinkResolverError):
    """Raised when the input contains no valid HTTP/HTTPS URL."""
    pass


class VideoIdNotFoundError(LinkResolverError):
    """Raised when a TikTok Video ID cannot be extracted."""
    pass


class MissingCommentIdError(LinkResolverError):
    """Raised when the link is a valid TikTok video link, but contains no comment ID."""
    pass


class TikTokLinkResolver:
    """
    Resolves short URLs and extracts video/comment identifiers.
    """

    SHORT_DOMAINS = {
        "vt.tiktok.com",
        "vm.tiktok.com",
        "v.tiktok.com",
        "m.tiktok.com",
    }

    # Matches standard video paths: /@user/video/7708356144804236564 or /v/7708356144804236564.html
    VIDEO_PATH_REGEX = re.compile(r"/video/(\d+)|/v/(\d+)")

    URL_EXTRACT_REGEX = re.compile(r"(https?://[^\s\"'<>]+)")

    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"):
        self.user_agent = user_agent

    def extract_url_from_text(self, text: str) -> str:
        """Extracts the first HTTP/HTTPS URL found in freeform text."""
        if not text:
            raise InvalidUrlError("Input text is empty.")
        match = self.URL_EXTRACT_REGEX.search(text)
        if not match:
            raise InvalidUrlError(f"No valid URL found in input: '{text[:80]}'")
        return match.group(1).strip()

    def resolve_redirect(self, url: str, timeout: float = 10.0) -> str:
        """
        Follows HTTP redirects to resolve short links (e.g. vt.tiktok.com).
        Returns the destination canonical URL.
        """
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent},
            method="HEAD"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.geturl()
        except urllib.error.HTTPError as e:
            # 301/302 redirects with HEAD may sometimes return redirect location in headers
            if "Location" in e.headers:
                return e.headers["Location"]
            # Fallback to GET if HEAD failed
            req.method = "GET"
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.geturl()
        except Exception as e:
            # If network resolution fails, return original url and try parsing it
            return url

    def parse_url(self, raw_input: str, follow_redirects: bool = True) -> ResolvedTarget:
        """
        Full resolution and parsing pipeline.
        """
        clean_url = self.extract_url_from_text(raw_input)
        parsed = urllib.parse.urlparse(clean_url)

        # Check if domain is a short domain
        is_short = parsed.netloc.lower() in self.SHORT_DOMAINS or parsed.path.startswith("/t/")
        target_url = clean_url

        if is_short and follow_redirects:
            target_url = self.resolve_redirect(clean_url)
            parsed = urllib.parse.urlparse(target_url)

        query_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        # Extract Video ID: from path or query params (share_item_id)
        video_id = None
        path_match = self.VIDEO_PATH_REGEX.search(parsed.path)
        if path_match:
            video_id = path_match.group(1) or path_match.group(2)
        elif "share_item_id" in query_params:
            video_id = query_params["share_item_id"]
        elif "item_id" in query_params:
            video_id = query_params["item_id"]

        if not video_id:
            raise VideoIdNotFoundError(f"Could not extract Video ID from URL: {target_url}")

        # Extract Comment ID from query parameters
        comment_id = None
        for key in ["share_comment_id", "comment_id", "cid"]:
            if key in query_params and query_params[key].isdigit():
                comment_id = query_params[key]
                break

        author_id = query_params.get("comment_author_id")

        return ResolvedTarget(
            original_input=raw_input,
            canonical_url=target_url,
            video_id=video_id,
            comment_id=comment_id,
            author_id=author_id,
            is_comment_link=comment_id is not None,
            raw_query_params=query_params
        )
