import os
import sys
import logging
import signal
from datetime import date, timedelta
from typing import Dict, List, Optional
import psutil
import time
import threading
import pendulum
from datetime import datetime

# Временный обход для импорта keyboards и db
sys.path.append(os.path.dirname(__file__))

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError

import db
import keyboards

TIMEZONE = "Asia/Almaty"

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('aiogram').setLevel(logging.DEBUG)
logging.getLogger('fastapi').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

load_dotenv()

# --- Конфигурация ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://your-frontend-render-url")
RENDER_URL = os.getenv("RENDER_URL", "").rstrip('/')
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# --- Инициализация ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели Pydantic для API ---
class HistoryDayStats(BaseModel):
    date: str
    screen_time_goal: int
    screen_time_actual: int
    productive_time_actual: int
    workout_done: int
    english_done: int
    coding_done: int
    planning_done: int
    stretching_done: int
    reflection_done: int
    is_rest_day: bool

class TodayStats(BaseModel):
    screen_time_goal: Optional[int] = 0
    screen_time_actual: int = 0
    screen_time_breakdown: Dict[str, int] = {}
    productive_time_actual: int = 0
    productive_time_breakdown: Dict[str, int] = {}
    workout_planned: int
    workout_done: int
    english_planned: int
    english_done: int
    coding_planned: int
    coding_done: int
    planning_planned: int
    planning_done: int
    stretching_planned: int
    stretching_done: int
    reflection_planned: int
    reflection_done: int
    morning_poll_completed: bool
    is_rest_day: bool

class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]

# --- FSM для логирования активности ---
class LogActivity(StatesGroup):
    choosing_type = State()
    choosing_activity_name = State()
    choosing_duration = State()

# --- FSM для утреннего опроса ---
class MorningPoll(StatesGroup):
    choosing_day_type = State()

# --- FSM для записи спортивных достижений ---
class SportAchievement(StatesGroup):
    choosing_date = State()
    choosing_description = State()

# --- Глобальное хранилище планов ---
user_plans: Dict[int, Dict[str, Optional[int]]] = {}

# --- Логирование ошибок завершения ---
def log_uncaught_exceptions(exctype, value, tb):
    logger.error("Uncaught exception", exc_info=(exctype, value, tb))

sys.excepthook = log_uncaught_exceptions

# --- Обработчик сигналов для graceful shutdown ---
def handle_shutdown(signum, frame):
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    logger.info("Skipping webhook deletion to maintain 24/7 operation")

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# --- Обработчики Telegram ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    logger.info(f"Received /start from user_id: {message.from_user.id}")
    try:
        db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        await message.answer(
            "⚔️ Добро пожаловать, командир!\n\n"
            "Используй /menu, чтобы отдать приказ.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Error in /start for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    logger.info(f"Received /settings from user_id: {message.from_user.id}")
    try:
        await message.answer("Меню настроек:", reply_markup=keyboards.get_settings_keyboard("Asia/Almaty"))
    except Exception as e:
        logger.error(f"Error in /settings for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    logger.info(f"Received /menu from user_id: {message.from_user.id}")
    try:
        await state.clear()
        await message.answer("Выберите действие:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
    except Exception as e:
        logger.error(f"Error in /menu for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("achievements"))
async def cmd_achievements(message: Message):
    logger.info(f"Received /achievements from user_id: {message.from_user.id}")
    try:
        await message.answer("Что вы хотите сделать с достижениями?", reply_markup=keyboards.get_achievements_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in /achievements for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "menu_achievements")
async def cq_achievements_menu(callback: CallbackQuery):
    logger.info(f"Received callback menu_achievements from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Что вы хотите сделать с достижениями?", reply_markup=keyboards.get_achievements_menu_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_achievements for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "achievements_view")
async def cq_view_achievements(callback: CallbackQuery):
    logger.info(f"Received callback achievements_view from user_id: {callback.from_user.id}")
    try:
        with db.get_db() as db_session:
            stmt = text("SELECT achievement_name, date_earned FROM sport_achievements WHERE user_id = :uid ORDER BY date_earned DESC")
            achievements = db_session.execute(stmt, {'uid': callback.from_user.id}).fetchall()
            if not achievements:
                await callback.message.edit_text(
                    "🏆 У вас пока нет спортивных достижений. Добавьте первое!",
                    reply_markup=keyboards.get_achievements_menu_keyboard()
                )
                await callback.answer()
                return
            achievement_lines = ["🏆 Ваши спортивные достижения:\n"]
            for ach in achievements:
                achievement_lines.append(f"• {ach.achievement_name} ({ach.date_earned.strftime('%d.%m.%Y')})")
            await callback.message.edit_text(
                "\n".join(achievement_lines),
                reply_markup=keyboards.get_achievements_menu_keyboard()
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in achievements_view for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке достижений. Попробуйте позже.",
            reply_markup=keyboards.get_achievements_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "achievements_add", StateFilter("*"))
async def cq_add_achievement(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback achievements_add from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text(
            "Введите дату достижения в формате ДД.ММ (например, 15.10):",
            reply_markup=keyboards.get_cancel_keyboard()
        )
        await state.set_state(SportAchievement.choosing_date)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in achievements_add for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.message(StateFilter(SportAchievement.choosing_date))
async def achievement_date_chosen(message: Message, state: FSMContext):
    logger.info(f"Achievement date chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        date_str = message.text.strip()
        try:
            datetime.strptime(date_str, '%d.%m')
        except ValueError:
            await message.answer("Ошибка. Введите дату в формате ДД.ММ (например, 15.10).", reply_markup=keyboards.get_cancel_keyboard())
            return
        await state.update_data(achievement_date=date_str)
        await message.answer("Опишите достижение (например, '25 подтягиваний'):", reply_markup=keyboards.get_cancel_keyboard())
        await state.set_state(SportAchievement.choosing_description)
    except Exception as e:
        logger.error(f"Error in achievement_date_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(StateFilter(SportAchievement.choosing_description))
async def achievement_description_chosen(message: Message, state: FSMContext):
    logger.info(f"Achievement description chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        achievement_name = message.text.strip()
        user_data = await state.get_data()
        date_str = user_data.get('achievement_date')
        try:
            day, month = map(int, date_str.split('.'))
            current_year = datetime.now().year
            date_earned = datetime(current_year, month, day).date()
        except ValueError:
            await message.answer("Ошибка в формате даты. Попробуйте снова с /achievements.", reply_markup=types.ReplyKeyboardRemove())
            await state.clear()
            return
        db.add_sport_achievement(message.from_user.id, achievement_name, date_earned)
        await message.answer(
            f"🏆 Достижение '{achievement_name}' ({date_earned.strftime('%d.%m.%Y')}) добавлено!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        await message.answer("Что вы хотите сделать с достижениями?", reply_markup=keyboards.get_achievements_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in achievement_description_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "menu_settings")
async def cq_menu_settings(callback: CallbackQuery):
    logger.info(f"Received callback menu_settings from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Меню настроек:", reply_markup=keyboards.get_settings_keyboard("Asia/Almaty"))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_settings for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data == "menu_mark_done")
async def cq_mark_done_menu(callback: CallbackQuery):
    logger.info(f"Received callback menu_mark_done from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Какое достижение отметить?", reply_markup=keyboards.get_mark_done_keyboard(callback.from_user.id))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_mark_done for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.message(Command("stats"))
@dp.callback_query(lambda c: c.data == "menu_stats")
async def show_stats(update: Message | CallbackQuery):
    user_id = update.from_user.id if isinstance(update, Message) else update.from_user.id
    logger.info(f"Received stats request from user_id: {user_id}")
    try:
        webapp_url = f"{FRONTEND_URL}?user_id={user_id}"
        message_to_answer = update if isinstance(update, Message) else update.message
        await message_to_answer.answer(
            "📊 Аналитические данные готовы, командир. Панель доступна по кнопке ниже.",
            reply_markup=keyboards.get_stats_keyboard(webapp_url)
        )
        if isinstance(update, CallbackQuery):
            await update.answer()
    except Exception as e:
        logger.error(f"Error in stats for user_id {user_id}: {e}")
        await (update if isinstance(update, Message) else update.message).answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "menu_back")
async def cq_back_to_menu(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback menu_back from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text("Выберите действие:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_back for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("done_"))
async def cq_mark_activity_done(callback: CallbackQuery):
    activity_type = callback.data.split('_')[1]
    logger.info(f"Marking activity {activity_type} for user_id: {callback.from_user.id}")
    try:
        db.mark_activity_done(callback.from_user.id, activity_type)
        await callback.answer(f"✅ {activity_type.capitalize()} засчитано!", show_alert=True)
    except Exception as e:
        logger.error(f"Error marking activity {activity_type} for user_id {callback.from_user.id}: {e}")
        await callback.answer("⚠️ Ошибка. Попробуйте позже.", show_alert=True)

@dp.message(Command("clear_stats"))
@dp.callback_query(lambda c: c.data == "menu_clear_stats")
async def cmd_clear_stats(update: Message | CallbackQuery):
    user_id = update.from_user.id if isinstance(update, Message) else update.from_user.id
    logger.info(f"Received clear_stats request from user_id: {user_id}")
    try:
        text = "Вы уверены, что хотите удалить ВСЕ свои данные безвозвратно? Это действие необратимо."
        markup = keyboards.get_confirm_clear_keyboard()
        message_to_edit = update if isinstance(update, Message) else update.message
        await message_to_edit.answer(text, reply_markup=markup)
        if isinstance(update, CallbackQuery):
            await update.answer()
    except Exception as e:
        logger.error(f"Error in clear_stats for user_id {user_id}: {e}")
        await (update if isinstance(update, Message) else update.message).answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "confirm_clear_yes")
async def cq_confirm_clear(callback: CallbackQuery):
    logger.info(f"Confirming clear data for user_id: {callback.from_user.id}")
    try:
        db.clear_user_data(callback.from_user.id)
        await callback.message.edit_text("⚔️ Все ваши данные удалены. Начнем с чистого листа. Используй /start")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error clearing data for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data == "confirm_clear_no")
async def cq_cancel_clear(callback: CallbackQuery):
    logger.info(f"Canceling clear data for user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Операция отменена. Возвращаю в главное меню.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_clear for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data == "fsm_cancel", StateFilter("*"))
async def cq_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Canceling FSM for user_id: {callback.from_user.id}")
    try:
        current_state = await state.get_state()
        if current_state is None:
            await callback.message.delete()
            await callback.answer("Здесь нечего отменять.")
            return
        await state.clear()
        await callback.message.edit_text(
            "Действие отменено. Возвращаю в главное меню.",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in fsm_cancel for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.message(Command("log"))
@dp.callback_query(lambda c: c.data == "menu_log_activity")
async def start_log_activity(update: Message | CallbackQuery, state: FSMContext):
    user_id = update.from_user.id if isinstance(update, Message) else update.from_user.id
    logger.info(f"Starting log activity for user_id: {user_id}")
    try:
        message_to_use = update if isinstance(update, Message) else update.message
        await message_to_use.answer("Выберите тип активности:", reply_markup=keyboards.get_log_activity_type_keyboard())
        await state.set_state(LogActivity.choosing_type)
        if isinstance(update, CallbackQuery):
            await update.answer()
    except Exception as e:
        logger.error(f"Error in start_log_activity for user_id {user_id}: {e}")
        await (update if isinstance(update, Message) else update.message).answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data.startswith("log_type_"), StateFilter(LogActivity.choosing_type))
async def activity_type_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Activity type chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        activity_type = callback.data.split('_')[2]  # screen или productive
        await state.update_data(activity_type=activity_type)
        await callback.message.edit_text(
            f"Какую {'не полезную' if activity_type == 'screen' else 'полезную'} активность вы хотите записать? (например: {'YouTube, Соцсети' if activity_type == 'screen' else 'Чтение, Работа'})",
            reply_markup=keyboards.get_cancel_keyboard()
        )
        await state.set_state(LogActivity.choosing_activity_name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in activity_type_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.message(StateFilter(LogActivity.choosing_activity_name))
async def activity_name_chosen(message: Message, state: FSMContext):
    logger.info(f"Activity name chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        await state.update_data(activity_name=message.text)
        await message.answer("Сколько минут это заняло? Введите только число.", reply_markup=keyboards.get_cancel_keyboard())
        await state.set_state(LogActivity.choosing_duration)
    except Exception as e:
        logger.error(f"Error in activity_name_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(StateFilter(LogActivity.choosing_duration))
async def duration_chosen(message: Message, state: FSMContext):
    logger.info(f"Duration chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        if not message.text or not message.text.isdigit():
            await message.answer("Ошибка. Пожалуйста, введите число (количество минут).", reply_markup=keyboards.get_cancel_keyboard())
            return
        user_data = await state.get_data()
        activity_name = user_data.get('activity_name', 'Неизвестная активность')
        activity_type = user_data.get('activity_type', 'screen')
        duration_minutes = int(message.text)
        if activity_type == 'screen':
            db.log_custom_activity(message.from_user.id, activity_name, duration_minutes)
        else:
            db.log_productive_activity(message.from_user.id, activity_name, duration_minutes)
        await message.answer(
            f"Записано: '{activity_name}' - {duration_minutes} мин. ({'Не полезная' if activity_type == 'screen' else 'Полезная'} активность)",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        await message.answer("Главное меню:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
    except Exception as e:
        logger.error(f"Error in duration_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("morning"))
async def cmd_morning(message: Message, state: FSMContext):
    logger.info(f"Received /morning from user_id: {message.from_user.id}")
    try:
        user_id = message.from_user.id
        with db.get_db() as db_session:
            stmt = text("SELECT morning_poll_completed, is_rest_day FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
            result = db_session.execute(stmt, {'uid': user_id, 'today': date.today()}).first()
            db_session.commit()
            if result and result._asdict()['morning_poll_completed']:
                await message.answer("☀️ Утренний опрос уже завершен сегодня. Используй /menu для других действий.", reply_markup=types.ReplyKeyboardRemove())
                return
            if result and result._asdict()['is_rest_day']:
                await message.answer("🏖️ Сегодня день отдыха. Хорошего отдыха, командир!", reply_markup=types.ReplyKeyboardRemove())
                return
        await state.clear()
        if user_id in user_plans:
            del user_plans[user_id]
        await message.answer("☀️ Какой у вас сегодня день?", reply_markup=keyboards.get_morning_day_type_keyboard())
        await state.set_state(MorningPoll.choosing_day_type)
    except Exception as e:
        logger.error(f"Error in /morning for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data.startswith("plan_day_"), StateFilter(MorningPoll.choosing_day_type))
async def day_type_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Day type chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        day_type = callback.data.split('_')[2]  # rest или workday
        if day_type == 'rest':
            db.save_morning_plan(
                user_id=callback.from_user.id,
                screen_time=0,
                workout=0,
                english=0,
                coding=0,
                planning=0,
                stretching=0,
                reflection=0,
                walk=0,
                is_rest_day=True
            )
            await callback.message.edit_text("🏖️ Хорошего отдыха, командир!")
            await state.clear()
        else:
            if callback.from_user.id in user_plans:
                del user_plans[callback.from_user.id]
            user_plans[callback.from_user.id] = {
                'time': None,
                'workout': 0,
                'english': 0,
                'coding': 0,
                'planning': 0,
                'stretching': 0,
                'reflection': 0,
                'walk': 0
            }
            message_text = "☀️ Составьте план на сегодня:\n\n⏰ Лимит времени: не выбрано\n" + "\n".join([
                f"🏋️ Тренировка: {'✅' if user_plans[callback.from_user.id]['workout'] else '❌'}",
                f"🗣 Язык: {'✅' if user_plans[callback.from_user.id]['english'] else '❌'}",
                f"💻 Программирование: {'✅' if user_plans[callback.from_user.id]['coding'] else '❌'}",
                f"📝 Планирование: {'✅' if user_plans[callback.from_user.id]['planning'] else '❌'}",
                f"🧘 Растяжка: {'✅' if user_plans[callback.from_user.id]['stretching'] else '❌'}",
                f"🤔 Рефлексия: {'✅' if user_plans[callback.from_user.id]['reflection'] else '❌'}",
                f"🚶 Прогулка: {'✅' if user_plans[callback.from_user.id]['walk'] else '❌'}"
            ])
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboards.get_morning_poll_keyboard(user_plans.get(callback.from_user.id))
            )
            await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in day_type_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("plan_"))
async def handle_morning_plan(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split('_')
    logger.info(f"Morning plan action: {callback.data} for user_id: {user_id}")
    try:
        if user_id not in user_plans:
            user_plans[user_id] = {
                'time': None,
                'workout': 0,
                'english': 0,
                'coding': 0,
                'planning': 0,
                'stretching': 0,
                'reflection': 0,
                'walk': 0
            }
        if action[1] == 'time':
            time_map = {
                '2': 2 * 60,
                '3': 3 * 60,
                '4': 4 * 60,
                '5': 5 * 60,
                '6': 6 * 60
            }
            selected_time = action[2]
            user_plans[user_id]['time'] = time_map.get(selected_time, user_plans[user_id]['time'])
            await callback.answer(f"Лимит времени: {selected_time}ч")
        elif action[1] == 'toggle':
            habit = action[2]
            user_plans[user_id][habit] = 1 - user_plans[user_id][habit]
            habit_display = {
                'workout': 'Тренировка',
                'english': 'Язык',
                'coding': 'Программирование',
                'planning': 'Планирование',
                'stretching': 'Растяжка',
                'reflection': 'Рефлексия',
                'walk': 'Прогулка'
            }.get(habit, habit.capitalize())
            status_text = "в планах" if user_plans[user_id][habit] == 1 else "не в планах"
            await callback.answer(f"{habit_display} {status_text}")
        elif action[1] == 'done':
            plan = user_plans.get(user_id)
            if plan is None or plan['time'] is None:
                await callback.answer("Пожалуйста, выберите лимит времени.", show_alert=True)
                return
            try:
                with db.get_db() as db_session:
                    stmt = text("SELECT id FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
                    result = db_session.execute(stmt, {'uid': user_id, 'today': date.today()}).first()
                    if result:
                        stmt = text("""
                            UPDATE daily_stats SET
                                screen_time_goal = :screen_time_goal,
                                screen_time_actual = :screen_time_actual,
                                workout_planned = :workout_planned,
                                workout_done = :workout_done,
                                english_planned = :english_planned,
                                english_done = :english_done,
                                coding_planned = :coding_planned,
                                coding_done = :coding_done,
                                planning_planned = :planning_planned,
                                planning_done = :planning_done,
                                stretching_planned = :stretching_planned,
                                stretching_done = :stretching_done,
                                reflection_planned = :reflection_planned,
                                reflection_done = :reflection_done,
                                walk_planned = :walk_planned,
                                walk_done = :walk_done,
                                morning_poll_completed = :morning_poll_completed,
                                is_rest_day = :is_rest_day
                            WHERE user_id = :uid AND stat_date = :today
                        """)
                    else:
                        stmt = text("""
                            INSERT INTO daily_stats (
                                user_id, stat_date, screen_time_goal, screen_time_actual,
                                workout_planned, workout_done, english_planned, english_done,
                                coding_planned, coding_done, planning_planned, planning_done,
                                stretching_planned, stretching_done, reflection_planned, reflection_done,
                                walk_planned, walk_done,
                                morning_poll_completed, is_rest_day
                            ) VALUES (
                                :uid, :today, :screen_time_goal, :screen_time_actual,
                                :workout_planned, :workout_done, :english_planned, :english_done,
                                :coding_planned, :coding_done, :planning_planned, :planning_done,
                                :stretching_planned, :stretching_done, :reflection_planned, :reflection_done,
                                :walk_planned, :walk_done,
                                :morning_poll_completed, :is_rest_day
                            )
                        """)
                    db_session.execute(stmt, {
                        'uid': user_id,
                        'today': date.today(),
                        'screen_time_goal': plan['time'],
                        'screen_time_actual': 0,
                        'workout_planned': plan['workout'],
                        'workout_done': 0,
                        'english_planned': plan['english'],
                        'english_done': 0,
                        'coding_planned': plan['coding'],
                        'coding_done': 0,
                        'planning_planned': plan['planning'],
                        'planning_done': 0,
                        'stretching_planned': plan['stretching'],
                        'stretching_done': 0,
                        'reflection_planned': plan['reflection'],
                        'reflection_done': 0,
                        'walk_planned': plan['walk'],
                        'walk_done': 0,
                        'morning_poll_completed': True,
                        'is_rest_day': False
                    })
                    db_session.commit()
                del user_plans[user_id]
                await callback.message.edit_text("⚔️ План на день сохранён. Продуктивного дня, командир!")
                await callback.answer()
                return  # Выходим, чтобы не вызывать edit_text ниже
            except Exception as e:
                logger.error(f"Error saving morning plan for user_id {user_id}: {e}")
                await callback.message.edit_text("⚠️ Ошибка сохранения плана. Попробуйте позже.")
                db_session.rollback()
                await callback.answer()
                return
        # Обновляем сообщение с текущим состоянием плана
        plan = user_plans[user_id]
        time_text = f"{plan['time'] // 60}ч" if plan['time'] else "не выбрано"
        activities = [
            f"🏋️ Тренировка: {'✅' if plan['workout'] else '❌'}",
            f"🗣 Язык: {'✅' if plan['english'] else '❌'}",
            f"💻 Программирование: {'✅' if plan['coding'] else '❌'}",
            f"📝 Планирование: {'✅' if plan['planning'] else '❌'}",
            f"🧘 Растяжка: {'✅' if plan['stretching'] else '❌'}",
            f"🤔 Рефлексия: {'✅' if plan['reflection'] else '❌'}",
            f"🚶 Прогулка: {'✅' if plan['walk'] else '❌'}"
        ]
        message_text = f"☀️ Составьте план на сегодня:\n\n⏰ Лимит времени: {time_text}\n" + "\n".join(activities)
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboards.get_morning_poll_keyboard(user_plans.get(user_id))
        )
        await callback.answer()
    except TelegramAPIError as e:
        if "message is not modified" in str(e):
            logger.info(f"Message not modified for user_id {user_id}, skipping edit")
            await callback.answer()
        else:
            logger.error(f"TelegramAPIError in handle_morning_plan for user_id {user_id}: {e}")
            await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_morning_plan for user_id {user_id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")
        await callback.answer()

# --- API для веб-приложения ---
@fastapi_app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
async def read_user_stats(user_id: int):
    logger.info(f"API request for stats, user_id: {user_id}")
    try:
        with db.get_db() as db_session:
            today = date.today()
            today_iso = today.isoformat()
            stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
            today_main_stats = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).first()
            if not today_main_stats:
                logger.warning(f"No daily stats found for user_id: {user_id}, date: {today}")
                raise HTTPException(status_code=404, detail="План на сегодня не найден.")
            
            today_main_stats_dict = today_main_stats._asdict()
            
            # Запрос на экранные активности за сегодня
            stmt = text("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = :uid AND activity_date = :today")
            today_screen_activities = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            screen_breakdown = {row._asdict()['activity_name']: row._asdict()['duration_minutes'] for row in today_screen_activities}
            total_screen_minutes_today = sum(screen_breakdown.values())
            
            # Запрос на полезные активности за сегодня
            stmt = text("SELECT activity_name, duration_minutes FROM productive_activities WHERE user_id = :uid AND activity_date = :today")
            today_productive_activities = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            productive_breakdown = {row._asdict()['activity_name']: row._asdict()['duration_minutes'] for row in today_productive_activities}
            total_productive_minutes_today = sum(productive_breakdown.values())
            
            today_data = TodayStats(
                screen_time_goal=today_main_stats_dict['screen_time_goal'],
                screen_time_actual=total_screen_minutes_today,
                screen_time_breakdown=screen_breakdown,
                productive_time_actual=total_productive_minutes_today,
                productive_time_breakdown=productive_breakdown,
                workout_planned=today_main_stats_dict['workout_planned'],
                workout_done=today_main_stats_dict['workout_done'],
                english_planned=today_main_stats_dict['english_planned'],
                english_done=today_main_stats_dict['english_done'],
                coding_planned=today_main_stats_dict['coding_planned'],
                coding_done=today_main_stats_dict['coding_done'],
                planning_planned=today_main_stats_dict['planning_planned'],
                planning_done=today_main_stats_dict['planning_done'],
                stretching_planned=today_main_stats_dict['stretching_planned'],
                stretching_done=today_main_stats_dict['stretching_done'],
                reflection_planned=today_main_stats_dict['reflection_planned'],
                reflection_done=today_main_stats_dict['reflection_done'],
                morning_poll_completed=today_main_stats_dict['morning_poll_completed'],
                is_rest_day=today_main_stats_dict['is_rest_day']
            )
            
            seven_days_ago = today - timedelta(days=7)
            stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date >= :start AND stat_date < :today ORDER BY stat_date DESC")
            history_main_stats = db_session.execute(stmt, {'uid': user_id, 'start': seven_days_ago.isoformat(), 'today': today_iso}).fetchall()
            
            stmt = text("SELECT activity_date, SUM(duration_minutes) as total_minutes FROM screen_activities WHERE user_id = :uid AND activity_date >= :start AND activity_date < :today GROUP BY activity_date")
            history_screen_time = db_session.execute(stmt, {'uid': user_id, 'start': seven_days_ago.isoformat(), 'today': today_iso}).fetchall()
            screen_time_map = {row._asdict()['activity_date']: row._asdict()['total_minutes'] for row in history_screen_time}
            
            stmt = text("SELECT activity_date, SUM(duration_minutes) as total_minutes FROM productive_activities WHERE user_id = :uid AND activity_date >= :start AND activity_date < :today GROUP BY activity_date")
            history_productive_time = db_session.execute(stmt, {'uid': user_id, 'start': seven_days_ago.isoformat(), 'today': today_iso}).fetchall()
            productive_time_map = {row._asdict()['activity_date']: row._asdict()['total_minutes'] for row in history_productive_time}
            
            history_data = [
                HistoryDayStats(
                    date=day_stats._asdict()['stat_date'],
                    screen_time_goal=day_stats._asdict()['screen_time_goal'],
                    screen_time_actual=screen_time_map.get(day_stats._asdict()['stat_date'], 0),
                    productive_time_actual=productive_time_map.get(day_stats._asdict()['stat_date'], 0),
                    workout_done=day_stats._asdict()['workout_done'],
                    english_done=day_stats._asdict()['english_done'],
                    coding_done=day_stats._asdict()['coding_done'],
                    planning_done=day_stats._asdict()['planning_done'],
                    stretching_done=day_stats._asdict()['stretching_done'],
                    reflection_done=day_stats._asdict()['reflection_done'],
                    is_rest_day=day_stats._asdict()['is_rest_day']
                )
                for day_stats in history_main_stats
            ]
            
            db_session.commit()
            
            return UserStatsResponse(user_id=user_id, today=today_data, history=history_data)
    except HTTPException as e:
        logger.error(f"HTTPException in /api/stats/{user_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in /api/stats/{user_id}: {e}")
        db_session.rollback()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

@fastapi_app.api_route("/ping", methods=["GET", "HEAD"])
async def handle_ping(request: Request):
    logger.info(f"Received {request.method} /ping request from {request.client.host}")
    return {"status": "ok"}

@fastapi_app.get("/api/morning/cron")
async def morning_poll_cron():
    logger.info("Running morning poll CRON via GET")
    now = pendulum.now(TIMEZONE)
    if not (7 <= now.hour <= 9):
        logger.info(f"Skipping morning poll CRON: current time {now} is outside 7:00-9:00 Asia/Almaty")
        return {"status": "skipped", "message": "Outside morning poll window"}
    
    try:
        with db.get_db() as db_session:
            stmt = text("SELECT user_id FROM users")
            users = db_session.execute(stmt).fetchall()
            if not users:
                logger.warning("No users found in the database")
                return {"status": "skipped", "message": "No users in database"}
            for user in users:
                user_id = user._asdict()['user_id']
                try:
                    stmt_check = text("SELECT morning_poll_completed, is_rest_day FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
                    result = db_session.execute(stmt_check, {'uid': user_id, 'today': date.today()}).first()
                    if result and (result._asdict()['morning_poll_completed'] or result._asdict()['is_rest_day']):
                        logger.info(f"Skipping morning poll for user_id: {user_id}, already completed or rest day")
                        continue
                    # Инициализация FSM
                    dp.storage.set_state(chat_id=user_id, user_id=user_id, state=MorningPoll.choosing_day_type)
                    await bot.send_message(
                        user_id,
                        "☀️ Доброе утро, командир! Какой у вас сегодня день?",
                        reply_markup=keyboards.get_morning_day_type_keyboard()
                    )
                    logger.info(f"Sent morning poll to user_id: {user_id}")
                except TelegramAPIError as e:
                    logger.error(f"Failed to send morning poll to user_id {user_id}: {e}")
            db_session.commit()
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Error in morning poll CRON: {e}")
        db_session.rollback()
        return {"status": "error", "message": str(e)}

@fastapi_app.get("/api/evening/cron")
async def evening_summary_cron():
    logger.info("Running evening summary CRON via GET")
    now = pendulum.now(TIMEZONE)
    if not (19 <= now.hour <= 21):
        logger.info(f"Skipping evening summary CRON: current time {now} is outside 19:00-21:00 Asia/Almaty")
        return {"status": "skipped", "message": "Outside evening summary window"}
    
    try:
        with db.get_db() as db_session:
            stmt = text("SELECT user_id, is_rest_day FROM daily_stats WHERE stat_date = :today")
            users = db_session.execute(stmt, {'today': date.today()}).fetchall()
            if not users:
                logger.warning("No users with stats for today found")
                return {"status": "skipped", "message": "No users with stats for today"}
            for user in users:
                user_id = user._asdict()['user_id']
                is_rest_day = user._asdict()['is_rest_day']
                try:
                    if is_rest_day:
                        await bot.send_message(user_id, "🌙 В дни разгрузки данные отсутствуют.")
                        logger.info(f"Sent rest day evening summary to user_id: {user_id}")
                        continue
                    stats = db.get_today_stats_for_user(user_id)
                    if not stats:
                        logger.info(f"No stats for user_id: {user_id} today")
                        continue
                    time_actual = db.get_today_screen_time(user_id)
                    time_goal = stats['screen_time_goal']
                    time_status = "✅ В пределах лимита!" if time_actual / 60 <= time_goal else "❌ Превышен лимит!"
                    summary_lines = [
                        "🌙 Вечерний отчёт, командир:\n",
                        f"📱 Экранное время: ~{round(time_actual / 60, 1)}ч из {time_goal // 60}ч ({time_status})\n"
                    ]
                    def get_status(planned, done):
                        return "не запланировано" if not planned else "✅ Выполнено!" if done else "❌ Пропущено"
                    summary_lines.extend([
                        f"⚔️ Тренировка: {get_status(stats['workout_planned'], stats['workout_done'])}",
                        f"🎓 Язык: {get_status(stats['english_planned'], stats['english_done'])}",
                        f"💻 Программирование: {get_status(stats['coding_planned'], stats['coding_done'])}",
                        f"📝 Планирование: {get_status(stats['planning_planned'], stats['planning_done'])}",
                        f"🧘 Растяжка: {get_status(stats['stretching_planned'], stats['stretching_done'])}",
                        f"🤔 Рефлексия: {get_status(stats['reflection_planned'], stats['reflection_done'])}",
                        f"🚶 Прогулка: {get_status(stats['walk_planned'], stats['walk_done'])}",
                    ])
                    await bot.send_message(user_id, "\n".join(summary_lines))
                    logger.info(f"Sent evening summary to user_id: {user_id}")
                except TelegramAPIError as e:
                    logger.error(f"Failed to send evening summary to user_id {user_id}: {e}")
            db_session.commit()
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Error in evening summary CRON: {e}")
        db_session.rollback()
        return {"status": "error", "message": str(e)}

@fastapi_app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Handling request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Error processing request {request.method} {request.url}: {e}")
        raise

@fastapi_app.on_event("startup")
async def on_startup():
    logger.info(f"Starting application, setting webhook to {WEBHOOK_URL}")
    def log_memory():
        while True:
            process = psutil.Process()
            mem_info = process.memory_info()
            logger.info(f"Memory: RSS={mem_info.rss / 1024 / 1024:.2f} MB, VMS={mem_info.vms / 1024 / 1024:.2f} MB")
            time.sleep(60)
    threading.Thread(target=log_memory, daemon=True).start()
    try:
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True, max_connections=30)
        logger.info("Webhook set successfully")
    except TelegramAPIError as e:
        logger.error(f"Failed to set webhook: {e}")
        raise RuntimeError(f"Webhook setup failed: {e}")
    try:
        db.init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")

@fastapi_app.on_event("shutdown")
async def on_shutdown():
    logger.warning("Application shutting down, skipping webhook deletion for 24/7 uptime...")

@fastapi_app.post(f"/webhook/{BOT_TOKEN}")
async def bot_webhook(request: Request):
    logger.info(f"Received webhook request")
    try:
        update = await request.json()
        logger.debug(f"Webhook update: {update}")
        telegram_update = types.Update(**update)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"ok": True}
    except ValueError as e:
        logger.error(f"Invalid JSON in webhook request: {e}")
        raise HTTPException(status_code=422, detail="Некорректный JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server")
    uvicorn.run(
        "app:fastapi_app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        timeout_keep_alive=300,
        timeout_graceful_shutdown=60,
        log_level="debug"
    )