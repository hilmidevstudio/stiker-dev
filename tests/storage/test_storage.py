"""
Unit and Integration Tests for Persistent Storage Repository.
"""

import unittest
import os
import shutil
import tempfile
from src.storage.db import DatabaseManager
from src.storage.repository import StickerRepository, StickerRecord
from src.media.processor import MediaProcessor


class TestStickerRepository(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_stickerdrop.db")
        self.media_dir = os.path.join(self.temp_dir, "media")

        self.db_manager = DatabaseManager(self.db_path)
        self.repo = StickerRepository(self.db_manager, self.media_dir)
        self.processor = MediaProcessor()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_retrieve_sticker(self):
        sample_bytes = self.processor.create_synthetic_animated_webp(512, 512, frame_count=4)

        record, was_created = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="7708394712596972308",
            source_author="@crazyolshop1",
            original_media_url="https://p16-sign-va.tiktokcdn.com/sticker.awebp",
            media_bytes=sample_bytes,
            is_animated=True,
            width=512,
            height=512,
            frame_count=4,
            duration_ms=1000,
            sticker_id="7421890123456789012"
        )

        self.assertTrue(was_created)
        self.assertEqual(record.source_comment_id, "7708394712596972308")
        self.assertTrue(record.is_animated)
        self.assertTrue(os.path.exists(record.local_media_path))

        # Retrieve by comment ID
        fetched = self.repo.get_by_comment_id("7708394712596972308")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.internal_id, record.internal_id)

    def test_persistence_across_connection_restarts(self):
        sample_bytes = self.processor.create_synthetic_static_webp(512, 512)
        record, _ = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="1111111111111111111",
            source_author="@user1",
            original_media_url="https://p16-sign-va.tiktokcdn.com/static.webp",
            media_bytes=sample_bytes,
            is_animated=False,
            width=512,
            height=512
        )

        # Re-initialize DB manager and Repository pointing to the same file
        new_db_manager = DatabaseManager(self.db_path)
        new_repo = StickerRepository(new_db_manager, self.media_dir)

        fetched = new_repo.get_by_comment_id("1111111111111111111")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.internal_id, record.internal_id)
        self.assertEqual(new_repo.count(), 1)

    def test_comment_deduplication(self):
        sample_bytes = self.processor.create_synthetic_static_webp(512, 512)
        rec1, created1 = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="2222222222222222222",
            source_author="@user2",
            original_media_url="https://p16-sign-va.tiktokcdn.com/test.webp",
            media_bytes=sample_bytes,
            is_animated=False,
            width=512,
            height=512
        )
        self.assertTrue(created1)

        # Attempt to save the exact same comment again
        rec2, created2 = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="2222222222222222222",
            source_author="@user2",
            original_media_url="https://p16-sign-va.tiktokcdn.com/test.webp",
            media_bytes=sample_bytes,
            is_animated=False,
            width=512,
            height=512
        )
        self.assertFalse(created2)
        self.assertEqual(rec1.internal_id, rec2.internal_id)
        self.assertEqual(self.repo.count(), 1)

    def test_media_hash_deduplication(self):
        # Different comment, but exact same media bytes
        sample_bytes = self.processor.create_synthetic_static_webp(512, 512)
        rec1, created1 = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="3333333333333333333",
            source_author="@user3",
            original_media_url="https://p16-sign-va.tiktokcdn.com/test.webp",
            media_bytes=sample_bytes,
            is_animated=False,
            width=512,
            height=512
        )
        self.assertTrue(created1)

        rec2, created2 = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="4444444444444444444",  # Different comment ID
            source_author="@user4",
            original_media_url="https://p16-sign-va.tiktokcdn.com/test.webp",
            media_bytes=sample_bytes,                  # Identical bytes
            is_animated=False,
            width=512,
            height=512
        )
        self.assertFalse(created2)
        self.assertEqual(rec1.internal_id, rec2.internal_id)

    def test_library_integrity_verification(self):
        sample_bytes = self.processor.create_synthetic_static_webp(512, 512)
        record, _ = self.repo.save_sticker(
            source_video_id="7708356144804236564",
            source_comment_id="5555555555555555555",
            source_author="@user5",
            original_media_url="https://p16-sign-va.tiktokcdn.com/test.webp",
            media_bytes=sample_bytes,
            is_animated=False,
            width=512,
            height=512
        )

        # Baseline: library is healthy
        report = self.repo.verify_library_integrity()
        self.assertTrue(report.is_healthy)
        self.assertEqual(report.valid_records, 1)

        # Intentionally delete the file to simulate missing asset
        os.remove(record.local_media_path)
        bad_report = self.repo.verify_library_integrity()
        self.assertFalse(bad_report.is_healthy)
        self.assertIn(record.internal_id, bad_report.missing_files)


if __name__ == "__main__":
    unittest.main()
