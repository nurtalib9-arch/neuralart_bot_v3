"""Psychologist handlers."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.states import PsychologistStates
from bot.database import Database
from bot.keyboards import back_to_menu_kb

import logging
logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data == "psychologist")
async def start_psychologist(callback: CallbackQuery, state: FSMContext, db: Database, psych_api):
    user_id = callback.from_user.id
    
    await state.set_state(PsychologistStates.in_session)
    
    # Можно раскомментировать, если хочешь каждый раз начинать с чистого листа
    # db.clear_psych_history(user_id)
    
    history = db.get_psych_history(user_id, limit=10)
    
    if history:
        greeting = (
            "🧠 <b>Продолжаем нашу беседу</b>\n\n"
            "Я помню, о чём мы говорили раньше.\n"
            "Чем могу помочь сегодня?"
        )
    else:
        greeting = (
            "🧠 <b>Сессия с психологом начата</b>\n\n"
            "Я — опытный психолог-консультант с 20-летним стажем.\n\n"
            "Здесь ты можешь говорить открыто о том, что тебя беспокоит.\n"
            "Я буду слушать, задавать вопросы и предлагать практики.\n\n"
            "Расскажи, пожалуйста, что происходит?"
        )
    
    await callback.message.answer(greeting, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(PsychologistStates.in_session)
async def handle_psych_message(message: Message, state: FSMContext, db: Database, psych_api):
    user_id = message.from_user.id
    user_text = (message.text or "").strip()
    
    if not user_text:
        await message.answer("Пожалуйста, напиши текст сообщения.")
        return
    
    # Сохраняем сообщение пользователя
    db.save_psych_message(user_id, user_text, "user")
    
    # Берём историю (последние 20 сообщений)
    history = db.get_psych_history(user_id, limit=20)
    
    try:
        response = await psych_api.chat(history)
        
        # Сохраняем ответ психолога
        db.save_psych_message(user_id, response, "assistant")
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Psychologist API error: {e}")
        await message.answer(
            "Извини, произошла техническая ошибка на стороне API.\n"
            "Попробуй написать ещё раз через 30–60 секунд.\n\n"
            "Или нажми «В главное меню», чтобы выйти из сессии."
        )


# Дополнительно: если пользователь напишет /menu или /start — выходим из состояния
@router.message(F.text.in_({"/menu", "/start", "/главное меню"}), PsychologistStates.in_session)
async def exit_psych_from_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Сессия с психологом завершена. Возвращаюсь в главное меню...")