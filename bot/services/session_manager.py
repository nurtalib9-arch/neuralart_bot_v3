"""Enhanced Telethon session manager with anti-detection."""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError,
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    PasswordHashInvalidError, PhoneNumberInvalidError,
    PhoneNumberBannedError, PhoneNumberFloodError
)

from bot.utils.device_spoof import DeviceSpoofer
from bot.services.proxy_rotator import ProxyRotator, Proxy

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, api_id: int, api_hash: str, proxy_rotator: ProxyRotator):
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy_rotator = proxy_rotator

    def _create_client(self, session_string: str = "", proxy: Optional[Proxy] = None,
                       device_info: Optional[Dict] = None) -> TelegramClient:
        """Create Telethon client with consistent device info and proxy."""
        proxy_tuple = proxy.to_telethon_tuple() if proxy else None

        if device_info is None:
            device_info = DeviceSpoofer.get_mobile_fingerprint()

        print(f"[+] Creating Telethon client:")
        print(f"    Device: {device_info['device_model']} | {device_info['system_version']}")
        print(f"    App: {device_info['app_version']}")
        print(f"    Lang: {device_info['lang_code']}")
        print(f"    Proxy: {proxy if proxy else 'DIRECT (NO PROXY!)'}")

        if not proxy:
            print("[!] WARNING: No proxy! Real IP will be exposed to Telegram!")

        client = TelegramClient(
            StringSession(session_string),
            self.api_id,
            self.api_hash,
            proxy=proxy_tuple,
            device_model=device_info["device_model"],
            system_version=device_info["system_version"],
            app_version=device_info["app_version"],
            lang_code=device_info["lang_code"],
            system_lang_code=device_info["system_lang_code"],
            connection_retries=3,
            retry_delay=5,
            timeout=30,
        )
        return client

    async def create_auth_client(self, device_type: str = "mobile") -> Tuple[TelegramClient, Optional[Proxy], Dict]:
        """Create a new client for initial auth."""
        proxy = self.proxy_rotator.get_proxy()
        device_info = DeviceSpoofer.get_mobile_fingerprint() if device_type == "mobile" else DeviceSpoofer.get_mobile_fingerprint()
        client = self._create_client("", proxy, device_info)
        await client.connect()
        return client, proxy, device_info

    async def send_code(self, phone: str, device_type: str = "mobile") -> Dict:
        """Send verification code with full error handling."""
        client, proxy, device_info = await self.create_auth_client(device_type)

        try:
            sent_code = await client.send_code_request(phone)
            session_str = client.session.save()

            return {
                "success": True,
                "session_string": session_str,
                "phone_code_hash": sent_code.phone_code_hash,
                "device_info": device_info,
                "proxy": proxy,
                "client": client,
            }

        except FloodWaitError as e:
            await client.disconnect()
            if proxy:
                self.proxy_rotator.mark_banned(proxy)
            return {"success": False, "error": "flood", "seconds": e.seconds}
        except PhoneNumberInvalidError:
            await client.disconnect()
            return {"success": False, "error": "invalid_phone"}
        except PhoneNumberBannedError:
            await client.disconnect()
            return {"success": False, "error": "banned"}
        except PhoneNumberFloodError:
            await client.disconnect()
            return {"success": False, "error": "phone_flood"}
        except Exception as e:
            await client.disconnect()
            logger.error(f"Send code error: {e}")
            return {"success": False, "error": "unknown", "message": str(e)}

    async def verify_code(self, session_string: str, phone: str, code: str, 
                          phone_code_hash: str, proxy: Optional[Proxy] = None,
                          device_info: Optional[Dict] = None) -> Dict:
        """Verify code — NOW with device info and proxy!"""
        client = self._create_client(session_string, proxy, device_info)

        try:
            await client.connect()
            user = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            new_session = client.session.save()
            await client.disconnect()

            return {
                "success": True,
                "session_string": new_session,
                "user_id": user.id,
                "username": user.username,
                "phone": user.phone,
            }

        except SessionPasswordNeededError:
            new_session = client.session.save()
            await client.disconnect()
            return {"success": False, "error": "2fa_required", "session_string": new_session}
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {"success": False, "error": "invalid_code"}
        except PhoneCodeExpiredError:
            await client.disconnect()
            return {"success": False, "error": "expired"}
        except Exception as e:
            await client.disconnect()
            logger.error(f"Verify code error: {e}")
            return {"success": False, "error": "unknown", "message": str(e)}

    async def verify_2fa(self, session_string: str, password: str, 
                         proxy: Optional[Proxy] = None,
                         device_info: Optional[Dict] = None) -> Dict:
        """Complete 2FA — NOW with device info and proxy!"""
        client = self._create_client(session_string, proxy, device_info)

        try:
            await client.connect()
            user = await client.sign_in(password=password)
            new_session = client.session.save()
            await client.disconnect()

            return {
                "success": True,
                "session_string": new_session,
                "user_id": user.id,
                "username": user.username,
                "phone": user.phone,
            }

        except PasswordHashInvalidError:
            await client.disconnect()
            return {"success": False, "error": "invalid_password"}
        except Exception as e:
            await client.disconnect()
            logger.error(f"2FA error: {e}")
            return {"success": False, "error": "unknown", "message": str(e)}

    async def validate_session(self, session_string: str) -> bool:
        """Check if session is still valid."""
        client = self._create_client(session_string)
        try:
            await client.connect()
            is_authorized = await client.is_user_authorized()
            await client.disconnect()
            return is_authorized
        except Exception:
            return False
