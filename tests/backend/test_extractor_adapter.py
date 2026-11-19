import unittest

from backend.extractor_adapter import ScrapeCreatorsAdapter


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


if __name__ == "__main__":
    unittest.main()
