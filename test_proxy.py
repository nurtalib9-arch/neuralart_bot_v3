"""Test if proxy works with Telethon."""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = 33664677  # ЗАМЕНИ!
API_HASH = "f83861ab402a4a037d9565ed8c999bc7"  # ЗАМЕНИ!

async def test():
    # Прокси из твоего файла
    proxy = ("socks5", "bproxy.site", 18081, True, "UVBun2", "syuEdNYdeR7A")
    
    print("[+] Testing proxy connection...")
    client = TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
        proxy=proxy,
    )
    
    try:
        await client.connect()
        print("[+] Connected through proxy!")
        print(f"[+] Proxy IP check: {await client.get_me()}")
        await client.disconnect()
    except Exception as e:
        print(f"[!] Proxy failed: {e}")

asyncio.run(test())