import hashlib
import unittest

from backend.source_qualification import qualify_sticker_source


def _chunk(name: bytes, data: bytes) -> bytes:
    return name + len(data).to_bytes(4, "little") + data + (b"\x00" if len(data) % 2 else b"")


def _valid_webp() -> bytes:
    # A structurally valid static WebP fixture for the pure-Python RIFF parser.
    vp8x = bytes([0x10, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    vp8 = b"\x00\x00\x00\x9d\x01\x2a\x00\x00\x00\x00"
    body = b"WEBP" + _chunk(b"VP8X", vp8x) + _chunk(b"VP8 ", vp8)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def _comment(comment_id="target-1", media_host="p16.tiktokcdn.com"):
    return {
        "cid": comment_id,
        "text": "[Sticker]",
        "cmt_sticker_struct": {
            "sticker_id": "sticker-123",
            "sticker_type": 1,
            "static_url": {
                "url_list": [f"https://{media_host}/path/sticker.webp?x-expires=123&x-signature=secret"],
                "width": 458,
                "height": 498,
            },
        },
    }


class TestSourceQualification(unittest.TestCase):
    def test_exact_top_level_comment_with_real_media_qualifies(self):
        media = _valid_webp()
        report = qualify_sticker_source(
            {"comments": [_comment()]},
            "target-1",
            media_bytes=media,
            expected_sha256=hashlib.sha256(media).hexdigest(),
        )
        self.assertEqual(report["status"], "qualified")
        self.assertEqual(report["sticker_id"], "sticker-123")
        self.assertTrue(report["checks"]["media_file_valid"])
        self.assertTrue(report["checks"]["expected_sha256_match"])
        self.assertNotIn("x-signature", str(report))

    def test_exact_nested_reply_is_found(self):
        report = qualify_sticker_source(
            {"comments": [{"cid": "parent-1", "reply_comment": [_comment("reply-9")]}]},
            "reply-9",
        )
        self.assertEqual(report["status"], "metadata_only")
        self.assertTrue(report["checks"]["exact_comment_found"])
        self.assertTrue(report["checks"]["sticker_struct_present"])

    def test_plain_sticker_label_without_media_struct_is_rejected(self):
        report = qualify_sticker_source(
            {"comments": [{"cid": "target-1", "text": "[Sticker]"}]},
            "target-1",
        )
        self.assertEqual(report["status"], "comment_only")
        self.assertIn("STICKER_STRUCT_MISSING", report["issues"])

    def test_exact_comment_id_is_required(self):
        report = qualify_sticker_source(
            {"comments": [_comment("another-comment")]},
            "target-1",
            media_bytes=_valid_webp(),
        )
        self.assertEqual(report["status"], "not_qualified")
        self.assertIn("EXACT_COMMENT_NOT_FOUND", report["issues"])

    def test_unapproved_host_is_rejected(self):
        report = qualify_sticker_source(
            {"comments": [_comment(media_host="attacker.example")]},
            "target-1",
            media_bytes=_valid_webp(),
        )
        self.assertEqual(report["status"], "not_qualified")
        self.assertFalse(report["checks"]["media_url_allowed"])
        self.assertIn("MEDIA_HOST_OR_URL_NOT_ALLOWED", report["issues"])

    def test_media_without_structural_webp_is_rejected(self):
        report = qualify_sticker_source(
            {"comments": [_comment()]},
            "target-1",
            media_bytes=b"not a webp file",
        )
        self.assertEqual(report["status"], "not_qualified")
        self.assertFalse(report["checks"]["media_file_valid"])
        self.assertIn("MEDIA_FILE_INVALID_WEBP", report["issues"])

    def test_expected_sha256_mismatch_is_rejected(self):
        report = qualify_sticker_source(
            {"comments": [_comment()]},
            "target-1",
            media_bytes=_valid_webp(),
            expected_sha256="0" * 64,
        )
        self.assertEqual(report["status"], "not_qualified")
        self.assertFalse(report["checks"]["expected_sha256_match"])
        self.assertIn("SHA256_MISMATCH", report["issues"])

    def test_missing_media_bytes_is_only_metadata_qualified(self):
        report = qualify_sticker_source({"comments": [_comment()]}, "target-1")
        self.assertEqual(report["status"], "metadata_only")
        self.assertIn("MEDIA_BYTES_NOT_PROVIDED", report["issues"])

    def test_animated_url_is_preferred_when_present(self):
        comment = _comment()
        comment["cmt_sticker_struct"]["animated_url"] = {
            "url_list": ["https://p16.tiktokcdn.com/path/sticker.awebp"]
        }
        report = qualify_sticker_source({"comments": [comment]}, "target-1")
        self.assertEqual(report["source_media_hint"], "animated")


if __name__ == "__main__":
    unittest.main()
