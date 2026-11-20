"""
Integration and End-to-End API Tests for StickerDrop FastAPI Backend.
Uses starlette/fastapi TestClient.
"""

import unittest
import os
import sys
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend.main import app


class TestBackendAPI(unittest.TestCase):

    def setUp(self):
        self._previous_provider = os.environ.get("EXTRACTION_PROVIDER")
        self._previous_app_env = os.environ.get("APP_ENV")
        os.environ["EXTRACTION_PROVIDER"] = "mock"
        os.environ["APP_ENV"] = "test"
        self.client = TestClient(app)

    def tearDown(self):
        if self._previous_provider is None:
            os.environ.pop("EXTRACTION_PROVIDER", None)
        else:
            os.environ["EXTRACTION_PROVIDER"] = self._previous_provider
        if self._previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = self._previous_app_env

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["service"], "StickerDrop Backend API")
        self.assertEqual(data["status"], "online")
        self.assertIn("endpoints", data)

    def test_media_proxy_returns_validated_webp_bytes_without_exposing_url_in_path(self):
        fake_gateway = type("FakeGateway", (), {})()
        fake_gateway.fetch = AsyncMock(return_value=b"RIFF" + b"\x00" * 4 + b"WEBP-test")
        with patch("backend.main.media_gateway", fake_gateway):
            response = self.client.post(
                "/v1/media-proxy",
                json={"url": "https://p16-tiktok-dm-sticker-sign.tiktokcdn-us.com/sticker.awebp?sig=hidden"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"RIFF" + b"\x00" * 4 + b"WEBP-test")
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_media_proxy_rejects_unapproved_host(self):
        response = self.client.post(
            "/v1/media-proxy",
            json={"url": "https://attacker.example/sticker.webp"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "MEDIA_URL_NOT_ALLOWED")

    def test_media_proxy_rate_limit_returns_retry_after_header(self):
        from backend.media_gateway import MediaGatewayError

        fake_gateway = type("FakeGateway", (), {})()
        fake_gateway.fetch = AsyncMock(side_effect=MediaGatewayError(
            "Media gateway is receiving too many requests. Please retry shortly.",
            "MEDIA_RATE_LIMITED",
            429,
        ))
        with patch("backend.main.media_gateway", fake_gateway):
            response = self.client.post(
                "/v1/media-proxy",
                json={"url": "https://p16-tiktok-dm-sticker-sign.tiktokcdn-us.com/sticker.webp"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers.get("retry-after"), "60")
        self.assertEqual(response.json()["error_code"], "MEDIA_RATE_LIMITED")

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["cors_enabled"])

    def test_cors_headers(self):
        response = self.client.options(
            "/v1/resolve-and-extract",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access-control-allow-origin", response.headers)
        # When allow_credentials=True, Starlette echoes the requested Origin in accordance with W3C CORS specs
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_resolve_and_extract_post_success(self):
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=7708394712596972308"
        )
        payload = {"url": url}
        response = self.client.post("/v1/resolve-and-extract", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["video_id"], "7708356144804236564")
        self.assertEqual(data["comment_id"], "7708394712596972308")
        self.assertEqual(data["author"]["unique_id"], "crazyolshop1")
        self.assertEqual(data["comment_text"], "ngajak ribut kamu? 🗿")

        # Verify sticker metadata
        sticker = data["sticker"]
        self.assertEqual(sticker["sticker_id"], "7421890123456789012")
        self.assertTrue(sticker["is_animated"])
        self.assertEqual(sticker["format"], "awebp")
        self.assertIn("prabowo_animated.awebp", sticker["media_url"])
        self.assertEqual(sticker["width"], 300)
        self.assertEqual(sticker["height"], 300)

    def test_resolve_and_extract_get_success(self):
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=7708394712596972308"
        )
        response = self.client.get(
            "/v1/resolve-and-extract",
            params={"url": url}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["comment_id"], "7708394712596972308")
        self.assertTrue(data["sticker"]["is_animated"])

    def test_video_link_without_comment_id_error(self):
        url = "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
        response = self.client.post("/v1/resolve-and-extract", json={"url": url})
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "MISSING_COMMENT_ID")

    def test_invalid_url_string_error(self):
        response = self.client.post("/v1/resolve-and-extract", json={"url": "not a valid url"})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "INVALID_URL")


    def test_validation_error_does_not_echo_submitted_signed_url(self):
        secret_url = "https://www.tiktok.com/@x/video/123?x-signature=DO_NOT_ECHO"
        response = self.client.post(
            "/v1/resolve-and-extract",
            json={"url": secret_url, "provider": "mock"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "VALIDATION_ERROR")
        self.assertNotIn("DO_NOT_ECHO", response.text)
        self.assertNotIn("x-signature", response.text)

    def test_invalid_url_error_does_not_echo_raw_input(self):
        private_value = "private-token-should-not-echo"
        with self.assertLogs("stickerdrop.backend", level="WARNING") as captured:
            response = self.client.post(
                "/v1/resolve-and-extract",
                json={"url": private_value},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_URL")
        self.assertNotIn(private_value, response.text)
        self.assertNotIn(private_value, "\n".join(captured.output))

    def test_post_without_post_id_does_not_echo_resolved_query(self):
        signed_url = "https://www.tiktok.com/@x/not-a-post?x-signature=DO_NOT_ECHO"
        response = self.client.post(
            "/v1/resolve-and-extract",
            json={"url": signed_url},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "VIDEO_ID_NOT_FOUND")
        self.assertNotIn("DO_NOT_ECHO", response.text)

    def test_public_client_cannot_override_provider(self):
        response = self.client.post(
            "/v1/resolve-and-extract",
            json={"url": "https://www.tiktok.com/@nyariprompt/video/7708356144804236564?share_comment_id=7708394712596972308", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "VALIDATION_ERROR")

    def test_comment_without_sticker_error(self):
        # 7708111111111111111 is in the mock fixture but has NO sticker
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=7708111111111111111"
        )
        response = self.client.post("/v1/resolve-and-extract", json={"url": url})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "STICKER_NOT_FOUND")

    def test_comment_not_found_error(self):
        # 9999999999999999999 does not exist in the mock fixture
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=9999999999999999999"
        )
        response = self.client.post("/v1/resolve-and-extract", json={"url": url})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "COMMENT_NOT_FOUND")

    def test_arbitrary_missing_comment_is_not_synthesized(self):
        # Any unknown ID must remain a 404; the backend must never create demo metadata.
        url = (
            "https://www.tiktok.com/@nyariprompt/video/7708356144804236564"
            "?share_comment_id=8888888888888888888"
        )
        response = self.client.post("/v1/resolve-and-extract", json={"url": url})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "COMMENT_NOT_FOUND")

    def test_photo_comment_link_is_not_rewritten_as_video(self):
        from backend.link_resolver import TikTokLinkResolver
        import asyncio
        target = asyncio.run(TikTokLinkResolver().resolve(
            "https://www.tiktok.com/@aranaarea/photo/7706876060025408788"
            "?share_comment_id=7709075303109116690&comment_author_id=6919262587071333377&aweme_type=150",
            follow_redirects=False,
        ))
        self.assertEqual(target.post_type, "photo")
        self.assertEqual(target.video_id, "7706876060025408788")
        self.assertEqual(target.comment_id, "7709075303109116690")
        self.assertIn("/photo/7706876060025408788", target.canonical_url)


    def test_resolve_link_endpoint_does_not_call_provider(self):
        url = (
            "https://www.tiktok.com/@livorwed/photo/7709797914675121428"
            "?share_comment_id=7709899214972928776&aweme_type=150"
        )
        response = self.client.post("/v1/resolve-link", json={"url": url})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["provider_called"])
        self.assertEqual(data["post_type"], "photo")
        self.assertEqual(data["comment_id"], "7709899214972928776")
        self.assertIn("/photo/7709797914675121428", data["canonical_url"])


    def test_extraction_status_reports_mock_without_calling_provider(self):
        response = self.client.get("/v1/extraction-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider"], "mock")
        self.assertFalse(data["provider_called"])
        self.assertFalse(data["external_credit_provider"])

    def test_disabled_provider_fails_closed_without_using_api_key(self):
        previous_provider = os.environ.get("EXTRACTION_PROVIDER")
        previous_key = os.environ.get("SCRAPECREATORS_API_KEY")
        try:
            os.environ["EXTRACTION_PROVIDER"] = "disabled"
            os.environ["SCRAPECREATORS_API_KEY"] = "deliberately-present-test-key"
            response = self.client.post(
                "/v1/resolve-and-extract",
                json={"url": "https://www.tiktok.com/@sample/video/1234567890123456789?share_comment_id=9876543210987654321"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["error_code"], "EXTRACTION_SOURCE_NOT_CONFIGURED")
        finally:
            if previous_provider is None:
                os.environ.pop("EXTRACTION_PROVIDER", None)
            else:
                os.environ["EXTRACTION_PROVIDER"] = previous_provider
            if previous_key is None:
                os.environ.pop("SCRAPECREATORS_API_KEY", None)
            else:
                os.environ["SCRAPECREATORS_API_KEY"] = previous_key


if __name__ == "__main__":
    unittest.main()
