"""
Unit and Integration Tests for WebP / AWEBP Binary Parser and Media Processor.
"""

import unittest
from src.media.validator import WebPBinaryParser
from src.media.processor import MediaProcessor


class TestMediaValidator(unittest.TestCase):

    def setUp(self):
        self.parser = WebPBinaryParser()
        self.processor = MediaProcessor()

    def test_parse_valid_static_webp_512(self):
        webp_bytes = self.processor.create_synthetic_static_webp(width=512, height=512, payload_size=4096)
        meta = self.parser.parse(webp_bytes)

        self.assertTrue(meta.is_valid_webp)
        self.assertFalse(meta.is_animated)
        self.assertEqual(meta.width, 512)
        self.assertEqual(meta.height, 512)
        self.assertEqual(meta.frame_count, 1)
        self.assertTrue(meta.has_alpha)
        self.assertTrue(meta.whatsapp_compliant)
        self.assertEqual(len(meta.compliance_issues), 0)

    def test_parse_valid_animated_webp_512(self):
        webp_bytes = self.processor.create_synthetic_animated_webp(
            width=512,
            height=512,
            frame_count=8,
            frame_duration_ms=100,  # 800ms total
            frame_payload_size=2048
        )
        meta = self.parser.parse(webp_bytes)

        self.assertTrue(meta.is_valid_webp)
        self.assertTrue(meta.is_animated)
        self.assertEqual(meta.width, 512)
        self.assertEqual(meta.height, 512)
        self.assertEqual(meta.frame_count, 8)
        self.assertEqual(meta.duration_ms, 800)
        self.assertTrue(meta.whatsapp_compliant)
        self.assertEqual(len(meta.compliance_issues), 0)

    def test_invalid_header_non_webp(self):
        corrupt_bytes = b"NOT_A_WEBP_IMAGE_FILE_DATA"
        meta = self.parser.parse(corrupt_bytes)
        self.assertFalse(meta.is_valid_webp)
        self.assertIn("Invalid magic bytes", meta.compliance_issues[0])

    def test_non_512_dimension_compliance_failure(self):
        # 300x300 (common raw TikTok dimension)
        webp_bytes = self.processor.create_synthetic_static_webp(width=300, height=300)
        meta = self.parser.parse(webp_bytes)

        self.assertTrue(meta.is_valid_webp)
        self.assertFalse(meta.whatsapp_compliant)
        self.assertTrue(any("512x512" in issue for issue in meta.compliance_issues))

    def test_oversized_animated_webp_compliance_failure(self):
        # WhatsApp animated limit is 500 KB (512,000 bytes). Create > 520 KB file.
        webp_bytes = self.processor.create_synthetic_animated_webp(
            width=512,
            height=512,
            frame_count=6,
            frame_duration_ms=200,
            frame_payload_size=100 * 1024  # 6 * 100KB = ~600KB
        )
        meta = self.parser.parse(webp_bytes)

        self.assertTrue(meta.is_valid_webp)
        self.assertTrue(meta.is_animated)
        self.assertFalse(meta.whatsapp_compliant)
        self.assertTrue(any("exceeds WhatsApp 500 KB limit" in issue for issue in meta.compliance_issues))

    def test_static_binary_overrides_animation_metadata_hints(self):
        # The binary container is authoritative: no ANIM/ANMF and no animation flag.
        webp_bytes = self.processor.create_synthetic_static_webp(width=458, height=498)
        meta = self.parser.parse(webp_bytes)
        self.assertTrue(meta.is_valid_webp)
        self.assertFalse(meta.is_animated)
        self.assertEqual(meta.frame_count, 1)
        self.assertEqual(meta.duration_ms, 0)
        self.assertEqual(meta.width, 458)
        self.assertEqual(meta.height, 498)

    def test_reject_riff_size_mismatch(self):
        webp_bytes = bytearray(self.processor.create_synthetic_static_webp())
        webp_bytes[4] = (webp_bytes[4] + 1) & 0xFF
        meta = self.parser.parse(bytes(webp_bytes))
        self.assertFalse(meta.is_valid_webp)
        self.assertTrue(any("RIFF size mismatch" in issue for issue in meta.compliance_issues))

    def test_reject_animation_flag_without_anim_frames(self):
        webp_bytes = bytearray(self.processor.create_synthetic_static_webp())
        # Set VP8X animation flag but deliberately omit ANIM and ANMF chunks.
        webp_bytes[20] |= 0x02
        meta = self.parser.parse(bytes(webp_bytes))
        self.assertFalse(meta.is_valid_webp)
        self.assertTrue(any("animation flag" in issue for issue in meta.compliance_issues))


if __name__ == "__main__":
    unittest.main()
