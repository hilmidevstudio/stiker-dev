"""
WhatsApp Sticker Pack Directory Validator.
Verifies compliance with WhatsApp Android ContentProvider rules.
"""

from typing import List, Dict, Any
import os
import json

from ..media.validator import WebPBinaryParser


class WhatsAppPackValidator:
    """
    Validates a generated pack directory against WhatsApp specifications.
    """

    def __init__(self):
        self.parser = WebPBinaryParser()

    def validate_pack(self, pack_dir_path: str) -> Dict[str, Any]:
        """
        Validates pack folder contents, contents.json, tray icon, and sticker images.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not os.path.isdir(pack_dir_path):
            return {"valid": False, "errors": [f"Pack directory not found: {pack_dir_path}"]}

        # 1. Validate contents.json
        manifest_path = os.path.join(pack_dir_path, "contents.json")
        if not os.path.isfile(manifest_path):
            errors.append("Missing contents.json manifest.")
            return {"valid": False, "errors": errors}

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            errors.append(f"contents.json is invalid JSON: {str(e)}")
            return {"valid": False, "errors": errors}

        packs = manifest_data.get("sticker_packs", [])
        if not packs or len(packs) == 0:
            errors.append("contents.json does not contain any sticker_packs.")
            return {"valid": False, "errors": errors}

        pack = packs[0]
        identifier = pack.get("identifier")
        is_animated_pack = bool(pack.get("animated_sticker_pack", False))
        stickers = pack.get("stickers", [])

        # 2. Check sticker count limits (3 to 30)
        sticker_count = len(stickers)
        if sticker_count < 3:
            errors.append(f"Pack contains {sticker_count} stickers; WhatsApp requires at least 3.")
        elif sticker_count > 30:
            errors.append(f"Pack contains {sticker_count} stickers; WhatsApp allows at most 30.")

        # 3. Check tray icon
        tray_filename = pack.get("tray_image_file")
        if not tray_filename:
            errors.append("tray_image_file is not specified.")
        else:
            tray_path = os.path.join(pack_dir_path, tray_filename)
            if not os.path.isfile(tray_path):
                errors.append(f"Tray icon file '{tray_filename}' does not exist on disk.")
            else:
                tray_size = os.path.getsize(tray_path)
                if tray_size > 50 * 1024:
                    errors.append(f"Tray icon size ({tray_size} bytes) exceeds WhatsApp 50 KB limit.")

        # 4. Check each sticker file
        for idx, s in enumerate(stickers):
            s_file = s.get("image_file")
            if not s_file:
                errors.append(f"Sticker index {idx} has no image_file.")
                continue

            s_path = os.path.join(pack_dir_path, s_file)
            if not os.path.isfile(s_path):
                errors.append(f"Sticker file '{s_file}' does not exist.")
                continue

            with open(s_path, "rb") as f:
                raw_bytes = f.read()

            meta = self.parser.parse(raw_bytes)
            if not meta.is_valid_webp:
                errors.append(f"Sticker '{s_file}' is not a valid WebP file.")
            else:
                if is_animated_pack and not meta.is_animated:
                    errors.append(f"Static sticker '{s_file}' found in animated pack (mixing prohibited).")
                elif not is_animated_pack and meta.is_animated:
                    errors.append(f"Animated sticker '{s_file}' found in static pack (mixing prohibited).")

                if meta.compliance_issues:
                    for issue in meta.compliance_issues:
                        errors.append(f"Sticker '{s_file}': {issue}")

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "identifier": identifier,
            "sticker_count": sticker_count,
            "is_animated_pack": is_animated_pack,
            "errors": errors,
            "warnings": warnings
        }
