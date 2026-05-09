"""Real image generation fallback."""
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ImageGenerator:
    def __init__(self, api_url: str = "https://image.pollinations.ai/prompt/"):
        self.api_url = api_url
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))

    async def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> Optional[str]:
        encoded = prompt.replace(" ", "%20").replace(",", "%2C").replace("?", "%3F")
        url = f"{self.api_url}{encoded}?width={width}&height={height}&nologo=true&seed={hash(prompt) % 10000}"
        try:
            async with self.session.get(url, allow_redirects=True) as resp:
                if resp.status == 200:
                    return str(resp.url)
                return None
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None

    async def close(self):
        await self.session.close()
