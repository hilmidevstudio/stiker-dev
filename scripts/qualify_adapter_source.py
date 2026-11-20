"""Qualify a captured adapter response without making any network requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.source_qualification import qualify_sticker_source_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether a captured, normalized comment response and media file "
            "meet StickerDrop's exact-comment/sticker/WebP source contract. "
            "This tool is offline and does not contact TikTok or any provider."
        )
    )
    parser.add_argument("--fixture", required=True, help="Normalized JSON response fixture")
    parser.add_argument("--comment-id", required=True, help="Exact target comment ID")
    parser.add_argument("--media-file", help="Exact downloaded WebP file from the authorized source")
    parser.add_argument("--expected-sha256", help="Optional SHA-256 expected for the media file")
    parser.add_argument(
        "--allowed-host",
        action="append",
        dest="allowed_hosts",
        help="Additional exact CDN root to allow (repeatable); built-in TikTok CDN roots remain enabled",
    )
    args = parser.parse_args()

    report = qualify_sticker_source_file(
        args.fixture,
        args.comment_id,
        media_path=args.media_file,
        expected_sha256=args.expected_sha256,
        allowed_hosts=args.allowed_hosts,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "qualified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
