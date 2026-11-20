import os
import unittest
from unittest.mock import patch

import httpx

from services.tiktok_business_source import app as source
from backend.extractor_adapter import ExtractorAdapter


class TikTokBusinessSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TIKTOK_BUSINESS_ACCESS_TOKEN": "test-access-token",
                "TIKTOK_BUSINESS_ID": "test-open-id",
                "STICKERDROP_SOURCE_API_KEY": "test-source-key-12345678901234567890",
                "TIKTOK_BUSINESS_TIMEOUT_SECONDS": "5",
            },
            clear=False,
        )
        self.env.start()
        source._request_times.clear()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=source.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.env.stop()
        source._http_transport = None
        source._request_times.clear()

    async def test_health_is_public_and_does_not_expose_credentials(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["healthy"])
        self.assertNotIn("test-access-token", response.text)

    async def test_status_requires_source_auth_and_is_non_secret(self):
        denied = await self.client.get("/v1/status")
        self.assertEqual(denied.status_code, 401)

        response = await self.client.get(
            "/v1/status", headers={"Authorization": "Bearer test-source-key-12345678901234567890"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ready"])
        self.assertEqual(body["supported_scope"], "owned_videos_only")
        self.assertNotIn("test-access-token", response.text)

    async def test_video_id_parser_accepts_owned_video_url(self):
        self.assertEqual(
            source.extract_video_id("https://www.tiktok.com/@creator/video/7700924470206156050"),
            "7700924470206156050",
        )

    async def test_video_id_parser_rejects_photo_posts_not_documented_by_this_connector(self):
        with self.assertRaises(ValueError):
            source.extract_video_id("https://www.tiktok.com/@creator/photo/7700924470206156050")

    async def test_video_id_parser_rejects_non_tiktok_and_noncanonical_urls(self):
        with self.assertRaises(ValueError):
            source.extract_video_id("https://evil.example/@creator/video/7700924470206156050")
        with self.assertRaises(ValueError):
            source.extract_video_id("https://www.tiktok.com/@creator/video/not-an-id")
        with self.assertRaises(ValueError):
            source.extract_video_id("http://www.tiktok.com/@creator/video/7700924470206156050")

    async def test_comments_route_calls_official_business_endpoint_and_maps_image_url(self):
        captured = {}

        def handler(request):
            captured["request"] = request
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={
                    "code": 0,
                    "message": "OK",
                    "data": {
                        "comments": [
                            {
                                "comment_id": "7700946321838818056",
                                "video_id": "7700924470206156050",
                                "text": "Naruto sticker",
                                "likes": 12,
                                "replies": 2,
                                "create_time": 1760000000,
                                "username": "sample_user",
                                "display_name": "Sample User",
                                "unique_identifier": "account-user-id",
                                "image_url": "https://p16-sign-va.tiktokcdn.com/comment-image.webp",
                                "reply_list": [
                                    {
                                        "comment_id": "7700946321838818057",
                                        "parent_comment_id": "7700946321838818056",
                                        "text": "reply",
                                        "username": "reply_user",
                                    }
                                ],
                            }
                        ],
                        "has_more": True,
                        "cursor": 30,
                    },
                },
            )

        source._http_transport = httpx.MockTransport(handler)
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={
                "video_url": "https://www.tiktok.com/@creator/video/7700924470206156050",
                "cursor": 0,
                "count": 50,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        request = captured["request"]
        self.assertEqual(request.url.host, "business-api.tiktok.com")
        self.assertEqual(request.url.path, source.COMMENTS_PATH)
        self.assertEqual(request.headers["Access-Token"], "test-access-token")
        self.assertEqual(request.url.params["business_id"], "test-open-id")
        self.assertEqual(request.url.params["video_id"], "7700924470206156050")
        self.assertEqual(request.url.params["max_count"], "30")

        page = response.json()
        comment = page["comments"][0]
        self.assertEqual(comment["cid"], "7700946321838818056")
        self.assertEqual(comment["reply_comment_total"], 2)
        self.assertEqual(comment["user"]["unique_id"], "sample_user")
        self.assertEqual(comment["source_media_kind"], "comment_image")
        self.assertEqual(
            comment["comment_pics"][0]["url_list"][0],
            "https://p16-sign-va.tiktokcdn.com/comment-image.webp",
        )
        self.assertEqual(comment["reply_comment"][0]["cid"], "7700946321838818057")
        self.assertTrue(page["has_more"])
        self.assertEqual(page["cursor"], 30)

    async def test_reply_route_calls_official_reply_endpoint(self):
        captured = {}

        def handler(request):
            captured["request"] = request
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={
                    "code": 0,
                    "data": {
                        "comments": [
                            {
                                "comment_id": "7700946321838818057",
                                "parent_comment_id": "7700946321838818056",
                                "text": "reply image",
                                "image_url": "https://p16-sign-va.tiktokcdn.com/reply.webp",
                            }
                        ],
                        "has_more": False,
                        "cursor": 1,
                    },
                },
            )

        source._http_transport = httpx.MockTransport(handler)
        response = await self.client.post(
            "/v1/replies",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={
                "video_url": "https://www.tiktok.com/@creator/video/7700924470206156050",
                "comment_id": "7700946321838818056",
                "cursor": 0,
                "count": 20,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        request = captured["request"]
        self.assertEqual(request.url.path, source.REPLIES_PATH)
        self.assertEqual(request.url.params["comment_id"], "7700946321838818056")
        reply = response.json()["comments"][0]
        self.assertEqual(reply["cid"], "7700946321838818057")
        self.assertEqual(reply["parent_comment_id"], "7700946321838818056")
        self.assertEqual(reply["source_media_kind"], "comment_image")

    async def test_unauthorized_source_key_is_rejected_before_upstream_call(self):
        calls = []
        source._http_transport = httpx.MockTransport(lambda request: calls.append(request))
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer wrong-key"},
            json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, [])

    async def test_missing_tiktok_credentials_returns_configuration_error(self):
        with patch.dict(os.environ, {"TIKTOK_BUSINESS_ACCESS_TOKEN": "", "TIKTOK_BUSINESS_ID": ""}):
            response = await self.client.post(
                "/v1/comments",
                headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
                json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["error_code"], "TIKTOK_BUSINESS_NOT_CONFIGURED")

    async def test_unowned_video_permission_error_is_sanitized(self):
        def handler(request):
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"code": 40002, "message": "Video does not belong to this account", "data": {}},
            )

        source._http_transport = httpx.MockTransport(handler)
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={"video_url": "https://www.tiktok.com/@other/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["error_code"], "TIKTOK_BUSINESS_UPSTREAM_ERROR")
        self.assertNotIn("Video does not belong", response.text)

    async def test_upstream_401_maps_to_sanitized_auth_error(self):
        source._http_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, headers={"content-type": "application/json"}, json={})
        )
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["error_code"], "TIKTOK_BUSINESS_AUTH_REJECTED")

    async def test_upstream_429_maps_to_retryable_503(self):
        source._http_transport = httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"content-type": "application/json"}, json={})
        )
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers.get("retry-after"), "60")

    async def test_malformed_upstream_page_is_rejected(self):
        source._http_transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"code": 0, "data": {"comments": [], "cursor": 0}},
            )
        )
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["error_code"], "TIKTOK_BUSINESS_INVALID_RESPONSE")

    async def test_invalid_comment_id_is_rejected(self):
        response = await self.client.post(
            "/v1/replies",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={
                "video_url": "https://www.tiktok.com/@creator/video/7700924470206156050",
                "comment_id": "not-numeric",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["error_code"], "INVALID_COMMENT_ID")

    async def test_redirect_is_rejected(self):
        source._http_transport = httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"location": "https://example.com"})
        )
        response = await self.client.post(
            "/v1/comments",
            headers={"Authorization": "Bearer test-source-key-12345678901234567890"},
            json={"video_url": "https://www.tiktok.com/@creator/video/7700924470206156050"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["error_code"], "TIKTOK_BUSINESS_REDIRECT_REJECTED")

    async def test_image_comment_maps_to_existing_static_media_parser(self):
        normalized = source._normalize_comment(
            {
                "comment_id": "1234567890",
                "image_url": "https://p16-sign-va.tiktokcdn.com/example.webp",
            }
        )
        sticker_candidate = ExtractorAdapter.parse_sticker(None, normalized)
        self.assertIsNotNone(sticker_candidate)
        self.assertFalse(sticker_candidate.is_animated)
        self.assertEqual(sticker_candidate.format, "webp")
        self.assertEqual(sticker_candidate.media_url, "https://p16-sign-va.tiktokcdn.com/example.webp")

    async def test_image_comment_is_not_falsely_marked_as_native_sticker_struct(self):
        normalized = source._normalize_comment(
            {
                "comment_id": "1234567890",
                "image_url": "https://p16-sign-va.tiktokcdn.com/example.webp",
            }
        )
        self.assertIn("comment_pics", normalized)
        self.assertNotIn("cmt_sticker_struct", normalized)
        self.assertEqual(normalized["source_media_kind"], "comment_image")


if __name__ == "__main__":
    unittest.main()
