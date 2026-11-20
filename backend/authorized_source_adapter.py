"""HTTP bridge for an operator-managed, authorized extraction source.

This module does not scrape TikTok. It connects StickerDrop to a separately
operated source service that is authorized for the intended data acquisition.
The source service must implement the small JSON contract documented in
`docs/19-authorized-source-http-adapter.md`.
"""

from __future__ import annotations

import ipaddress
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx

from .extractor_adapter import (
    ExtractionException,
    ExtractorAdapter,
    ProviderAuthException,
)
from .provider_normalization import normalize_provider_page


_DEFAULT_TIMEOUT_SECONDS = 20.0
_DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MIN_RESPONSE_BYTES = 1024
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _validate_base_url(raw_url: str, *, app_env: Optional[str] = None) -> str:
    """Validate operator configuration, not user-supplied request data."""
    if not isinstance(raw_url, str) or not raw_url.strip() or len(raw_url) > 512:
        raise ExtractionException(
            "AUTHORIZED_SOURCE_BASE_URL is missing or invalid.",
            error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
            status_code=500,
        )

    try:
        parsed = urlsplit(raw_url.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        hostname = None
        port = None
        parsed = urlsplit("")

    if (
        not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "\\" in parsed.path
        or any(segment == ".." for segment in parsed.path.split("/"))
    ):
        raise ExtractionException(
            "AUTHORIZED_SOURCE_BASE_URL must be an absolute URL without credentials, query, fragment, or traversal segments.",
            error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
            status_code=500,
        )

    env = (app_env or os.getenv("APP_ENV", "production")).lower().strip()
    local_http_allowed = env in {"test", "development", "local"} and (
        hostname.lower() == "localhost" or hostname.lower() == "127.0.0.1"
    )
    if parsed.scheme.lower() != "https" and not (parsed.scheme.lower() == "http" and local_http_allowed):
        raise ExtractionException(
            "AUTHORIZED_SOURCE_BASE_URL must use HTTPS in production.",
            error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
            status_code=500,
        )

    if port is not None and not (1 <= port <= 65535):
        raise ExtractionException(
            "AUTHORIZED_SOURCE_BASE_URL contains an invalid port.",
            error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
            status_code=500,
        )

    # Reject literal IP addresses in production configuration. A managed source
    # should be addressed by its stable HTTPS service hostname, not a raw IP.
    try:
        ipaddress.ip_address(hostname)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False
    if is_ip_literal and not local_http_allowed:
        raise ExtractionException(
            "AUTHORIZED_SOURCE_BASE_URL must use a service hostname, not an IP literal.",
            error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
            status_code=500,
        )

    normalized_path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{parsed.netloc}{normalized_path}"


def authorized_source_configuration_status() -> Dict[str, Any]:
    """Return safe configuration information without making a network request."""
    base_url = os.getenv("AUTHORIZED_SOURCE_BASE_URL", "").strip()
    api_key = os.getenv("AUTHORIZED_SOURCE_API_KEY", "")
    configured = bool(base_url and api_key)
    if not configured:
        return {
            "provider": "authorized_source",
            "configured": False,
            "ready": False,
            "provider_called": False,
            "external_credit_provider": False,
            "external_service": True,
            "billing_model": "operator_managed",
        }

    try:
        _validate_base_url(base_url)
        ready = True
        configuration_error = None
    except ExtractionException:
        ready = False
        configuration_error = "AUTHORIZED_SOURCE_BASE_URL is invalid"

    status: Dict[str, Any] = {
        "provider": "authorized_source",
        "configured": True,
        "ready": ready,
        "provider_called": False,
        "external_credit_provider": False,
        "external_service": True,
        "billing_model": "operator_managed",
    }
    if configuration_error:
        status["configuration_error"] = configuration_error
    return status


class AuthorizedSourceAdapter(ExtractorAdapter):
    """Connect to an operator-managed source over a bounded JSON HTTP contract.

    It intentionally does not implement TikTok acquisition. The configured
    service must return exact comment objects, including real `cmt_sticker_struct`
    metadata when present. Sticker media bytes are subsequently fetched through
    StickerDrop's separate allowlisted media gateway.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_response_bytes: Optional[int] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        raw_base_url = base_url if base_url is not None else os.getenv("AUTHORIZED_SOURCE_BASE_URL", "")
        self.base_url = _validate_base_url(raw_base_url)
        self.api_key = api_key if api_key is not None else os.getenv("AUTHORIZED_SOURCE_API_KEY", "")
        if not self.api_key or len(self.api_key) > 4096:
            raise ExtractionException(
                "AUTHORIZED_SOURCE_API_KEY is not configured.",
                error_code="AUTHORIZED_SOURCE_NOT_CONFIGURED",
                status_code=503,
            )

        raw_timeout = timeout_seconds
        if raw_timeout is None:
            try:
                raw_timeout = float(os.getenv("AUTHORIZED_SOURCE_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)))
            except ValueError as exc:
                raise ExtractionException(
                    "AUTHORIZED_SOURCE_TIMEOUT_SECONDS must be a number.",
                    error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
                    status_code=500,
                ) from exc
        if raw_timeout < 1 or raw_timeout > 60:
            raise ExtractionException(
                "AUTHORIZED_SOURCE_TIMEOUT_SECONDS must be between 1 and 60.",
                error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
                status_code=500,
            )
        self.timeout_seconds = raw_timeout

        raw_max_bytes = max_response_bytes
        if raw_max_bytes is None:
            try:
                raw_max_bytes = int(os.getenv("AUTHORIZED_SOURCE_MAX_RESPONSE_BYTES", str(_DEFAULT_MAX_RESPONSE_BYTES)))
            except ValueError as exc:
                raise ExtractionException(
                    "AUTHORIZED_SOURCE_MAX_RESPONSE_BYTES must be an integer.",
                    error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
                    status_code=500,
                ) from exc
        if raw_max_bytes < _MIN_RESPONSE_BYTES or raw_max_bytes > _MAX_RESPONSE_BYTES:
            raise ExtractionException(
                "AUTHORIZED_SOURCE_MAX_RESPONSE_BYTES must be between 1024 and 10485760.",
                error_code="AUTHORIZED_SOURCE_CONFIG_INVALID",
                status_code=500,
            )
        self.max_response_bytes = raw_max_bytes
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "authorized_source"

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "StickerDrop-Authorized-Source/1.0",
        }
        options: Dict[str, Any] = {
            "timeout": self.timeout_seconds,
            "follow_redirects": False,
        }
        if self.transport is not None:
            options["transport"] = self.transport

        try:
            async with httpx.AsyncClient(**options) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    status_code = response.status_code
                    if status_code in {401, 403}:
                        raise ProviderAuthException(
                            "The configured authorized source rejected StickerDrop authentication."
                        )
                    if 300 <= status_code < 400:
                        raise ExtractionException(
                            "The authorized source attempted a redirect; redirects are disabled.",
                            error_code="AUTHORIZED_SOURCE_REDIRECT_REJECTED",
                            status_code=502,
                        )
                    if status_code == 429:
                        raise ExtractionException(
                            "The authorized source rate limit was reached.",
                            error_code="AUTHORIZED_SOURCE_RATE_LIMITED",
                            status_code=503,
                        )
                    if status_code >= 400:
                        raise ExtractionException(
                            f"The authorized source returned HTTP {status_code}.",
                            error_code="AUTHORIZED_SOURCE_REQUEST_FAILED",
                            status_code=502,
                            details={"upstream_status": status_code},
                        )
                    if status_code != 200:
                        raise ExtractionException(
                            "The authorized source returned an unexpected HTTP status.",
                            error_code="AUTHORIZED_SOURCE_INVALID_STATUS",
                            status_code=502,
                        )

                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type != "application/json" and not content_type.endswith("+json"):
                        raise ExtractionException(
                            "The authorized source did not return a JSON response.",
                            error_code="AUTHORIZED_SOURCE_INVALID_CONTENT_TYPE",
                            status_code=502,
                        )

                    declared_size = response.headers.get("content-length")
                    if declared_size:
                        try:
                            if int(declared_size) > self.max_response_bytes:
                                raise ExtractionException(
                                    "The authorized source response exceeds the configured size limit.",
                                    error_code="AUTHORIZED_SOURCE_RESPONSE_TOO_LARGE",
                                    status_code=502,
                                )
                        except ValueError as exc:
                            raise ExtractionException(
                                "The authorized source returned an invalid content length.",
                                error_code="AUTHORIZED_SOURCE_INVALID_RESPONSE",
                                status_code=502,
                            ) from exc

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.max_response_bytes:
                            raise ExtractionException(
                                "The authorized source response exceeds the configured size limit.",
                                error_code="AUTHORIZED_SOURCE_RESPONSE_TOO_LARGE",
                                status_code=502,
                            )

            try:
                decoded = json.loads(bytes(body).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExtractionException(
                    "The authorized source returned malformed JSON.",
                    error_code="AUTHORIZED_SOURCE_INVALID_RESPONSE",
                    status_code=502,
                ) from exc
            if not isinstance(decoded, dict):
                raise ExtractionException(
                    "The authorized source response must be a JSON object.",
                    error_code="AUTHORIZED_SOURCE_INVALID_RESPONSE",
                    status_code=502,
                )
            return decoded

        except (ExtractionException, ProviderAuthException):
            raise
        except httpx.TimeoutException as exc:
            raise ExtractionException(
                "Timed out waiting for the authorized extraction source.",
                error_code="AUTHORIZED_SOURCE_TIMEOUT",
                status_code=504,
            ) from None
        except httpx.HTTPError as exc:
            # Do not propagate the request URL, headers, or upstream body.
            raise ExtractionException(
                "Could not connect to the configured authorized extraction source.",
                error_code="AUTHORIZED_SOURCE_NETWORK_ERROR",
                status_code=502,
            ) from None
        except Exception:
            raise ExtractionException(
                "The authorized extraction source request failed unexpectedly.",
                error_code="AUTHORIZED_SOURCE_NETWORK_ERROR",
                status_code=502,
            ) from None

    async def fetch_comments(
        self, video_url: str, cursor: Any = 0, count: int = 50
    ) -> Dict[str, Any]:
        payload = {
            "video_url": video_url,
            "cursor": cursor,
            "count": max(1, min(int(count), 100)),
        }
        return normalize_provider_page(await self._post_json("/v1/comments", payload))

    async def fetch_replies(
        self, comment_id: str, video_url: str, cursor: Any = 0
    ) -> Dict[str, Any]:
        payload = {
            "comment_id": str(comment_id),
            "video_url": video_url,
            "cursor": cursor,
        }
        return normalize_provider_page(await self._post_json("/v1/replies", payload))
