"""Centralized configuration."""
import os
from dataclasses import dataclass
from typing import List
from pathlib import Path

# Load .env from multiple locations
for env_path in [Path(".env"), Path(__file__).parent.parent / ".env", Path(os.getcwd()) / ".env"]:
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        print(f"[+] Loaded .env from: {env_path.absolute()}")
        break

@dataclass(frozen=True)
class BotConfig:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    TELEGRAM_API_ID: int = int(os.getenv("API_ID", "0") or "0")
    TELEGRAM_API_HASH: str = os.getenv("API_HASH", "")
    IMAGE_API_URL: str = "https://image.pollinations.ai/prompt/"
    DB_PATH: str = "data/sessions.db"
    PROXY_FILE: str = "data/proxies.txt"
    ADMIN_IDS: List[int] = None
    MAX_SESSIONS_PER_PROXY: int = 3
    FREE_GENERATIONS: int = 2
    REFERRAL_BONUS: int = 5

    def __post_init__(self):
        if self.ADMIN_IDS is None:
            ids_str = os.getenv("ADMIN_IDS", "")
            object.__setattr__(self, 'ADMIN_IDS', [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()])

config = BotConfig()
print(f"[+] BOT_TOKEN: {'YES' if config.BOT_TOKEN else 'NO'}")
print(f"[+] API_ID: {config.TELEGRAM_API_ID}")
print(f"[+] API_HASH: {'YES' if config.TELEGRAM_API_HASH else 'NO'}")
