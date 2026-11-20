import unittest
import os


from backend.extractor_adapter import (
    ScrapeCreatorsAdapter,
    DisabledExtractorAdapter,
    get_extractor_adapter,
)


class TestScrapeCreatorsAdapter(unittest.TestCase):
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
