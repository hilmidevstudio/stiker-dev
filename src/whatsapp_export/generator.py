"""
WhatsApp Sticker Pack Generator and Virtual Pack Partitioner for StickerDrop.
"""

from typing import List, Dict, Any, Tuple
import os
import shutil
import json
import zlib
import struct

from ..storage.repository import StickerRecord
from ..media.processor import MediaProcessor
from .models import (
    WhatsAppStickerItem,
    WhatsAppPackMetadata,
    WhatsAppContentsManifest,
)


class WhatsAppPackGenerator:
    """
    Partitions persistent sticker collections into WhatsApp-compliant packs.
    """

    MIN_PACK_STICKERS = 3
    MAX_PACK_STICKERS = 30
    TRAY_IMAGE_NAME = "tray_icon.png"

    def __init__(self, output_root_dir: str = "samples/output/packs"):
        self.output_root = os.path.abspath(output_root_dir)
        os.makedirs(self.output_root, exist_ok=True)

    @staticmethod
    def generate_synthetic_tray_icon_png(width: int = 96, height: int = 96) -> bytes:
        """
        Generates a valid 96x96 transparent PNG image for WhatsApp tray icon.
        Pure Python implementation using zlib and struct (zero Pillow dependency).
        """
        # PNG signature
        png_sig = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk: 96x96, 8-bit depth, RGBA (color type 6)
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
        ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # Raw scanlines: for each row, 1 byte filter (0 = None), then width * 4 bytes RGBA
        # Semi-transparent blue sticker icon
        raw_rows = bytearray()
        for y in range(height):
            raw_rows.append(0)  # Filter byte: None
            for x in range(width):
                # Draw rounded border or blue box
                if 8 <= x < 88 and 8 <= y < 88:
                    raw_rows.extend([30, 144, 255, 220])  # DodgerBlue with alpha
                else:
                    raw_rows.extend([0, 0, 0, 0])        # Transparent

        compressed_data = zlib.compress(bytes(raw_rows), level=9)
        idat_crc = zlib.crc32(b"IDAT" + compressed_data)
        idat_chunk = struct.pack(">I", len(compressed_data)) + b"IDAT" + compressed_data + struct.pack(">I", idat_crc)

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND")
        iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return png_sig + ihdr_chunk + idat_chunk + iend_chunk

    def partition_collection(
        self,
        records: List[StickerRecord]
    ) -> Tuple[List[List[StickerRecord]], List[StickerRecord]]:
        """
        Splits collection into streams (animated vs static) and chunks into 30-item blocks.
        Returns: (ready_packs, incomplete_tail_stickers).
        """
        animated = [r for r in records if r.is_animated]
        static = [r for r in records if not r.is_animated]

        ready_packs: List[List[StickerRecord]] = []
        incomplete: List[StickerRecord] = []

        for stream in [animated, static]:
            for i in range(0, len(stream), self.MAX_PACK_STICKERS):
                chunk = stream[i:i + self.MAX_PACK_STICKERS]
                if len(chunk) >= self.MIN_PACK_STICKERS:
                    ready_packs.append(chunk)
                else:
                    incomplete.extend(chunk)

        return ready_packs, incomplete

    def generate_pack_directory(
        self,
        pack_stickers: List[StickerRecord],
        pack_index: int = 1,
        publisher_name: str = "StickerDrop"
    ) -> str:
        """
        Builds a physical pack export folder with contents.json, tray_icon.png, and stickers.
        """
        if len(pack_stickers) < self.MIN_PACK_STICKERS or len(pack_stickers) > self.MAX_PACK_STICKERS:
            raise ValueError(
                f"WhatsApp pack requires 3 to 30 stickers. Provided count: {len(pack_stickers)}"
            )

        is_animated = pack_stickers[0].is_animated
        pack_type_str = "anim" if is_animated else "static"
        pack_id = f"stickerdrop_pack_{pack_type_str}_{pack_index:03d}"
        pack_name = f"StickerDrop {'Animated ' if is_animated else ''}{pack_index}"

        pack_dir = os.path.join(self.output_root, pack_id)
        os.makedirs(pack_dir, exist_ok=True)

        # Step 1: Write Tray Icon
        tray_path = os.path.join(pack_dir, self.TRAY_IMAGE_NAME)
        tray_bytes = self.generate_synthetic_tray_icon_png(96, 96)
        with open(tray_path, "wb") as f:
            f.write(tray_bytes)

        # Step 2: Copy and rename stickers into pack directory
        sticker_items: List[WhatsAppStickerItem] = []
        for idx, sticker in enumerate(pack_stickers):
            ext = ".webp"
            sticker_filename = f"sticker_{idx+1:02d}_{sticker.source_comment_id[:10]}{ext}"
            dest_sticker_path = os.path.join(pack_dir, sticker_filename)

            if os.path.exists(sticker.local_media_path):
                shutil.copy2(sticker.local_media_path, dest_sticker_path)
            else:
                # If source file does not exist, synthesize valid WebP for testing
                dummy_webp = MediaProcessor.create_synthetic_animated_webp(512, 512) if is_animated else MediaProcessor.create_synthetic_static_webp(512, 512)
                with open(dest_sticker_path, "wb") as f:
                    f.write(dummy_webp)

            sticker_items.append(
                WhatsAppStickerItem(
                    image_file=sticker_filename,
                    emojis=["🔥", "🗿"] if is_animated else ["👍"]
                )
            )

        # Step 3: Write contents.json manifest
        pack_meta = WhatsAppPackMetadata(
            identifier=pack_id,
            name=pack_name,
            publisher=publisher_name,
            tray_image_file=self.TRAY_IMAGE_NAME,
            animated_sticker_pack=is_animated,
            stickers=sticker_items
        )

        manifest = WhatsAppContentsManifest(
            sticker_packs=[pack_meta]
        )

        manifest_path = os.path.join(pack_dir, "contents.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return pack_dir
