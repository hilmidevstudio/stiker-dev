"""Provider-neutral exact-comment discovery with bounded cursor pagination.

This module deliberately knows nothing about provider credentials or HTTP routes.
Any approved source adapter implementing fetch_comments/fetch_replies can be used.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
import os
from typing import Any, Dict, List, Optional, Protocol, Tuple
from .extractor_adapter import ExtractionException


class CommentPageAdapter(Protocol):
    async def fetch_comments(self, video_url: str, cursor: Any = 0, count: int = 50) -> Dict[str, Any]: ...
    async def fetch_replies(self, comment_id: str, video_url: str, cursor: Any = 0) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class DiscoveryLimits:
    max_comment_pages: int = 10
    max_reply_parents: int = 10
    max_reply_pages_per_parent: int = 5

    @classmethod
    def from_environment(cls) -> "DiscoveryLimits":
        def read(name: str, default: int) -> int:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
            return value
        values = {
            "max_comment_pages": read("STICKERDROP_MAX_COMMENT_PAGES", 10),
            "max_reply_parents": read("STICKERDROP_MAX_REPLY_PARENTS", 10),
            "max_reply_pages_per_parent": read("STICKERDROP_MAX_REPLY_PAGES", 5),
        }
        ceilings = {
            "max_comment_pages": 100,
            "max_reply_parents": 500,
            "max_reply_pages_per_parent": 50,
        }
        for key, value in values.items():
            if value > ceilings[key]:
                raise ValueError(f"{key} cannot exceed hard safety ceiling {ceilings[key]}")
        return cls(**values)


@dataclass
class DiscoveryStats:
    comment_pages: int = 0
    reply_pages: int = 0
    reply_parents_checked: int = 0
    reply_parents_discovered: int = 0
    complete: bool = True
    matched_in: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryResult:
    comment: Optional[Dict[str, Any]]
    stats: DiscoveryStats


class CommentSearchIncompleteException(ExtractionException):
    def __init__(self, stats: DiscoveryStats):
        super().__init__(
            "The exact comment was not found before the configured search budget was reached. "
            "The search is incomplete; this does not prove that the comment is absent.",
            error_code="COMMENT_SEARCH_INCOMPLETE",
            status_code=503,
            details=stats.to_dict(),
        )


def _comment_id(comment: Dict[str, Any]) -> str:
    return str(comment.get("cid") or comment.get("id") or comment.get("comment_id") or "")


def _author_id(comment: Dict[str, Any]) -> str:
    user = comment.get("user") or comment.get("author") or {}
    if not isinstance(user, dict):
        user = {}
    return str(user.get("uid") or user.get("user_id") or comment.get("user_id") or comment.get("author_id") or "")


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _next_cursor(response: Dict[str, Any], current: Any, seen: set[str]) -> Tuple[bool, Any]:
    if not bool(response.get("has_more", False)):
        return False, None
    candidate = response.get("cursor")
    if candidate is None:
        return False, None
    key = str(candidate)
    if key == str(current) or key in seen:
        return False, None
    return True, candidate


class CommentDiscoveryEngine:
    """Find one exact comment across top-level pages and candidate reply threads."""

    def __init__(self, limits: Optional[DiscoveryLimits] = None):
        self.limits = limits or DiscoveryLimits.from_environment()

    @staticmethod
    def _scan_comment_and_previews(comments, target_comment_id, target_author_id):
        candidates: Dict[str, Dict[str, Any]] = {}
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            if _comment_id(comment) == target_comment_id:
                return comment, list(candidates.values())

            previews = comment.get("reply_comment") or []
            if isinstance(previews, dict):
                previews = [previews]
            if not isinstance(previews, list):
                previews = []

            author_hint_match = False
            for reply in previews:
                if not isinstance(reply, dict):
                    continue
                if _comment_id(reply) == target_comment_id:
                    return reply, list(candidates.values())
                if target_author_id and _author_id(reply) == target_author_id:
                    author_hint_match = True

            parent_id = _comment_id(comment)
            reply_total = _as_int(comment.get("reply_comment_total"))
            if parent_id and (reply_total > 0 or previews):
                old = candidates.get(parent_id, {})
                candidates[parent_id] = {
                    "comment_id": parent_id,
                    "reply_total": max(reply_total, len(previews), old.get("reply_total", 0)),
                    "author_hint_match": author_hint_match or old.get("author_hint_match", False),
                }

        ordered = list(candidates.values())
        ordered.sort(key=lambda item: (not item["author_hint_match"], -item["reply_total"]))
        return None, ordered

    async def find_comment(
        self,
        adapter: CommentPageAdapter,
        *,
        video_url: str,
        target_comment_id: str,
        target_author_id: Optional[str] = None,
    ) -> DiscoveryResult:
        stats = DiscoveryStats()
        parent_candidates: Dict[str, Dict[str, Any]] = {}
        cursor: Any = 0
        seen_comment_cursors = {str(cursor)}
        comment_pages_exhausted = False

        # Phase 1: follow every available top-level cursor page within the cap.
        for _ in range(self.limits.max_comment_pages):
            response = await adapter.fetch_comments(video_url=video_url, cursor=cursor, count=50)
            stats.comment_pages += 1
            comments = response.get("comments") or []
            if not isinstance(comments, list):
                comments = []

            match, candidates = self._scan_comment_and_previews(
                comments, target_comment_id, target_author_id
            )
            for candidate in candidates:
                key = candidate["comment_id"]
                previous = parent_candidates.get(key)
                if previous:
                    candidate["reply_total"] = max(candidate["reply_total"], previous["reply_total"])
                    candidate["author_hint_match"] = candidate["author_hint_match"] or previous["author_hint_match"]
                parent_candidates[key] = candidate

            if match:
                stats.matched_in = "top_level_or_reply_preview"
                stats.reply_parents_discovered = len(parent_candidates)
                return DiscoveryResult(match, stats)

            can_continue, next_cursor = _next_cursor(response, cursor, seen_comment_cursors)
            if not can_continue:
                if bool(response.get("has_more", False)):
                    stats.complete = False
                else:
                    comment_pages_exhausted = True
                break
            cursor = next_cursor
            seen_comment_cursors.add(str(cursor))
        else:
            stats.complete = False

        stats.reply_parents_discovered = len(parent_candidates)
        parents = list(parent_candidates.values())
        selected_parents = parents[: self.limits.max_reply_parents]
        if len(parents) > len(selected_parents):
            stats.complete = False

        # Phase 2: follow reply pagination for all selected candidate parents.
        for parent in selected_parents:
            parent_id = parent["comment_id"]
            stats.reply_parents_checked += 1
            reply_cursor: Any = 0
            seen_reply_cursors = {str(reply_cursor)}
            parent_finished = False

            for _ in range(self.limits.max_reply_pages_per_parent):
                try:
                    response = await adapter.fetch_replies(
                        comment_id=parent_id, video_url=video_url, cursor=reply_cursor
                    )
                except Exception:
                    stats.complete = False
                    parent_finished = True
                    break

                stats.reply_pages += 1
                replies = response.get("comments") or []
                if not isinstance(replies, list):
                    replies = []
                match, _ = self._scan_comment_and_previews(replies, target_comment_id, target_author_id)
                if match:
                    stats.matched_in = f"reply_thread:{parent_id}"
                    return DiscoveryResult(match, stats)

                can_continue, next_cursor = _next_cursor(response, reply_cursor, seen_reply_cursors)
                if not can_continue:
                    if bool(response.get("has_more", False)):
                        stats.complete = False
                    parent_finished = True
                    break
                reply_cursor = next_cursor
                seen_reply_cursors.add(str(reply_cursor))

            if not parent_finished:
                stats.complete = False

        if not parents and not comment_pages_exhausted and stats.comment_pages:
            stats.complete = False
        return DiscoveryResult(None, stats)
