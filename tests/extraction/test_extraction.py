"""
Unit and Integration Tests for TikTok Sticker Extraction.
"""

import unittest
from unittest.mock import patch
from src.extraction.models import CommentRecord, StickerMedia, ExtractionResult
from src.extraction.adapter import MockExtractionAdapter
from src.extraction.extractor import StickerExtractor
from src.media.processor import MediaProcessor


class TestStickerExtraction(unittest.TestCase):

    def setUp(self):
        # Target test fixture matching research context
        self.target_fixture = {
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
                    "url_list": ["https://p16-sign-va.tiktokcdn.com/avatar.webp"]
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
        }

        self.text_only_fixture = {
            "cid": "7708999999999999999",
            "aweme_id": "7708356144804236564",
            "text": "Lucu banget videonya bang",
            "create_time": 1731600100,
            "digg_count": 5,
            "user": {
                "uid": "1111111111111111111",
                "nickname": "user_biasa",
                "unique_id": "user_biasa"
            }
        }

        self.adapter = MockExtractionAdapter([self.target_fixture, self.text_only_fixture])
        self.extractor = StickerExtractor(self.adapter)

    def test_parse_comment_with_sticker(self):
        record = self.adapter.parse_comment_record(self.target_fixture)
        self.assertEqual(record.cid, "7708394712596972308")
        self.assertEqual(record.author.unique_id, "crazyolshop1")
        self.assertEqual(record.text, "ngajak ribut kamu? 🗿")
        self.assertIsNotNone(record.sticker)
        self.assertTrue(record.sticker.is_animated)
        self.assertEqual(record.sticker.sticker_id, "7421890123456789012")
        self.assertIn("prabowo_animated.awebp", record.sticker.animated_url)

    def test_parse_text_only_comment(self):
        record = self.adapter.parse_comment_record(self.text_only_fixture)
        self.assertEqual(record.cid, "7708999999999999999")
        self.assertIsNone(record.sticker)

    def test_extract_target_comment_with_mock_download(self):
        mock_webp_bytes = MediaProcessor.create_synthetic_animated_webp(width=512, height=512)

        with patch.object(self.extractor, "download_media", return_value=mock_webp_bytes):
            canonical_url = "https://www.tiktok.com/@nyariprompt/video/7708356144804236564?share_comment_id=7708394712596972308"
            result = self.extractor.extract_by_ids(
                video_id="7708356144804236564",
                comment_id="7708394712596972308",
                canonical_url=canonical_url,
                download_media=True
            )

            self.assertTrue(result.success)
            self.assertEqual(result.target_comment_id, "7708394712596972308")
            self.assertTrue(result.has_sticker)
            self.assertIsNotNone(result.media_bytes)
            self.assertEqual(result.media_format, "awebp")
            self.assertIsNotNone(result.sha256)
            self.assertEqual(result.comment.author.unique_id, "crazyolshop1")

    def test_extract_non_existent_comment(self):
        result = self.extractor.extract_by_ids(
            video_id="7708356144804236564",
            comment_id="9999999999999999999",
            canonical_url="https://www.tiktok.com/@nyariprompt/video/7708356144804236564",
            download_media=False
        )
        self.assertFalse(result.success)
        self.assertIn("was not found", result.error_message)

    def test_sticker_type_hint_without_animated_asset_is_static(self):
        comment = {
            "cid": "static-hint-only",
            "cmt_sticker_struct": {
                "sticker_id": "static-1",
                "sticker_type": 2,
                "static_url": {"url_list": ["https://cdn.example.test/sticker.webp"]},
            },
        }
        parsed = self.adapter.parse_sticker(comment)
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed.is_animated)
        self.assertEqual(parsed.best_url, "https://cdn.example.test/sticker.webp")


if __name__ == "__main__":
    unittest.main()
