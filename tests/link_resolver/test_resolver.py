"""
Unit and Integration Tests for TikTok Link Resolver.
"""

import unittest
from src.link_resolver.resolver import (
    TikTokLinkResolver,
    ResolvedTarget,
    InvalidUrlError,
    VideoIdNotFoundError
)


class TestTikTokLinkResolver(unittest.TestCase):

    def setUp(self):
        self.resolver = TikTokLinkResolver()

    def test_extract_url_from_text(self):
        text = "Check this cool sticker! https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/ see you there"
        extracted = self.resolver.extract_url_from_text(text)
        self.assertEqual(extracted, "https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/")

    def test_extract_url_empty_raises(self):
        with self.assertRaises(InvalidUrlError):
            self.resolver.extract_url_from_text("")

    def test_parse_canonical_comment_url(self):
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=7708394712596972308&comment_author_id=7435664412436120631"
        )
        target = self.resolver.parse_url(url, follow_redirects=False)
        self.assertEqual(target.video_id, "7708356144804236564")
        self.assertEqual(target.comment_id, "7708394712596972308")
        self.assertEqual(target.author_id, "7435664412436120631")
        self.assertTrue(target.is_comment_link)

    def test_parse_canonical_video_url_without_comment(self):
        url = "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
        target = self.resolver.parse_url(url, follow_redirects=False)
        self.assertEqual(target.video_id, "7708356144804236564")
        self.assertIsNone(target.comment_id)
        self.assertFalse(target.is_comment_link)

    def test_parse_alternative_comment_param(self):
        url = "https://www.tiktok.com/@user/video/1234567890123456789?comment_id=9876543210987654321"
        target = self.resolver.parse_url(url, follow_redirects=False)
        self.assertEqual(target.video_id, "1234567890123456789")
        self.assertEqual(target.comment_id, "9876543210987654321")
        self.assertTrue(target.is_comment_link)

    def test_parse_cid_param(self):
        url = "https://www.tiktok.com/@user/video/1234567890123456789?cid=5555555555555555555"
        target = self.resolver.parse_url(url, follow_redirects=False)
        self.assertEqual(target.comment_id, "5555555555555555555")

    def test_missing_video_id_raises(self):
        url = "https://www.tiktok.com/@user/about"
        with self.assertRaises(VideoIdNotFoundError):
            self.resolver.parse_url(url, follow_redirects=False)


if __name__ == "__main__":
    unittest.main()
