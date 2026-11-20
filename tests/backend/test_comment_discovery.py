import unittest

from backend.comment_discovery import (
    CommentDiscoveryEngine,
    CommentSearchIncompleteException,
    DiscoveryLimits,
)


class FakePagedAdapter:
    def __init__(self, comment_pages=None, reply_pages=None, reply_errors=None):
        self.comment_pages = comment_pages or {}
        self.reply_pages = reply_pages or {}
        self.reply_errors = reply_errors or set()
        self.comment_calls = []
        self.reply_calls = []

    async def fetch_comments(self, video_url, cursor=0, count=50):
        self.comment_calls.append(cursor)
        return self.comment_pages.get(cursor, {"comments": [], "has_more": False, "cursor": None})

    async def fetch_replies(self, comment_id, video_url, cursor=0):
        self.reply_calls.append((comment_id, cursor))
        if comment_id in self.reply_errors:
            raise RuntimeError("simulated source error")
        return self.reply_pages.get(
            (comment_id, cursor),
            {"comments": [], "has_more": False, "cursor": None},
        )


class TestCommentDiscoveryEngine(unittest.IsolatedAsyncioTestCase):
    async def test_follows_top_level_pagination_past_old_five_page_limit(self):
        pages = {
            0: {"comments": [], "has_more": True, "cursor": 20},
            20: {"comments": [], "has_more": True, "cursor": 40},
            40: {"comments": [], "has_more": True, "cursor": 60},
            60: {"comments": [], "has_more": True, "cursor": 80},
            80: {"comments": [], "has_more": True, "cursor": 100},
            100: {"comments": [{"cid": "target-6"}], "has_more": False, "cursor": None},
        }
        adapter = FakePagedAdapter(comment_pages=pages)
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=10, max_reply_parents=10, max_reply_pages_per_parent=5)
        ).find_comment(adapter, video_url="https://example.test/post", target_comment_id="target-6")

        self.assertEqual(result.comment["cid"], "target-6")
        self.assertEqual(result.stats.comment_pages, 6)
        self.assertEqual(adapter.comment_calls, [0, 20, 40, 60, 80, 100])

    async def test_searches_reply_parent_beyond_first_four_and_paginates_replies(self):
        parents = [
            {"cid": f"parent-{i}", "reply_comment_total": 5, "reply_comment": []}
            for i in range(1, 7)
        ]
        comment_pages = {0: {"comments": parents, "has_more": False, "cursor": None}}
        reply_pages = {
            ("parent-1", 0): {"comments": [], "has_more": False, "cursor": None},
            ("parent-2", 0): {"comments": [], "has_more": False, "cursor": None},
            ("parent-3", 0): {"comments": [], "has_more": False, "cursor": None},
            ("parent-4", 0): {"comments": [], "has_more": False, "cursor": None},
            ("parent-5", 0): {"comments": [], "has_more": True, "cursor": 10},
            ("parent-5", 10): {"comments": [{"cid": "target-reply"}], "has_more": False, "cursor": None},
        }
        adapter = FakePagedAdapter(comment_pages=comment_pages, reply_pages=reply_pages)
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=3, max_reply_parents=10, max_reply_pages_per_parent=5)
        ).find_comment(adapter, video_url="https://example.test/post", target_comment_id="target-reply")

        self.assertEqual(result.comment["cid"], "target-reply")
        self.assertEqual(result.stats.reply_parents_checked, 5)
        self.assertEqual(result.stats.reply_pages, 6)
        self.assertIn(("parent-5", 10), adapter.reply_calls)

    async def test_prioritizes_parent_with_target_author_preview(self):
        parents = [
            {"cid": "large-thread", "reply_comment_total": 100, "reply_comment": []},
            {"cid": "author-hint-thread", "reply_comment_total": 2,
             "reply_comment": [{"cid": "preview", "user": {"uid": "target-author"}}]},
        ]
        adapter = FakePagedAdapter(
            comment_pages={0: {"comments": parents, "has_more": False, "cursor": None}},
            reply_pages={
                ("author-hint-thread", 0): {
                    "comments": [{"cid": "target-reply"}],
                    "has_more": False,
                    "cursor": None,
                }
            },
        )
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=2, max_reply_parents=1, max_reply_pages_per_parent=2)
        ).find_comment(
            adapter,
            video_url="https://example.test/post",
            target_comment_id="target-reply",
            target_author_id="target-author",
        )

        self.assertEqual(result.comment["cid"], "target-reply")
        self.assertEqual(adapter.reply_calls[0][0], "author-hint-thread")

    async def test_reports_incomplete_when_comment_page_budget_is_reached(self):
        adapter = FakePagedAdapter(comment_pages={
            0: {"comments": [], "has_more": True, "cursor": 20},
            20: {"comments": [], "has_more": True, "cursor": 40},
        })
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=2, max_reply_parents=1, max_reply_pages_per_parent=1)
        ).find_comment(adapter, video_url="https://example.test/post", target_comment_id="missing")
        self.assertIsNone(result.comment)
        self.assertFalse(result.stats.complete)
        with self.assertRaises(CommentSearchIncompleteException):
            raise CommentSearchIncompleteException(result.stats)

    async def test_repeated_cursor_is_reported_as_incomplete_not_not_found(self):
        adapter = FakePagedAdapter(comment_pages={
            0: {"comments": [], "has_more": True, "cursor": 20},
            20: {"comments": [], "has_more": True, "cursor": 20},
        })
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=5, max_reply_parents=1, max_reply_pages_per_parent=1)
        ).find_comment(adapter, video_url="https://example.test/post", target_comment_id="missing")
        self.assertFalse(result.stats.complete)
        self.assertEqual(adapter.comment_calls, [0, 20])

    async def test_reply_source_error_marks_search_incomplete(self):
        adapter = FakePagedAdapter(
            comment_pages={0: {"comments": [{"cid": "parent", "reply_comment_total": 3}], "has_more": False}},
            reply_errors={"parent"},
        )
        result = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=2, max_reply_parents=2, max_reply_pages_per_parent=2)
        ).find_comment(adapter, video_url="https://example.test/post", target_comment_id="missing")
        self.assertFalse(result.stats.complete)
        self.assertEqual(result.stats.reply_parents_checked, 1)


if __name__ == "__main__":
    unittest.main()
