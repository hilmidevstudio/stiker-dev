"""
Integration and End-to-End API Tests for StickerDrop FastAPI Backend.
Uses starlette/fastapi TestClient.
"""

import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend.main import app


class TestBackendAPI(unittest.TestCase):

    def setUp(self):
        self._previous_provider = os.environ.get("EXTRACTION_PROVIDER")
        os.environ["EXTRACTION_PROVIDER"] = "mock"
        self.client = TestClient(app)

    def tearDown(self):
        if self._previous_provider is None:
            os.environ.pop("EXTRACTION_PROVIDER", None)
        else:
            os.environ["EXTRACTION_PROVIDER"] = self._previous_provider

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["service"], "StickerDrop Backend API")
        self.assertEqual(data["status"], "online")
        self.assertIn("endpoints", data)

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



if __name__ == "__main__":
    unittest.main()
