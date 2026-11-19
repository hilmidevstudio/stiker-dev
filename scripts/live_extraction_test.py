"""
Live Extraction Test Script for StickerDrop.
Executes live end-to-end extraction against target TikTok comment:
Video ID: 7708356144804236564
Comment ID: 7708394712596972308
Author: @crazyolshop1
Target Sticker: Prabowo in red shirt
"""

import os
import sys
import json
import hashlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.link_resolver.resolver import TikTokLinkResolver
from src.extraction.adapter import ScrapeSocialAdapter, ScrapeCreatorsAdapter
from src.extraction.extractor import StickerExtractor
from src.media.validator import WebPBinaryParser
from src.storage.db import DatabaseManager
from src.storage.repository import StickerRepository


def run_live_test():
    print("=" * 70)
    print("STICKERDROP LIVE EXTRACTION TEST HARNESS")
    print("=" * 70)

    target_comment_url = os.getenv(
        "TEST_TIKTOK_COMMENT_URL",
        "https://vt.tiktok.com/ZS9f3yqSf57UR-naeU1/"
    )
    api_key = os.getenv("SCRAPESOCIAL_API_KEY") or os.getenv("SCRAPECREATORS_API_KEY")

    if not api_key:
        print("\n[!] SCRAPESOCIAL_API_KEY or SCRAPECREATORS_API_KEY environment variable is NOT set.")
        print("[!] To run live extraction, execute:")
        print("    $env:SCRAPESOCIAL_API_KEY = \"your_real_api_key_here\"")
        print("    python scripts/live_extraction_test.py")
        print("=" * 70)
        return 1

    print(f"\n1. Resolving Link: {target_comment_url}")
    resolver = TikTokLinkResolver()
    target = resolver.parse_url(target_comment_url, follow_redirects=True)
    print(f"   -> Canonical URL: {target.canonical_url}")
    print(f"   -> Video ID:      {target.video_id}")
    print(f"   -> Comment ID:    {target.comment_id}")
    print(f"   -> Author ID:     {target.author_id}")

    provider_name = "ScrapeSocial" if os.getenv("SCRAPESOCIAL_API_KEY") else "ScrapeCreators"
    base_url = os.getenv("SCRAPESOCIAL_BASE_URL", "https://api.scrapesocial.ai")
    adapter = ScrapeSocialAdapter(api_key=api_key, base_url=base_url)
    extractor = StickerExtractor(provider_adapter=adapter, link_resolver=resolver)

    print(f"\n2. Querying Provider: {provider_name} ({base_url})")
    result = extractor.extract_by_ids(
        video_id=target.video_id,
        comment_id=target.comment_id,
        canonical_url=target.canonical_url,
        download_media=True
    )

    if not result.success:
        print(f"\n[X] Extraction Failed: {result.error_message}")
        return 2

    print("\n[V] Extraction Succeeded!")
    print(f"   -> Comment ID:       {result.target_comment_id}")
    print(f"   -> Author:           @{result.comment.author.unique_id} ({result.comment.author.nickname})")
    print(f"   -> Comment Text:     {result.comment.text}")
    print(f"   -> Sticker ID:       {result.comment.sticker.sticker_id}")
    print(f"   -> Is Animated:      {result.comment.sticker.is_animated}")
    print(f"   -> Static URL:       {result.comment.sticker.static_url}")
    print(f"   -> Animated URL:     {result.comment.sticker.animated_url}")

    print("\n3. Validating Media Binary...")
    parser = WebPBinaryParser()
    meta = parser.parse(result.media_bytes)
    print(f"   -> Valid WebP:       {meta.is_valid_webp}")
    print(f"   -> Animation:        {meta.is_animated}")
    print(f"   -> Dimensions:       {meta.width} x {meta.height}")
    print(f"   -> File Size:        {meta.file_size} bytes ({meta.file_size/1024:.2f} KB)")
    print(f"   -> Frame Count:      {meta.frame_count}")
    print(f"   -> Duration:         {meta.duration_ms} ms")
    print(f"   -> SHA-256 Hash:     {meta.sha256}")
    print(f"   -> WhatsApp Compliant: {meta.whatsapp_compliant}")
    if meta.compliance_issues:
        print(f"   -> Compliance Notes: {meta.compliance_issues}")

    print("\n4. Persisting to SQLite Database...")
    db = DatabaseManager("data/stickerdrop.db")
    repo = StickerRepository(db, "data/media")
    record, created = repo.save_sticker(
        source_video_id=result.video_id,
        source_comment_id=result.target_comment_id,
        source_author=result.comment.author.unique_id,
        original_media_url=result.comment.sticker.best_url,
        media_bytes=result.media_bytes,
        is_animated=meta.is_animated,
        width=meta.width,
        height=meta.height,
        frame_count=meta.frame_count,
        duration_ms=meta.duration_ms,
        sticker_id=result.comment.sticker.sticker_id
    )
    print(f"   -> Saved record ID:  {record.id}")
    print(f"   -> Internal UUID:    {record.internal_id}")
    print(f"   -> Local Path:       {record.local_media_path}")
    print(f"   -> New entry:        {created}")

    print("\n" + "=" * 70)
    print("LIVE EXTRACTION TEST COMPLETE: SUCCESS")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(run_live_test())
