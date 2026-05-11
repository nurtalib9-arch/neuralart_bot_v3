"""Generate realistic device fingerprints."""
import random
from typing import Dict


# class DeviceSpoofer:
    # DEVICE_MODELS = [
    #     ("SM-G991B", "Android 13", "Telegram Android 9.7.1")
    # ]
    # LANG_CODES = ["en", "ru"]

    # @classmethod
    # def get_mobile_fingerprint(cls) -> Dict[str, str]:
    #     model, system, app = random.choice(cls.DEVICE_MODELS)
    #     return {
    #         "device_model": model,
    #         "system_version": system,
    #         "app_version": app,
    #         "lang_code": random.choice(cls.LANG_CODES),
    #         "system_lang_code": random.choice(cls.LANG_CODES),
    #     }

class DeviceSpoofer:
    @classmethod
    def get_mobile_fingerprint(cls) -> Dict[str, str]:
        return {
            "device_model": "SM-G991B",
            "system_version": "Android 13",
            "app_version": "Telegram Android 9.7.1",
            "lang_code": "ru",
            "system_lang_code": "ru",
        }