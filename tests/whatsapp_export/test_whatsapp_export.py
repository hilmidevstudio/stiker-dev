"""
Unit and Integration Tests for WhatsApp Sticker Pack Generator and Validator.
"""

import unittest
import os
import shutil
import tempfile
from src.storage.repository import StickerRecord
from src.whatsapp_export.generator import WhatsAppPackGenerator
from src.whatsapp_export.validator import WhatsAppPackValidator
from src.media.processor import MediaProcessor


class TestWhatsAppExport(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.packs_dir = os.path.join(self.temp_dir, "packs")
        self.media_dir = os.path.join(self.temp_dir, "media")
        os.makedirs(self.media_dir, exist_ok=True)

        self.generator = WhatsAppPackGenerator(self.packs_dir)
        self.validator = WhatsAppPackValidator()
        self.processor = MediaProcessor()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_sticker_record(
        self,
        comment_id: str,
        is_animated: bool = True
    ) -> StickerRecord:
        raw_bytes = (
            self.processor.create_synthetic_animated_webp(512, 512)
            if is_animated else
            self.processor.create_synthetic_static_webp(512, 512)
        )
        file_path = os.path.join(self.media_dir, f"{comment_id}.webp")
        with open(file_path, "wb") as f:
            f.write(raw_bytes)

        return StickerRecord(
            id=1,
            internal_id=f"uuid-{comment_id}",
            source_platform="tiktok",
            source_video_id="7708356144804236564",
            source_comment_id=comment_id,
            source_author="@tester",
            sticker_id=f"stk-{comment_id}",
            original_media_url="https://cdn.example.com/sticker.webp",
            local_media_path=file_path,
            media_type="image/awebp" if is_animated else "image/webp",
            is_animated=is_animated,
            width=512,
            height=512,
            file_size=len(raw_bytes),
            frame_count=4 if is_animated else 1,
            duration_ms=1000 if is_animated else 0,
            sha256="dummy_sha256",
            export_status="PENDING",
            created_at="2026-11-17T00:00:00Z",
            updated_at="2026-11-17T00:00:00Z"
        )

    def test_partitioning_logic(self):
        # Create 35 animated stickers and 2 static stickers
        animated_records = [self._create_mock_sticker_record(f"anim_{i}", is_animated=True) for i in range(35)]
        static_records = [self._create_mock_sticker_record(f"static_{i}", is_animated=False) for i in range(2)]

        all_records = animated_records + static_records
        ready_packs, incomplete = self.generator.partition_collection(all_records)

        # 35 animated should split into: Pack 1 (30), Pack 2 (5) -> both >= 3
        # 2 static should be incomplete (needs 3)
        self.assertEqual(len(ready_packs), 2)
        self.assertEqual(len(ready_packs[0]), 30)
        self.assertEqual(len(ready_packs[1]), 5)
        self.assertEqual(len(incomplete), 2)

    def test_pack_generation_and_validation(self):
        # Create 3 valid animated stickers (minimum WhatsApp pack size)
        stickers = [
            self._create_mock_sticker_record("7708394712596972308", is_animated=True),
            self._create_mock_sticker_record("7708394712596972309", is_animated=True),
            self._create_mock_sticker_record("7708394712596972310", is_animated=True),
        ]

        pack_dir = self.generator.generate_pack_directory(stickers, pack_index=1)
        self.assertTrue(os.path.isdir(pack_dir))
        self.assertTrue(os.path.isfile(os.path.join(pack_dir, "contents.json")))
        self.assertTrue(os.path.isfile(os.path.join(pack_dir, "tray_icon.png")))

        # Validate with official WhatsApp rules
        val_result = self.validator.validate_pack(pack_dir)
        self.assertTrue(val_result["valid"], msg=f"Validation errors: {val_result.get('errors')}")
        self.assertEqual(val_result["sticker_count"], 3)
        self.assertTrue(val_result["is_animated_pack"])

    def test_mixed_animated_and_static_pack_rejected(self):
        # Intentionally create a mixed pack (WhatsApp violation)
        stickers = [
            self._create_mock_sticker_record("1", is_animated=True),
            self._create_mock_sticker_record("2", is_animated=False),  # Static mixed in!
            self._create_mock_sticker_record("3", is_animated=True),
        ]

        # Generator will build folder, but validator must reject it
        pack_dir = self.generator.generate_pack_directory(stickers, pack_index=2)
        val_result = self.validator.validate_pack(pack_dir)
        self.assertFalse(val_result["valid"])
        self.assertTrue(any("mixing prohibited" in e for e in val_result["errors"]))


if __name__ == "__main__":
    unittest.main()
