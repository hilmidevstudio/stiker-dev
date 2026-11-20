import hashlib
import json
import unittest

import httpx

from scripts.live_source_acceptance import (
    AcceptanceFailure,
    GOLDEN_COMMENT_ID,
    GOLDEN_POST_ID,
    run_acceptance,
)


def _chunk(name: bytes, data: bytes) -> bytes:
    return name + len(data).to_bytes(4, "little") + data + (b"\x00" if len(data) % 2 else b"")


def _valid_webp() -> bytes:
    # 1x1 structurally valid static WebP. Compliance sizing is reported separately.
    vp8x = bytes([0x10, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    vp8 = b"\x00\x00\x00\x9d\x01\x2a\x00\x00\x00\x00"
    body = b"WEBP" + _chunk(b"VP8X", vp8x) + _chunk(b"VP8 ", vp8)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


class AcceptanceTransport(httpx.BaseTransport):
    def __init__(self, *, provider="authorized_source", ready=True, resolved_post=GOLDEN_POST_ID,
                 resolved_comment=GOLDEN_COMMENT_ID, extracted_provider="authorized_source",
                 extracted_comment=GOLDEN_COMMENT_ID, media_url=None, media_bytes=None,
                 external_credit_provider=False, billing_model="operator_managed", media_status=200):
        self.calls = []
        self.media_url = media_url or "https://p16.tiktokcdn-us.com/path/sticker.webp?x-signature=do-not-log"
        self.media_bytes = _valid_webp() if media_bytes is None else media_bytes
        self.provider = provider
        self.ready = ready
        self.resolved_post = resolved_post
        self.resolved_comment = resolved_comment
        self.extracted_provider = extracted_provider
        self.extracted_comment = extracted_comment
        self.external_credit_provider = external_credit_provider
        self.billing_model = billing_model
        self.media_status = media_status

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        if path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        if path.endswith("/v1/extraction-status"):
            return httpx.Response(200, json={
                "provider": self.provider,
                "configured": self.ready,
                "ready": self.ready,
                "provider_called": False,
                "external_credit_provider": self.external_credit_provider,
                "external_service": True,
                "billing_model": self.billing_model,
            })
        if path.endswith("/v1/resolve-link"):
            return httpx.Response(200, json={
                "success": True,
                "post_id": self.resolved_post,
                "video_id": self.resolved_post,
                "comment_id": self.resolved_comment,
                "post_type": "video",
            })
        if path.endswith("/v1/resolve-and-extract"):
            return httpx.Response(200, json={
                "success": True,
                "video_id": GOLDEN_POST_ID,
                "comment_id": self.extracted_comment,
                "provider_used": self.extracted_provider,
                "sticker": {
                    "sticker_id": "sticker-golden",
                    "sticker_type": 1,
                    "is_animated": False,
                    "format": "webp",
                    "media_url": self.media_url,
                    "static_url": self.media_url,
                    "animated_url": None,
                    "width": 1,
                    "height": 1,
                },
            })
        if path.endswith("/v1/media-proxy"):
            return httpx.Response(self.media_status, content=self.media_bytes, headers={"content-type": "image/webp"})
        return httpx.Response(404, json={"detail": "not found"})


class TestLiveSourceAcceptance(unittest.TestCase):
    def _run(self, transport, **kwargs):
        kwargs.setdefault("expected_sha256", hashlib.sha256(_valid_webp()).hexdigest())
        return run_acceptance(
            backend_url="https://api.example.test",
            comment_url="https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/",
            transport=transport,
            **kwargs,
        )

    def test_full_authorized_source_flow_qualifies_and_redacts_signed_url(self):
        transport = AcceptanceTransport()
        report = self._run(transport)
        self.assertEqual(report["status"], "qualified")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["target"]["comment_id"], GOLDEN_COMMENT_ID)
        serialized = json.dumps(report)
        self.assertNotIn("x-signature", serialized)
        self.assertNotIn("do-not-log", serialized)
        self.assertIn(("POST", "/v1/media-proxy"), transport.calls)

    def test_paid_provider_is_rejected_before_extraction_call(self):
        transport = AcceptanceTransport(provider="scrapecreators")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "AUTHORIZED_SOURCE_NOT_SELECTED")
        self.assertNotIn(("POST", "/v1/resolve-and-extract"), transport.calls)

    def test_disabled_provider_is_rejected_before_extraction_call(self):
        transport = AcceptanceTransport(provider="disabled", ready=False)
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "AUTHORIZED_SOURCE_NOT_SELECTED")
        self.assertNotIn(("POST", "/v1/resolve-and-extract"), transport.calls)

    def test_source_not_ready_is_rejected(self):
        transport = AcceptanceTransport(ready=False)
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "AUTHORIZED_SOURCE_NOT_CONFIGURED_OR_NOT_READY")

    def test_exact_post_mismatch_is_rejected(self):
        transport = AcceptanceTransport(resolved_post="7700000000000000000")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "RESOLVED_POST_ID_MISMATCH")

    def test_exact_comment_mismatch_is_rejected(self):
        transport = AcceptanceTransport(resolved_comment="7700000000000000000")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "RESOLVED_COMMENT_ID_MISMATCH")

    def test_extraction_provider_mismatch_is_rejected(self):
        transport = AcceptanceTransport(extracted_provider="scrapesocial")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "EXTRACTION_PROVIDER_MISMATCH")

    def test_disallowed_media_host_is_rejected_before_proxy_call(self):
        transport = AcceptanceTransport(media_url="https://attacker.example/sticker.webp")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "MEDIA_URL_HOST_NOT_ALLOWED")
        self.assertNotIn(("POST", "/v1/media-proxy"), transport.calls)

    def test_invalid_media_bytes_are_rejected(self):
        transport = AcceptanceTransport(media_bytes=b"not a WebP")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport, expected_sha256=None)
        self.assertEqual(raised.exception.issue, "MEDIA_BINARY_NOT_VALID_WEBP")

    def test_hash_mismatch_fails_golden_gate(self):
        transport = AcceptanceTransport()
        with self.assertRaises(AcceptanceFailure) as raised:
            run_acceptance(
                backend_url="https://api.example.test",
                comment_url="https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/",
                expected_sha256="0" * 64,
                transport=transport,
            )
        self.assertEqual(raised.exception.issue, "SOURCE_QUALIFICATION_GATE_FAILED")
        self.assertIn("SHA256_MISMATCH", raised.exception.report["issues"])


    def test_external_credit_provider_configuration_is_rejected(self):
        transport = AcceptanceTransport(external_credit_provider=True)
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "UNEXPECTED_PROVIDER_BILLING_CONFIGURATION")
        self.assertNotIn(("POST", "/v1/resolve-and-extract"), transport.calls)

    def test_wrong_billing_model_is_rejected(self):
        transport = AcceptanceTransport(billing_model="third_party_credits")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "UNEXPECTED_PROVIDER_BILLING_CONFIGURATION")

    def test_extracted_comment_id_mismatch_is_rejected(self):
        transport = AcceptanceTransport(extracted_comment="7700000000000000000")
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "EXTRACTED_COMMENT_ID_MISMATCH")

    def test_media_proxy_non_200_is_rejected(self):
        transport = AcceptanceTransport(media_status=502)
        with self.assertRaises(AcceptanceFailure) as raised:
            self._run(transport)
        self.assertEqual(raised.exception.issue, "MEDIA_PROXY_HTTP_502")

    def test_backend_url_with_credentials_is_rejected(self):
        with self.assertRaises(ValueError) as raised:
            run_acceptance(
                backend_url="https://user:password@api.example.test",
                comment_url="https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/",
                transport=AcceptanceTransport(),
            )
        self.assertEqual(str(raised.exception), "BACKEND_URL_INVALID")

    def test_backend_http_not_allowed_without_localhost_flag(self):
        with self.assertRaises(ValueError) as raised:
            run_acceptance(
                backend_url="http://localhost:8000",
                comment_url="https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/",
                transport=AcceptanceTransport(),
            )
        self.assertEqual(str(raised.exception), "BACKEND_URL_MUST_USE_HTTPS")

    def test_localhost_http_can_be_explicitly_enabled_for_development(self):
        report = run_acceptance(
            backend_url="http://localhost:8000",
            comment_url="https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/",
            expected_sha256=hashlib.sha256(_valid_webp()).hexdigest(),
            allow_insecure_localhost=True,
            transport=AcceptanceTransport(),
        )
        self.assertEqual(report["status"], "qualified")


if __name__ == "__main__":
    unittest.main()
