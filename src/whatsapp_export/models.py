"""
Data models and JSON schemas for WhatsApp Sticker Pack generation.
Complies with official WhatsApp Android Stickers API specification.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class WhatsAppStickerItem:
    image_file: str
    emojis: List[str] = field(default_factory=lambda: ["🔥"])


@dataclass
class WhatsAppPackMetadata:
    identifier: str
    name: str
    publisher: str
    tray_image_file: str
    animated_sticker_pack: bool
    stickers: List[WhatsAppStickerItem]
    publisher_email: str = "support@stickerdrop.app"
    publisher_website: str = "https://stickerdrop.app"
    privacy_policy_website: str = "https://stickerdrop.app/privacy"
    license_agreement_website: str = "https://stickerdrop.app/terms"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "name": self.name,
            "publisher": self.publisher,
            "tray_image_file": self.tray_image_file,
            "publisher_email": self.publisher_email,
            "publisher_website": self.publisher_website,
            "privacy_policy_website": self.privacy_policy_website,
            "license_agreement_website": self.license_agreement_website,
            "animated_sticker_pack": self.animated_sticker_pack,
            "stickers": [
                {
                    "image_file": s.image_file,
                    "emojis": s.emojis
                }
                for s in self.stickers
            ]
        }


@dataclass
class WhatsAppContentsManifest:
    android_play_store_link: str = "https://play.google.com/store/apps/details?id=com.stickerdrop.app"
    ios_app_store_link: str = ""
    sticker_packs: List[WhatsAppPackMetadata] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "android_play_store_link": self.android_play_store_link,
            "ios_app_store_link": self.ios_app_store_link,
            "sticker_packs": [p.to_dict() for p in self.sticker_packs]
        }
