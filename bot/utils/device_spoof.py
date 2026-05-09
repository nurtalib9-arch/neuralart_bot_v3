"""Generate realistic device fingerprints."""
import random
from typing import Dict

class DeviceSpoofer:
    DEVICE_MODELS = [
        ("iPhone14,2", "iOS 16.5", "Telegram iOS 10.1.1"),
        ("iPhone13,4", "iOS 16.3", "Telegram iOS 9.7.2"),
        ("SM-G991B", "Android 13", "Telegram Android 9.7.1"),
        ("SM-G998B", "Android 12", "Telegram Android 9.6.5"),
        ("Pixel 7", "Android 13", "Telegram Android 9.7.0"),
        ("Mi 11", "Android 12", "Telegram Android 9.5.3"),
        ("ONEPLUS A6010", "Android 11", "Telegram Android 9.4.2"),
        ("iPhone11,8", "iOS 15.4", "Telegram iOS 8.9.1"),
        ("SM-A525F", "Android 11", "Telegram Android 9.3.0"),
        ("iPhone14,5", "iOS 16.6", "Telegram iOS 10.2.0"),
        ("SM-S901B", "Android 13", "Telegram Android 9.7.2"),
        ("Pixel 6 Pro", "Android 13", "Telegram Android 9.6.8"),
    ]
    LANG_CODES = ["en", "ru", "es", "de", "fr", "it", "pt", "ar", "tr", "pl", "uk", "ja"]

    @classmethod
    def get_mobile_fingerprint(cls) -> Dict[str, str]:
        model, system, app = random.choice(cls.DEVICE_MODELS)
        return {
            "device_model": model,
            "system_version": system,
            "app_version": app,
            "lang_code": random.choice(cls.LANG_CODES),
            "system_lang_code": random.choice(cls.LANG_CODES),
        }
