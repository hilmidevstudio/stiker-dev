"""Live acceptance test for the operator-managed StickerDrop source.

This script talks only to the configured StickerDrop backend. It never calls
ScrapeCreators, ScrapeSocial, TikTok APIs, or the source service directly.
The backend must explicitly report `authorized_source` before extraction is
attempted. Signed media URLs and user-provided share URLs are never printed or
written to the JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.media_gateway import MediaGateway, MediaGatewayError
from backend.source_qualification import qualify_sticker_source
from src.media.validator import WebPBinaryParser


GOLDEN_COMMENT_URL = "https://vt.tiktok.com/ZS9PN7MkrbuMs-swyrV/"
GOLDEN_POST_ID = "7700924470206156050"
GOLDEN_COMMENT_ID = "7700946321838818056"
GOLDEN_SHA256 = "b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878"
MAX_JSON_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MEDIA_RESPONSE_BYTES = 5_000_000


class AcceptanceFailure(RuntimeError):
    """A safe, machine-readable acceptance failure without upstream payloads."""

    def __init__(self, issue: str, report: Dict[str, Any]):
        super().__init__(issue)
        self.issue = issue
        self.report = report


def _validated_backend_url(raw_url: str, allow_insecure_localhost: bool) -> tuple[str, str]:
    if not isinstance(raw_url, str) or not raw_url.strip() or len(raw_url) > 512:
        raise ValueError("BACKEND_URL_REQUIRED_OR_INVALID")
    try:
        parsed = urlsplit(raw_url.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("BACKEND_URL_INVALID") from exc

    if (
        not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "\\" in parsed.path
        or any(part == ".." for part in parsed.path.split("/"))
    ):
        raise ValueError("BACKEND_URL_INVALID")

    local_host = host.lower() in {"localhost", "127.0.0.1", "::1"}
    secure = parsed.scheme.lower() == "https"
    local_http = parsed.scheme.lower() == "http" and local_host and allow_insecure_localhost
    if not secure and not local_http:
        raise ValueError("BACKEND_URL_MUST_USE_HTTPS")
    if port is not None and not (1 <= port <= 65535):
        raise ValueError("BACKEND_URL_INVALID_PORT")

    path = parsed.path.rstrip("/")
    base_url = urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))
    origin = urlunsplit((parsed.scheme.lower(), parsed.netloc, "", "", ""))
    return base_url, origin


def _validate_comment_url(raw_url: str) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip() or len(raw_url) > 4096:
        raise ValueError("TIKTOK_COMMENT_URL_REQUIRED_OR_INVALID")
    try:
        parsed = urlsplit(raw_url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ValueError("TIKTOK_COMMENT_URL_INVALID") from exc
    if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
        raise ValueError("TIKTOK_COMMENT_URL_MUST_BE_HTTPS")
    if not (host == "tiktok.com" or host.endswith(".tiktok.com")):
        raise ValueError("TIKTOK_COMMENT_URL_HOST_NOT_ALLOWED")
    return raw_url.strip()


def _read_limited(response: httpx.Response, limit: int, too_large_code: str) -> bytes:
    declared = response.headers.get("content-length")
    if declared:
        try:
            if int(declared) > limit:
                raise ValueError(too_large_code)
        except ValueError as exc:
            if str(exc) == too_large_code:
                raise
            raise ValueError("RESPONSE_CONTENT_LENGTH_INVALID") from exc
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > limit:
            raise ValueError(too_large_code)
    return bytes(body)


def _request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        with client.stream(method, url, json=json_body) as response:
            if response.status_code != 200:
                raise ValueError(f"BACKEND_HTTP_{response.status_code}")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise ValueError("BACKEND_JSON_CONTENT_TYPE_INVALID")
            body = _read_limited(response, MAX_JSON_RESPONSE_BYTES, "BACKEND_JSON_RESPONSE_TOO_LARGE")
    except httpx.TimeoutException as exc:
        raise ValueError("BACKEND_REQUEST_TIMEOUT") from exc
    except httpx.HTTPError as exc:
        raise ValueError("BACKEND_CONNECTION_FAILED") from exc

    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("BACKEND_JSON_RESPONSE_INVALID") from exc
    if not isinstance(decoded, dict):
        raise ValueError("BACKEND_JSON_RESPONSE_INVALID")
    return decoded


def _request_media(client: httpx.Client, url: str, media_url: str) -> bytes:
    try:
        with client.stream("POST", url, json={"url": media_url}) as response:
            if response.status_code != 200:
                raise ValueError(f"MEDIA_PROXY_HTTP_{response.status_code}")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"image/webp", "image/x-webp", "image/awebp"}:
                raise ValueError("MEDIA_PROXY_CONTENT_TYPE_INVALID")
            return _read_limited(response, MAX_MEDIA_RESPONSE_BYTES, "MEDIA_PROXY_RESPONSE_TOO_LARGE")
    except httpx.TimeoutException as exc:
        raise ValueError("MEDIA_PROXY_TIMEOUT") from exc
    except httpx.HTTPError as exc:
        raise ValueError("MEDIA_PROXY_CONNECTION_FAILED") from exc


def _new_report(origin: str, post_id: str, comment_id: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "not_qualified",
        "backend_origin": origin,
        "target": {"post_id": post_id, "comment_id": comment_id},
        "provider": None,
        "billing_model": None,
        "checks": {
            "backend_healthy": False,
            "authorized_source_selected": False,
            "source_configured": False,
            "external_credit_provider_disabled": False,
            "post_id_matches": False,
            "comment_id_matches": False,
            "extraction_provider_matches": False,
            "sticker_metadata_present": False,
            "media_host_allowed": False,
            "media_proxy_downloaded": False,
            "media_webp_valid": False,
            "expected_sha256_matches": None,
        },
        "media": None,
        "issues": [],
    }


def _fail(report: Dict[str, Any], issue: str) -> None:
    if issue not in report["issues"]:
        report["issues"].append(issue)
    raise AcceptanceFailure(issue, report)


def run_acceptance(
    *,
    backend_url: str,
    comment_url: str,
    expected_post_id: str = GOLDEN_POST_ID,
    expected_comment_id: str = GOLDEN_COMMENT_ID,
    expected_sha256: Optional[str] = GOLDEN_SHA256,
    timeout_seconds: float = 30.0,
    allow_insecure_localhost: bool = False,
    media_out_path: Optional[str | Path] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> Dict[str, Any]:
    """Run end-to-end acceptance through the app's configured authorized source.

    The supplied HTTP transport is intended for unit tests only. Normal CLI usage
    always talks to the configured backend URL.
    """
    base_url, origin = _validated_backend_url(backend_url, allow_insecure_localhost)
    safe_comment_url = _validate_comment_url(comment_url)

    if not re.fullmatch(r"\d{5,30}", str(expected_post_id)):
        raise ValueError("EXPECTED_POST_ID_INVALID")
    if not re.fullmatch(r"\d{5,30}", str(expected_comment_id)):
        raise ValueError("EXPECTED_COMMENT_ID_INVALID")
    if expected_sha256 is not None:
        expected_sha256 = expected_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError("EXPECTED_SHA256_INVALID")

    report = _new_report(origin, str(expected_post_id), str(expected_comment_id))
    client_options: Dict[str, Any] = {
        "timeout": httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0)),
        "follow_redirects": False,
    }
    if transport is not None:
        client_options["transport"] = transport

    try:
        with httpx.Client(**client_options) as client:
            health = _request_json(client, "GET", f"{base_url}/health")
            report["checks"]["backend_healthy"] = health.get("status") == "ok"
            if not report["checks"]["backend_healthy"]:
                _fail(report, "BACKEND_HEALTH_CHECK_FAILED")

            provider_status = _request_json(client, "GET", f"{base_url}/v1/extraction-status")
            report["provider"] = provider_status.get("provider")
            report["billing_model"] = provider_status.get("billing_model")
            report["checks"]["authorized_source_selected"] = provider_status.get("provider") == "authorized_source"
            report["checks"]["source_configured"] = provider_status.get("configured") is True and provider_status.get("ready") is True
            report["checks"]["external_credit_provider_disabled"] = provider_status.get("external_credit_provider") is False

            if not report["checks"]["authorized_source_selected"]:
                _fail(report, "AUTHORIZED_SOURCE_NOT_SELECTED")
            if not report["checks"]["source_configured"]:
                _fail(report, "AUTHORIZED_SOURCE_NOT_CONFIGURED_OR_NOT_READY")
            if not report["checks"]["external_credit_provider_disabled"] or provider_status.get("billing_model") != "operator_managed":
                _fail(report, "UNEXPECTED_PROVIDER_BILLING_CONFIGURATION")
            if provider_status.get("provider_called") is not False:
                _fail(report, "STATUS_ENDPOINT_MUST_NOT_CALL_SOURCE")

            resolved = _request_json(
                client,
                "POST",
                f"{base_url}/v1/resolve-link",
                json_body={"url": safe_comment_url},
            )
            resolved_post = str(resolved.get("post_id") or resolved.get("video_id") or "")
            resolved_comment = str(resolved.get("comment_id") or "")
            report["checks"]["post_id_matches"] = resolved_post == str(expected_post_id)
            report["checks"]["comment_id_matches"] = resolved_comment == str(expected_comment_id)
            if not report["checks"]["post_id_matches"]:
                _fail(report, "RESOLVED_POST_ID_MISMATCH")
            if not report["checks"]["comment_id_matches"]:
                _fail(report, "RESOLVED_COMMENT_ID_MISMATCH")

            extracted = _request_json(
                client,
                "POST",
                f"{base_url}/v1/resolve-and-extract",
                json_body={"url": safe_comment_url},
            )
            report["checks"]["extraction_provider_matches"] = extracted.get("provider_used") == "authorized_source"
            if not report["checks"]["extraction_provider_matches"]:
                _fail(report, "EXTRACTION_PROVIDER_MISMATCH")
            if str(extracted.get("video_id") or "") != str(expected_post_id):
                _fail(report, "EXTRACTED_POST_ID_MISMATCH")
            if str(extracted.get("comment_id") or "") != str(expected_comment_id):
                _fail(report, "EXTRACTED_COMMENT_ID_MISMATCH")

            sticker = extracted.get("sticker")
            if not isinstance(sticker, dict) or not sticker.get("sticker_id") or not sticker.get("media_url"):
                _fail(report, "STICKER_METADATA_OR_MEDIA_URL_MISSING")
            report["checks"]["sticker_metadata_present"] = True

            media_url = sticker.get("media_url")
            try:
                normalized_media_url = MediaGateway().validate_url(media_url)
                media_host = urlsplit(normalized_media_url).hostname
                report["checks"]["media_host_allowed"] = True
            except (MediaGatewayError, TypeError, ValueError):
                _fail(report, "MEDIA_URL_HOST_NOT_ALLOWED")

            media_bytes = _request_media(client, f"{base_url}/v1/media-proxy", media_url)
            report["checks"]["media_proxy_downloaded"] = True
            metadata = WebPBinaryParser().parse(media_bytes)
            report["checks"]["media_webp_valid"] = bool(metadata.is_valid_webp)
            report["media"] = {
                "host": media_host,
                "file_size": metadata.file_size,
                "sha256": metadata.sha256,
                "is_animated": metadata.is_animated,
                "width": metadata.width,
                "height": metadata.height,
                "frame_count": metadata.frame_count,
                "duration_ms": metadata.duration_ms,
                "whatsapp_compliant": metadata.whatsapp_compliant,
                "compliance_issues": metadata.compliance_issues,
            }
            if not metadata.is_valid_webp:
                _fail(report, "MEDIA_BINARY_NOT_VALID_WEBP")

            report["checks"]["expected_sha256_matches"] = (
                metadata.sha256.lower() == expected_sha256 if expected_sha256 else None
            )
            synthetic_struct: Dict[str, Any] = {
                "sticker_id": str(sticker.get("sticker_id")),
                "sticker_type": int(sticker.get("sticker_type") or (2 if sticker.get("is_animated") else 1)),
                "animated_url" if sticker.get("is_animated") else "static_url": {
                    "url_list": [media_url],
                    "width": sticker.get("width"),
                    "height": sticker.get("height"),
                },
            }
            qualification = qualify_sticker_source(
                {"comments": [{"cid": str(expected_comment_id), "cmt_sticker_struct": synthetic_struct}]},
                str(expected_comment_id),
                media_bytes=media_bytes,
                expected_sha256=expected_sha256,
            )
            if qualification.get("status") != "qualified":
                for issue in qualification.get("issues", []):
                    if issue not in report["issues"]:
                        report["issues"].append(issue)
                _fail(report, "SOURCE_QUALIFICATION_GATE_FAILED")

            report["status"] = "qualified"
            if media_out_path is not None:
                try:
                    output_path = Path(media_out_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(media_bytes)
                    report["media"]["saved_to"] = str(output_path)
                except OSError:
                    _fail(report, "MEDIA_OUTPUT_WRITE_FAILED")
            return report

    except AcceptanceFailure:
        raise
    except ValueError as exc:
        _fail(report, str(exc) if re.fullmatch(r"[A-Z0-9_]+", str(exc)) else "ACCEPTANCE_VALIDATION_FAILED")
    except Exception as exc:
        # Never put arbitrary exception strings into the report: they can contain URLs.
        _fail(report, f"UNEXPECTED_{type(exc).__name__.upper()}")


def _write_json(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run StickerDrop live acceptance through an authorized source backend.")
    parser.add_argument("--backend-url", default=os.getenv("STICKERDROP_BACKEND_URL", ""), help="StickerDrop backend HTTPS base URL.")
    parser.add_argument("--comment-url", default=os.getenv("STICKERDROP_GOLDEN_COMMENT_URL", GOLDEN_COMMENT_URL), help="TikTok comment share URL; never printed or saved.")
    parser.add_argument("--expected-post-id", default=GOLDEN_POST_ID)
    parser.add_argument("--expected-comment-id", default=GOLDEN_COMMENT_ID)
    parser.add_argument("--expected-sha256", default=GOLDEN_SHA256, help="Use 'none' to skip the golden-byte hash comparison.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--allow-insecure-localhost", action="store_true", help="Allow plain HTTP only for localhost development backend.")
    parser.add_argument("--media-out", help="Optional path to save the validated WebP bytes after full qualification.")
    parser.add_argument("--report", default="artifacts/live-acceptance-report.json", help="Safe JSON report output path.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.backend_url:
        print("FAILED: BACKEND_URL_REQUIRED. Set STICKERDROP_BACKEND_URL or pass --backend-url.")
        return 2
    expected_hash = None if str(args.expected_sha256).strip().lower() == "none" else args.expected_sha256
    try:
        report = run_acceptance(
            backend_url=args.backend_url,
            comment_url=args.comment_url,
            expected_post_id=args.expected_post_id,
            expected_comment_id=args.expected_comment_id,
            expected_sha256=expected_hash,
            timeout_seconds=args.timeout,
            allow_insecure_localhost=args.allow_insecure_localhost,
            media_out_path=args.media_out,
        )
        _write_json(Path(args.report), report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nACCEPTANCE: {report['status'].upper()}")
        print(f"Safe report: {Path(args.report)}")
        return 0
    except AcceptanceFailure as exc:
        report = exc.report
        try:
            _write_json(Path(args.report), report)
        except OSError:
            pass
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nACCEPTANCE: FAILED ({exc.issue})")
        return 2
    except (ValueError, OSError) as exc:
        print(f"FAILED: {str(exc) if re.fullmatch(r'[A-Z0-9_]+', str(exc)) else 'INVALID_ARGUMENT_OR_OUTPUT_PATH'}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
