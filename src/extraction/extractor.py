"""
Sticker Extraction Coordinator for StickerDrop.
Orchestrates link resolution, provider querying, pagination, and media downloading.
"""

from typing import Optional
import hashlib
import urllib.request

from ..link_resolver.resolver import TikTokLinkResolver, ResolvedTarget
from .models import ExtractionResult, CommentRecord, StickerMedia
from .adapter import ExtractionProviderAdapter


class StickerExtractor:
    """
    Coordinates end-to-end comment and sticker extraction.
    """

    def __init__(
        self,
        provider_adapter: ExtractionProviderAdapter,
        link_resolver: Optional[TikTokLinkResolver] = None,
        max_pagination_pages: int = 5
    ):
        self.provider = provider_adapter
        self.resolver = link_resolver or TikTokLinkResolver()
        self.max_pages = max_pagination_pages

    def download_media(self, media_url: str, timeout: float = 15.0) -> bytes:
        """Downloads raw media bytes from TikTok CDN with standard headers."""
        req = urllib.request.Request(
            media_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def extract_from_url(
        self,
        raw_url: str,
        download_media: bool = True
    ) -> ExtractionResult:
        """
        Extracts comment and sticker from a raw TikTok link.
        """
        # Step 1: Resolve Link
        try:
            target = self.resolver.parse_url(raw_url)
        except Exception as e:
            return ExtractionResult(
                success=False,
                target_comment_id="",
                video_id="",
                error_message=f"Link resolution error: {str(e)}"
            )

        if not target.comment_id:
            return ExtractionResult(
                success=False,
                target_comment_id="",
                video_id=target.video_id,
                error_message="The provided link is for a video, not a comment. Please copy a comment link."
            )

        return self.extract_by_ids(
            video_id=target.video_id,
            comment_id=target.comment_id,
            canonical_url=target.canonical_url,
            download_media=download_media
        )

    def extract_by_ids(
        self,
        video_id: str,
        comment_id: str,
        canonical_url: str,
        download_media: bool = True
    ) -> ExtractionResult:
        """
        Finds the target comment via the provider and downloads its sticker media.
        """
        matched_comment: Optional[CommentRecord] = None
        cursor = 0
        pages_checked = 0

        # Phase 1: Search top-level comments with cursor pagination
        while pages_checked < self.max_pages:
            try:
                comments, next_cursor, has_more = self.provider.fetch_video_comments(
                    video_url=canonical_url,
                    cursor=cursor
                )
            except Exception as e:
                return ExtractionResult(
                    success=False,
                    target_comment_id=comment_id,
                    video_id=video_id,
                    error_message=f"Provider API error: {str(e)}"
                )

            for c in comments:
                if str(c.cid) == str(comment_id):
                    matched_comment = c
                    break

            if matched_comment or not has_more or next_cursor is None:
                break

            cursor = next_cursor
            pages_checked += 1

        # Phase 2: If not found in top-level comments, search comment replies thread
        if not matched_comment:
            try:
                replies, _, _ = self.provider.fetch_comment_replies(
                    comment_id=comment_id,
                    video_url=canonical_url
                )
                for r in replies:
                    if str(r.cid) == str(comment_id):
                        matched_comment = r
                        break
            except Exception:
                pass  # Fall through to not found handling

        if not matched_comment:
            return ExtractionResult(
                success=False,
                target_comment_id=comment_id,
                video_id=video_id,
                error_message=f"Comment ID {comment_id} was not found in the first {pages_checked+1} comment pages or reply threads."
            )

        if not matched_comment.sticker:
            return ExtractionResult(
                success=True,
                target_comment_id=comment_id,
                video_id=video_id,
                comment=matched_comment,
                has_sticker=False,
                error_message="Comment located successfully, but does not contain an attached sticker."
            )

        # Phase 3: Download media asset if requested
        media_bytes = None
        sha256 = None
        media_format = "awebp" if matched_comment.sticker.is_animated else "webp"

        if download_media and matched_comment.sticker.best_url:
            try:
                media_bytes = self.download_media(matched_comment.sticker.best_url)
                sha256 = hashlib.sha256(media_bytes).hexdigest()
            except Exception as e:
                return ExtractionResult(
                    success=False,
                    target_comment_id=comment_id,
                    video_id=video_id,
                    comment=matched_comment,
                    has_sticker=True,
                    error_message=f"Failed to download sticker media from CDN: {str(e)}"
                )

        return ExtractionResult(
            success=True,
            target_comment_id=comment_id,
            video_id=video_id,
            comment=matched_comment,
            has_sticker=True,
            media_bytes=media_bytes,
            media_format=media_format,
            sha256=sha256,
            provider=self.provider.__class__.__name__
        )
