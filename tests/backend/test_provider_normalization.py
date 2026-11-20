import unittest

from backend.extractor_adapter import ExtractionException
from backend.provider_normalization import normalize_provider_page


class TestProviderNormalization(unittest.TestCase):
    def test_normalizes_nested_research_style_page(self):
        payload = {
            "data": {
                "comments": [{
                    "id": 123456789,
                    "text": "sticker",
                    "reply_count": 17,
                    "display_name": "Tester",
                    "parent_comment_id": 12,
                    "cmt_sticker_struct": {"sticker_id": "st-1"},
                }],
                "has_more": True,
                "cursor": 100,
            },
            "error": {"code": "ok"},
        }
        normalized = normalize_provider_page(payload)
        self.assertEqual(normalized["comments"][0]["cid"], "123456789")
        self.assertEqual(normalized["comments"][0]["reply_comment_total"], 17)
        self.assertEqual(normalized["comments"][0]["user"]["nickname"], "Tester")
        self.assertEqual(normalized["comments"][0]["parent_comment_id"], 12)
        self.assertEqual(normalized["comments"][0]["cmt_sticker_struct"]["sticker_id"], "st-1")
        self.assertTrue(normalized["has_more"])
        self.assertEqual(normalized["cursor"], 100)

    def test_normalizes_comment_list_alias_and_string_boolean(self):
        normalized = normalize_provider_page({
            "comment_list": [{"comment_id": "reply-1", "user_info": {"username": "alice"}}],
            "hasMore": "false",
            "nextCursor": 20,
        })
        self.assertEqual(normalized["comments"][0]["cid"], "reply-1")
        self.assertEqual(normalized["comments"][0]["user"]["unique_id"], "alice")
        self.assertFalse(normalized["has_more"])
        self.assertIsNone(normalized["cursor"])

    def test_empty_collection_is_a_valid_terminal_page(self):
        self.assertEqual(
            normalize_provider_page({"data": {"comments": [], "has_more": False, "cursor": 0}}),
            {"comments": [], "has_more": False, "cursor": None},
        )

    def test_cursor_without_boolean_indicates_more_pages(self):
        normalized = normalize_provider_page({"data": {"replies": [], "next_cursor": "opaque-2"}})
        self.assertTrue(normalized["has_more"])
        self.assertEqual(normalized["cursor"], "opaque-2")

    def test_provider_error_envelope_is_not_reported_as_empty_comments(self):
        with self.assertRaises(ExtractionException) as context:
            normalize_provider_page({
                "data": {"comments": [], "has_more": False},
                "error": {"code": "rate_limit", "message": "slow down"},
            })
        self.assertEqual(context.exception.error_code, "UPSTREAM_INVALID_RESPONSE")

    def test_unknown_payload_does_not_become_false_empty_page(self):
        with self.assertRaises(ExtractionException) as context:
            normalize_provider_page({"data": {"items_list": [], "next": "token"}})
        self.assertEqual(context.exception.error_code, "UPSTREAM_INVALID_RESPONSE")
        self.assertEqual(context.exception.status_code, 502)

    def test_malformed_comment_collection_is_rejected(self):
        with self.assertRaises(ExtractionException):
            normalize_provider_page({"comments": {"unexpected": "object"}, "has_more": False})

    def test_non_object_comment_is_rejected(self):
        with self.assertRaises(ExtractionException):
            normalize_provider_page({"comments": ["not-a-comment"], "has_more": False})


if __name__ == "__main__":
    unittest.main()
