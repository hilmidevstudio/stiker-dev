import unittest
import os
from unittest.mock import AsyncMock


from backend.extractor_adapter import (
    ScrapeCreatorsAdapter,
    ScrapeSocialAdapter,
    DisabledExtractorAdapter,
    get_extractor_adapter,
)


class TestScrapeCreatorsAdapter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.adapter = ScrapeCreatorsAdapter(api_key="test-only-key")

    def test_animated_type_without_animated_url_is_not_mislabeled(self):
        comment = {
            "cid": "123",
            "cmt_sticker_struct": {
                "sticker_id": "sticker-123",
                "sticker_type": 2,
                "static_url": {
                    "url_list": ["https://cdn.example.test/sticker.webp"],
                    "width": 512,
                    "height": 512,
                },
            },
        }
        sticker = self.adapter.parse_sticker(comment)
        self.assertIsNotNone(sticker)
        self.assertFalse(sticker.is_animated)
        self.assertEqual(sticker.format, "webp")
        self.assertEqual(sticker.media_url, "https://cdn.example.test/sticker.webp")

    async def test_scrapecreators_comment_page_is_normalized_before_discovery(self):
        self.adapter._get = AsyncMock(return_value={
            "data": {
                "comments": [{"id": "comment-1", "reply_count": 2, "display_name": "Tester"}],
                "has_more": True,
                "cursor": 20,
            }
        })
        page = await self.adapter.fetch_comments("https://www.tiktok.com/@x/video/1", cursor=0)
        self.adapter._get.assert_awaited_once_with(
            "/v1/tiktok/video/comments",
            {"url": "https://www.tiktok.com/@x/video/1", "cursor": 0},
        )
        self.assertEqual(page["comments"][0]["cid"], "comment-1")
        self.assertEqual(page["comments"][0]["reply_comment_total"], 2)
        self.assertEqual(page["comments"][0]["user"]["nickname"], "Tester")
        self.assertTrue(page["has_more"])
        self.assertEqual(page["cursor"], 20)

    async def test_scrapesocial_reply_page_is_normalized_before_discovery(self):
        adapter = ScrapeSocialAdapter(api_key="test-only-key")
        adapter._get = AsyncMock(return_value={
            "result": {
                "reply_list": [{"comment_id": "reply-1", "user": {"uid": "u-1"}}],
                "hasMore": False,
                "cursor": 10,
            }
        })
        page = await adapter.fetch_replies("parent-1", "https://www.tiktok.com/@x/video/1")
        adapter._get.assert_awaited_once_with(
            "/v1/tiktok/video/comment/replies",
            {"comment_id": "parent-1", "url": "https://www.tiktok.com/@x/video/1", "cursor": 0},
        )
        self.assertEqual(page["comments"][0]["cid"], "reply-1")
        self.assertFalse(page["has_more"])
        self.assertIsNone(page["cursor"])


    async def test_upstream_error_body_is_not_exposed_in_exception(self):
        class FakeResponse:
            status_code = 429
            text = "signed_url=https://cdn.example/sticker.webp?token=DO_NOT_LOG"

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def get(self, *args, **kwargs):
                return FakeResponse()

        from unittest.mock import patch
        from backend.extractor_adapter import ExtractionException

        with patch("backend.extractor_adapter.httpx.AsyncClient", return_value=FakeAsyncClient()):
            with self.assertRaises(ExtractionException) as context:
                await self.adapter._get("/v1/tiktok/video/comments", {"cursor": 0})

        self.assertEqual(context.exception.error_code, "PROVIDER_REQUEST_FAILED")
        self.assertNotIn("DO_NOT_LOG", str(context.exception))
        self.assertNotIn("cdn.example", str(context.exception))

    def test_sticker_without_any_media_url_is_rejected(self):
        comment = {
            "cid": "456",
            "cmt_sticker_struct": {
                "sticker_id": "sticker-456",
                "sticker_type": 2,
            },
        }
        self.assertIsNone(self.adapter.parse_sticker(comment))

    def test_provider_defaults_to_disabled_even_when_paid_key_exists(self):
        old_provider = os.environ.pop("EXTRACTION_PROVIDER", None)
        old_key = os.environ.get("SCRAPECREATORS_API_KEY")
        try:
            os.environ["SCRAPECREATORS_API_KEY"] = "present-but-must-not-auto-enable"
            adapter = get_extractor_adapter()
            self.assertIsInstance(adapter, DisabledExtractorAdapter)
            self.assertEqual(adapter.provider_name, "disabled")
        finally:
            if old_provider is not None:
                os.environ["EXTRACTION_PROVIDER"] = old_provider
            if old_key is None:
                os.environ.pop("SCRAPECREATORS_API_KEY", None)
            else:
                os.environ["SCRAPECREATORS_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
