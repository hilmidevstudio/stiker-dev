import asyncio
import unittest

import httpx

from backend.media_gateway import MediaGateway, MediaGatewayError


def _chunk(fourcc: bytes, payload: bytes) -> bytes:
    result = fourcc + len(payload).to_bytes(4, "little") + payload
    if len(payload) & 1:
        result += b"\x00"
    return result


def _static_webp() -> bytes:
    width = 16
    height = 16
    vp8x = bytes([0x10, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    vp8 = bytes([0, 0, 0, 0x9d, 0x01, 0x2a, 16, 0, 16, 0])
    body = b"WEBP" + _chunk(b"VP8X", vp8x) + _chunk(b"VP8 ", vp8)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


class TestMediaGateway(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_and_validates_webp_from_allowed_host(self):
        fixture = _static_webp()
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, content=fixture, headers={"content-type": "image/webp"}
        ))
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"], transport=transport)
        result = await gateway.fetch("https://cdn.example.test/sticker.webp?sig=private")
        self.assertEqual(result, fixture)

    async def test_rejects_unapproved_host_without_network_request(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, content=_static_webp())
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"], transport=httpx.MockTransport(handler))
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://attacker.example/asset.webp")
        self.assertEqual(context.exception.error_code, "MEDIA_URL_NOT_ALLOWED")
        self.assertEqual(calls, [])

    async def test_rejects_http_scheme_and_ip_literal(self):
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"])
        for url in ("http://cdn.example.test/a.webp", "https://127.0.0.1/a.webp"):
            with self.subTest(url=url):
                with self.assertRaises(MediaGatewayError):
                    await gateway.fetch(url)

    async def test_redirect_destination_is_revalidated(self):
        calls = []
        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(302, headers={"location": "https://outside.example/asset.webp"})
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"], transport=httpx.MockTransport(handler))
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://cdn.example.test/first.webp")
        self.assertEqual(context.exception.error_code, "MEDIA_URL_NOT_ALLOWED")
        self.assertEqual(calls, ["cdn.example.test"])

    async def test_rejects_invalid_webp_binary(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, content=b"not a webp", headers={"content-type": "application/octet-stream"}
        ))
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"], transport=transport)
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://cdn.example.test/not.webp")
        self.assertEqual(context.exception.error_code, "INVALID_MEDIA_FILE")

    async def test_enforces_content_length_limit(self):
        fixture = _static_webp()
        # Declared size is checked before the body is accepted; this response advertises too much.
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200,
            content=fixture,
            headers={"content-type": "image/webp", "content-length": "2048"},
        ))
        gateway = MediaGateway(allowed_hosts=["cdn.example.test"], max_bytes=1024, transport=transport)
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://cdn.example.test/large.webp")
        self.assertEqual(context.exception.error_code, "MEDIA_TOO_LARGE")

    def test_rejects_invalid_configured_size_ceiling(self):
        with self.assertRaises(ValueError):
            MediaGateway(max_bytes=10)
        with self.assertRaises(ValueError):
            MediaGateway(max_bytes=6_000_000)

    async def test_repeated_fetch_uses_bounded_process_cache(self):
        calls = []
        fixture = _static_webp()

        def handler(request):
            calls.append(request.url.path)
            return httpx.Response(200, content=fixture, headers={"content-type": "image/webp"})

        gateway = MediaGateway(
            allowed_hosts=["cdn.example.test"],
            transport=httpx.MockTransport(handler),
            cache_ttl_seconds=60,
            max_cache_bytes=4096,
        )
        first = await gateway.fetch("https://cdn.example.test/sticker.webp?signature=secret")
        second = await gateway.fetch("https://cdn.example.test/sticker.webp?signature=secret")
        self.assertEqual(first, fixture)
        self.assertEqual(second, fixture)
        self.assertEqual(calls, ["/sticker.webp"])
        self.assertLessEqual(gateway._cache_bytes, gateway.max_cache_bytes)

    async def test_process_rate_guard_rejects_request_after_configured_window_budget(self):
        fixture = _static_webp()
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, content=fixture, headers={"content-type": "image/webp"}
        ))
        gateway = MediaGateway(
            allowed_hosts=["cdn.example.test"],
            transport=transport,
            max_requests_per_minute=10,
            cache_ttl_seconds=0,
        )
        for index in range(10):
            await gateway.fetch(f"https://cdn.example.test/{index}.webp")
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://cdn.example.test/11.webp")
        self.assertEqual(context.exception.status_code, 429)
        self.assertEqual(context.exception.error_code, "MEDIA_RATE_LIMITED")

    async def test_concurrency_guard_rejects_excess_upstream_fetches(self):
        fixture = _static_webp()
        started = asyncio.Event()

        async def handler(request):
            started.set()
            await asyncio.sleep(0.25)
            return httpx.Response(200, content=fixture, headers={"content-type": "image/webp"})

        gateway = MediaGateway(
            allowed_hosts=["cdn.example.test"],
            transport=httpx.MockTransport(handler),
            max_concurrent=1,
            cache_ttl_seconds=0,
        )
        first_task = asyncio.create_task(gateway.fetch("https://cdn.example.test/first.webp"))
        await started.wait()
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://cdn.example.test/second.webp")
        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.error_code, "MEDIA_GATEWAY_BUSY")
        self.assertEqual(await first_task, fixture)

    async def test_rejects_general_tiktok_web_host_not_cdn_allowlist(self):
        gateway = MediaGateway()
        with self.assertRaises(MediaGatewayError) as context:
            await gateway.fetch("https://www.tiktok.com/anything.webp")
        self.assertEqual(context.exception.error_code, "MEDIA_URL_NOT_ALLOWED")

    def test_rejects_unsafe_gateway_limits(self):
        with self.assertRaises(ValueError):
            MediaGateway(max_redirects=6)
        with self.assertRaises(ValueError):
            MediaGateway(max_concurrent=0)
        with self.assertRaises(ValueError):
            MediaGateway(max_requests_per_minute=9)
        with self.assertRaises(ValueError):
            MediaGateway(max_cache_bytes=65 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
