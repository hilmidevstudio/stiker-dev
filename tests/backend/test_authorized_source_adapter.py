import json
import os
import unittest
from unittest.mock import patch

import httpx

from backend.authorized_source_adapter import (
    AuthorizedSourceAdapter,
    authorized_source_configuration_status,
)
from backend.extractor_adapter import (
    ExtractionException,
    ProviderAuthException,
    get_extraction_provider_status,
    get_extractor_adapter,
)
from backend.comment_discovery import CommentDiscoveryEngine, DiscoveryLimits


class TestAuthorizedSourceAdapter(unittest.IsolatedAsyncioTestCase):
    def make_adapter(self, handler, **kwargs):
        transport = httpx.MockTransport(handler)
        return AuthorizedSourceAdapter(
            base_url="https://source.example.test",
            api_key="unit-test-secret",
            transport=transport,
            **kwargs,
        )

    async def test_comments_request_uses_bearer_auth_and_normalizes_page(self):
        captured = {}

        def handler(request):
            captured["request"] = request
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={
                    "data": {
                        "comments": [{"id": "c-1", "reply_count": 3, "username": "tester"}],
                        "has_more": True,
                        "cursor": "next-page-token",
                    }
                },
            )

        adapter = self.make_adapter(handler)
        page = await adapter.fetch_comments("https://www.tiktok.com/@x/video/1", cursor="opaque-0", count=500)
        request = captured["request"]
        body = json.loads(request.content)

        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/v1/comments")
        self.assertEqual(request.headers["authorization"], "Bearer unit-test-secret")
        self.assertEqual(body["cursor"], "opaque-0")
        self.assertEqual(body["count"], 100)
        self.assertEqual(page["comments"][0]["cid"], "c-1")
        self.assertEqual(page["comments"][0]["reply_comment_total"], 3)
        self.assertEqual(page["comments"][0]["user"]["unique_id"], "tester")
        self.assertTrue(page["has_more"])
        self.assertEqual(page["cursor"], "next-page-token")

    async def test_adapter_integrates_with_discovery_and_parses_exact_sticker(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={
                    "comments": [
                        {
                            "cid": "golden-comment-1",
                            "text": "[Sticker]",
                            "cmt_sticker_struct": {
                                "sticker_id": "golden-sticker-1",
                                "sticker_type": 1,
                                "static_url": {
                                    "url_list": ["https://p16-tiktokcdn-us.com/sticker.webp"],
                                    "width": 458,
                                    "height": 498,
                                },
                            },
                        }
                    ],
                    "has_more": False,
                    "cursor": None,
                },
            )

        adapter = self.make_adapter(handler)
        discovery = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=2, max_reply_parents=2, max_reply_pages_per_parent=2)
        ).find_comment(
            adapter,
            video_url="https://www.tiktok.com/@creator/video/1",
            target_comment_id="golden-comment-1",
        )
        self.assertIsNotNone(discovery.comment)
        sticker = adapter.parse_sticker(discovery.comment)
        self.assertEqual(sticker.sticker_id, "golden-sticker-1")
        self.assertEqual(sticker.media_url, "https://p16-tiktokcdn-us.com/sticker.webp")
        self.assertFalse(sticker.is_animated)

    async def test_adapter_preserves_opaque_cursor_across_discovery_pages(self):
        requested_cursors = []

        def handler(request):
            body = json.loads(request.content)
            requested_cursors.append(body["cursor"])
            if body["cursor"] == 0:
                return httpx.Response(
                    200,
                    headers={"content-type": "application/json"},
                    json={"comments": [{"cid": "other"}], "has_more": True, "cursor": "page-two"},
                )
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"comments": [{"cid": "target"}], "has_more": False},
            )

        adapter = self.make_adapter(handler)
        discovery = await CommentDiscoveryEngine(
            DiscoveryLimits(max_comment_pages=3, max_reply_parents=1, max_reply_pages_per_parent=1)
        ).find_comment(
            adapter,
            video_url="https://www.tiktok.com/@creator/video/1",
            target_comment_id="target",
        )
        self.assertEqual(requested_cursors, [0, "page-two"])
        self.assertEqual(discovery.comment["cid"], "target")

    async def test_replies_request_uses_exact_parent_id_and_normalizes(self):
        captured = {}

        def handler(request):
            captured["request"] = request
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"comments": [{"comment_id": "reply-1"}], "has_more": False},
            )

        adapter = self.make_adapter(handler)
        page = await adapter.fetch_replies("parent-77", "https://www.tiktok.com/@x/video/1", cursor=10)
        body = json.loads(captured["request"].content)
        self.assertEqual(captured["request"].url.path, "/v1/replies")
        self.assertEqual(body["comment_id"], "parent-77")
        self.assertEqual(body["cursor"], 10)
        self.assertEqual(page["comments"][0]["cid"], "reply-1")
        self.assertFalse(page["has_more"])

    async def test_redirect_is_rejected_without_following(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(307, headers={"location": "https://elsewhere.example.test/steal"})

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_REDIRECT_REJECTED")
        self.assertEqual(len(calls), 1)

    async def test_unauthorized_source_response_raises_auth_error_without_body(self):
        secret_body = "Bearer leaked-source-token"

        def handler(request):
            return httpx.Response(
                401,
                headers={"content-type": "text/plain"},
                content=secret_body.encode(),
            )

        adapter = self.make_adapter(handler)
        with self.assertRaises(ProviderAuthException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertNotIn("leaked-source-token", str(context.exception))

    async def test_rate_limit_has_safe_error_code(self):
        def handler(request):
            return httpx.Response(429, content=b"account secret details")

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_RATE_LIMITED")
        self.assertNotIn("account secret", str(context.exception))

    async def test_oversized_body_is_rejected_even_without_content_length(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b" " * 2048,
            )

        adapter = self.make_adapter(handler, max_response_bytes=1024)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_RESPONSE_TOO_LARGE")

    async def test_malformed_json_is_rejected(self):
        def handler(request):
            return httpx.Response(200, headers={"content-type": "application/json"}, content=b"{broken")

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_INVALID_RESPONSE")

    async def test_unknown_page_shape_is_not_silently_treated_as_empty(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"success": True, "message": "no results"},
            )

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "UPSTREAM_INVALID_RESPONSE")

    async def test_non_json_content_type_is_rejected(self):
        def handler(request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html />")

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_INVALID_CONTENT_TYPE")

    async def test_http_error_does_not_expose_upstream_body(self):
        def handler(request):
            return httpx.Response(500, content=b"internal-key=sensitive")

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_REQUEST_FAILED")
        self.assertNotIn("sensitive", str(context.exception))

    async def test_timeout_is_reported_without_request_url(self):
        def handler(request):
            raise httpx.ReadTimeout("timeout at https://source.example.test/private?token=hidden", request=request)

        adapter = self.make_adapter(handler)
        with self.assertRaises(ExtractionException) as context:
            await adapter.fetch_comments("https://www.tiktok.com/@x/video/1")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_TIMEOUT")
        self.assertNotIn("token=hidden", str(context.exception))


class TestAuthorizedSourceConfiguration(unittest.TestCase):
    def test_production_requires_https(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with self.assertRaises(ExtractionException) as context:
                AuthorizedSourceAdapter(base_url="http://source.example.test", api_key="secret")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_CONFIG_INVALID")

    def test_localhost_http_is_allowed_only_outside_production(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            adapter = AuthorizedSourceAdapter(base_url="http://127.0.0.1:8081", api_key="secret")
            self.assertEqual(adapter.base_url, "http://127.0.0.1:8081")
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with self.assertRaises(ExtractionException):
                AuthorizedSourceAdapter(base_url="http://127.0.0.1:8081", api_key="secret")

    def test_credentials_query_fragment_and_path_traversal_are_rejected(self):
        invalid_urls = [
            "https://user:pass@source.example.test",
            "https://source.example.test?token=x",
            "https://source.example.test/#fragment",
            "https://source.example.test/api/../admin",
        ]
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ExtractionException):
                AuthorizedSourceAdapter(base_url=url, api_key="secret")

    def test_api_key_is_required(self):
        with self.assertRaises(ExtractionException) as context:
            AuthorizedSourceAdapter(base_url="https://source.example.test", api_key="")
        self.assertEqual(context.exception.error_code, "AUTHORIZED_SOURCE_NOT_CONFIGURED")

    def test_response_and_timeout_limits_are_bounded(self):
        for kwargs in ({"timeout_seconds": 0.5}, {"timeout_seconds": 61}, {"max_response_bytes": 100}, {"max_response_bytes": 11 * 1024 * 1024}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ExtractionException):
                AuthorizedSourceAdapter(base_url="https://source.example.test", api_key="secret", **kwargs)

    def test_factory_does_not_enable_adapter_implicitly(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "AUTHORIZED_SOURCE_BASE_URL": "https://source.example.test", "AUTHORIZED_SOURCE_API_KEY": "secret"}, clear=False):
            os.environ.pop("EXTRACTION_PROVIDER", None)
            adapter = get_extractor_adapter()
            self.assertEqual(adapter.provider_name, "disabled")

    def test_explicit_factory_selection_activates_authorized_source_adapter(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "EXTRACTION_PROVIDER": "authorized_source",
            "AUTHORIZED_SOURCE_BASE_URL": "https://source.example.test",
            "AUTHORIZED_SOURCE_API_KEY": "secret",
        }):
            adapter = get_extractor_adapter()
            self.assertIsInstance(adapter, AuthorizedSourceAdapter)

    def test_status_is_safe_and_does_not_show_key_or_url(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "EXTRACTION_PROVIDER": "authorized_source",
            "AUTHORIZED_SOURCE_BASE_URL": "https://source.example.test/private",
            "AUTHORIZED_SOURCE_API_KEY": "do-not-return-this-key",
        }):
            status = get_extraction_provider_status()
        serialized = json.dumps(status)
        self.assertTrue(status["ready"])
        self.assertFalse(status["provider_called"])
        self.assertFalse(status["external_credit_provider"])
        self.assertEqual(status["billing_model"], "operator_managed")
        self.assertNotIn("do-not-return-this-key", serialized)
        self.assertNotIn("source.example.test", serialized)

    def test_configuration_status_fails_closed_without_credentials(self):
        with patch.dict(os.environ, {"AUTHORIZED_SOURCE_BASE_URL": "", "AUTHORIZED_SOURCE_API_KEY": ""}):
            status = authorized_source_configuration_status()
        self.assertFalse(status["configured"])
        self.assertFalse(status["ready"])
        self.assertFalse(status["provider_called"])


if __name__ == "__main__":
    unittest.main()
