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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('aiogram').setLevel(logging.DEBUG)
logging.getLogger('fastapi').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://your-frontend-render-url")
RENDER_URL = os.getenv("RENDER_URL", "").rstrip('/')
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# Инициализация
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

# Модели Pydantic для API
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
    walk_done: int
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
    walk_planned: int
    walk_done: int
    morning_poll_completed: bool
    is_rest_day: bool
    habits: Dict[str, bool] = {}
    productivity_questions: Dict[str, str] = {}
    goals: Dict[str, bool] = {}  # Добавлено для целей

class Goal(BaseModel):
    id: int
    goal_name: str
    goal_type: str
    target_value: int
    current_value: int
    start_date: str
    end_date: str
    is_completed: bool
    streak: int  # Добавлено для отслеживания стрика

class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]
    goals: List[Goal]
    habits: List[Dict[str, str]]

# FSM состояния
class LogActivity(StatesGroup):
    choosing_type = State()
    choosing_activity_name = State()
    choosing_duration = State()

class MorningPoll(StatesGroup):
    choosing_day_type = State()

class SportAchievement(StatesGroup):
    choosing_date = State()
    choosing_description = State()

class SetGoal(StatesGroup):
    choosing_goal_type = State()
    choosing_goal_name = State()
    choosing_target_value = State()
    choosing_duration = State()

class AddHabit(StatesGroup):
    choosing_habit_name = State()

class EveningHabitPoll(StatesGroup):
    answering_habit = State()

class EveningGoalPoll(StatesGroup):  # Добавлено для целей
    answering_goal = State()

class ProductivityPoll(StatesGroup):
    answering_question = State()

class TipsSelection(StatesGroup):
    choosing_category = State()
    choosing_tip = State()

# Глобальное хранилище
user_plans: Dict[int, Dict[str, Optional[int]]] = {}
user_habit_answers: Dict[int, Dict[str, bool]] = {}
user_goal_answers: Dict[int, Dict[str, bool]] = {}  # Добавлено для целей
user_productivity_answers: Dict[int, Dict[str, str]] = {}

# Логирование ошибок
def log_uncaught_exceptions(exctype, value, tb):
    logger.error("Uncaught exception", exc_info=(exctype, value, tb))

sys.excepthook = log_uncaught_exceptions

# Обработчик сигналов
def handle_shutdown(signum, frame):
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    logger.info("Skipping webhook deletion to maintain 24/7 operation")

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# Telegram handlers
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

@dp.message(Command("goals"))
async def cmd_goals(message: Message, state: FSMContext):
    logger.info(f"Received /goals from user_id: {message.from_user.id}")
    try:
        await state.clear()
        await message.answer("Что вы хотите сделать с целями?", reply_markup=keyboards.get_goals_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in /goals for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("habits"))
async def cmd_habits(message: Message, state: FSMContext):
    logger.info(f"Received /habits from user_id: {message.from_user.id}")
    try:
        await state.clear()
        await message.answer("Что вы хотите сделать с привычками?", reply_markup=keyboards.get_habits_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in /habits for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("tips"))
async def cmd_tips(message: Message, state: FSMContext):
    logger.info(f"Received /tips from user_id: {message.from_user.id}")
    try:
        await state.clear()
        await message.answer("Выберите категорию советов:", reply_markup=keyboards.get_tips_categories_keyboard())
        await state.set_state(TipsSelection.choosing_category)
    except Exception as e:
        logger.error(f"Error in /tips for user_id {message.from_user.id}: {e}")
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

@dp.callback_query(lambda c: c.data == "menu_goals")
async def cq_goals_menu(callback: CallbackQuery):
    logger.info(f"Received callback menu_goals from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Что вы хотите сделать с целями?", reply_markup=keyboards.get_goals_menu_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_goals for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "goals_view")
async def cq_view_goals(callback: CallbackQuery):
    logger.info(f"Received callback goals_view from user_id: {callback.from_user.id}")
    try:
        with db.get_db() as db_session:
            stmt = text("""
                SELECT id, goal_name, goal_type, target_value, current_value, start_date, end_date, is_completed, streak
                FROM goals WHERE user_id = :uid AND is_completed = false ORDER BY start_date
            """)
            goals = db_session.execute(stmt, {'uid': callback.from_user.id}).fetchall()
            if not goals:
                await callback.message.edit_text(
                    "🎯 У вас пока нет активных целей. Добавьте первую!",
                    reply_markup=keyboards.get_goals_menu_keyboard()
                )
                await callback.answer()
                return
            goal_lines = ["🎯 Ваши цели:\n"]
            for goal in goals:
                progress = (goal.current_value / goal.target_value * 100) if goal.target_value > 0 else 0
                streak_info = f", стрик: {goal.streak} {'недель' if goal.goal_type == 'weekly' else 'дней'}" if goal.streak > 0 else ""
                goal_lines.append(f"• {goal.goal_name} ({goal.goal_type}): {goal.current_value}/{goal.target_value} ({progress:.1f}%){streak_info}")
            await callback.message.edit_text(
                "\n".join(goal_lines),
                reply_markup=keyboards.get_goals_menu_keyboard()
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in goals_view for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке целей. Попробуйте позже.",
            reply_markup=keyboards.get_goals_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "goals_add", StateFilter("*"))
async def cq_add_goal(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback goals_add from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text(
            "Выберите тип цели:", 
            reply_markup=keyboards.get_goal_type_keyboard()
        )
        await state.set_state(SetGoal.choosing_goal_type)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in goals_add for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data.startswith("goal_type_"), StateFilter(SetGoal.choosing_goal_type))
async def goal_type_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Goal type chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        goal_type = callback.data.split('_')[2]
        await state.update_data(goal_type=goal_type)
        await callback.message.edit_text(
            "Введите название цели (например, 'Тренироваться' или 'Съедать 100г белка'):", 
            reply_markup=keyboards.get_cancel_keyboard()
        )
        await state.set_state(SetGoal.choosing_goal_name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in goal_type_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.message(StateFilter(SetGoal.choosing_goal_name))
async def goal_name_chosen(message: Message, state: FSMContext):
    logger.info(f"Goal name chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        await state.update_data(goal_name=message.text.strip())
        user_data = await state.get_data()
        goal_type = user_data.get('goal_type')
        if goal_type == 'weekly':
            await message.answer("Сколько дней в неделю вы хотите выполнять цель? (Введите число от 1 до 7):", reply_markup=keyboards.get_cancel_keyboard())
            await state.set_state(SetGoal.choosing_target_value)
        else:
            await message.answer("Цель будет выполняться каждый день. Подтвердите создание цели:", reply_markup=keyboards.get_goal_confirm_keyboard())
            await state.set_state(SetGoal.choosing_duration)
    except Exception as e:
        logger.error(f"Error in goal_name_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(StateFilter(SetGoal.choosing_target_value))
async def goal_target_chosen(message: Message, state: FSMContext):
    logger.info(f"Goal target chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        if not message.text.isdigit() or not (1 <= int(message.text) <= 7):
            await message.answer("Ошибка. Введите число от 1 до 7.", reply_markup=keyboards.get_cancel_keyboard())
            return
        await state.update_data(target_value=int(message.text))
        await message.answer("Подтвердите создание цели:", reply_markup=keyboards.get_goal_confirm_keyboard())
        await state.set_state(SetGoal.choosing_duration)
    except Exception as e:
        logger.error(f"Error in goal_target_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "goal_confirm", StateFilter(SetGoal.choosing_duration))
async def goal_duration_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Goal confirmed by user_id: {callback.from_user.id}")
    try:
        user_data = await state.get_data()
        goal_type = user_data.get('goal_type')
        goal_name = user_data.get('goal_name')
        target_value = user_data.get('target_value', 1 if goal_type == 'daily' else None)
        if not target_value:
            await callback.message.edit_text("Ошибка. Целевое значение не задано.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
            await state.clear()
            return
        start_date = date.today()
        end_date = start_date + timedelta(days=365)  # Цели активны год
        db.add_goal(
            user_id=callback.from_user.id,
            goal_name=goal_name,
            goal_type=goal_type,
            target_value=target_value,
            current_value=0,
            start_date=start_date,
            end_date=end_date,
            streak=0
        )
        await callback.message.edit_text(
            f"🎯 Цель '{goal_name}' ({'ежедневная' if goal_type == 'daily' else f'повторяющаяся, {target_value} дней в неделю'}) добавлена!",
            reply_markup=keyboards.get_goals_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in goal_duration_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "menu_habits")
async def cq_habits_menu(callback: CallbackQuery):
    logger.info(f"Received callback menu_habits from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Что вы хотите сделать с привычками?", reply_markup=keyboards.get_habits_menu_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_habits for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "habits_add", StateFilter("*"))
async def cq_add_habit(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback habits_add from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text(
            "Введите название привычки (например, 'Читать 30 минут'):", 
            reply_markup=keyboards.get_cancel_keyboard()
        )
        await state.set_state(AddHabit.choosing_habit_name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in habits_add for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.message(StateFilter(AddHabit.choosing_habit_name))
async def habit_name_chosen(message: Message, state: FSMContext):
    logger.info(f"Habit name chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        habit_name = message.text.strip()
        db.add_habit(message.from_user.id, habit_name)
        await message.answer(
            f"✅ Привычка '{habit_name}' добавлена!",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        await message.answer("Что вы хотите сделать с привычками?", reply_markup=keyboards.get_habits_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in habit_name_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data == "habits_view")
async def cq_view_habits(callback: CallbackQuery):
    logger.info(f"Received callback habits_view from user_id: {callback.from_user.id}")
    try:
        with db.get_db() as db_session:
            habits = db.get_habits_with_progress(callback.from_user.id)
            if not habits:
                await callback.message.edit_text(
                    "📋 У вас пока нет привычек. Добавьте первую!",
                    reply_markup=keyboards.get_habits_menu_keyboard()
                )
                await callback.answer()
                return
            habit_lines = ["📋 Ваши привычки:\n"]
            for habit in habits:
                streak_text = f"{habit['streak']} {'день подряд' if habit['streak'] % 10 == 1 and habit['streak'] != 11 else 'дней подряд'}" if habit['streak'] > 0 else "0 дней подряд"
                habit_lines.append(f"• {habit['name']} ({streak_text})")
            await callback.message.edit_text(
                "\n".join(habit_lines),
                reply_markup=keyboards.get_habits_menu_keyboard()
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in habits_view for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке привычек. Попробуйте позже.",
            reply_markup=keyboards.get_habits_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "achievements_delete")
async def cq_delete_achievements_menu(callback: CallbackQuery):
    """
    Показывает список достижений для выбора удаления.
    """
    logger.info(f"Received callback achievements_delete from user_id: {callback.from_user.id}")
    try:
        with db.get_db() as db_session:
            stmt = text("SELECT id, achievement_name, date_earned FROM sport_achievements WHERE user_id = :uid ORDER BY date_earned DESC")
            achievements = db_session.execute(stmt, {'uid': callback.from_user.id}).fetchall()
            if not achievements:
                await callback.message.edit_text(
                    "🏆 У вас пока нет достижений для удаления.",
                    reply_markup=keyboards.get_achievements_menu_keyboard()
                )
                await callback.answer()
                return
            keyboard = keyboards.get_delete_achievements_keyboard(callback.from_user.id)
            await callback.message.edit_text(
                "Выберите достижение для удаления:",
                reply_markup=keyboard
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in achievements_delete for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке достижений для удаления. Попробуйте позже.",
            reply_markup=keyboards.get_achievements_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_achievement_"))
async def cq_delete_achievement(callback: CallbackQuery):
    """
    Удаляет выбранное достижение.
    """
    logger.info(f"Received callback delete_achievement for user_id: {callback.from_user.id}: {callback.data}")
    try:
        achievement_id = int(callback.data.split("_")[-1])
        db.delete_sport_achievement(callback.from_user.id, achievement_id)
        await callback.message.edit_text(
            "🏆 Достижение успешно удалено!",
            reply_markup=keyboards.get_achievements_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error deleting achievement for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при удалении достижения. Попробуйте позже.",
            reply_markup=keyboards.get_achievements_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "habits_delete")
async def cq_delete_habits_menu(callback: CallbackQuery):
    """
    Показывает список привычек для выбора удаления.
    """
    logger.info(f"Received callback habits_delete from user_id: {callback.from_user.id}")
    try:
        habits = db.get_habits(callback.from_user.id)
        if not habits:
            await callback.message.edit_text(
                "📋 У вас пока нет привычек для удаления.",
                reply_markup=keyboards.get_habits_menu_keyboard()
            )
            await callback.answer()
            return
        keyboard = keyboards.get_delete_habits_keyboard(callback.from_user.id)
        await callback.message.edit_text(
            "Выберите привычку для удаления:",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in habits_delete for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке привычек для удаления. Попробуйте позже.",
            reply_markup=keyboards.get_habits_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_habit_"))
async def cq_delete_habit(callback: CallbackQuery):
    """
    Удаляет выбранную привычку.
    """
    logger.info(f"Received callback delete_habit for user_id: {callback.from_user.id}: {callback.data}")
    try:
        habit_id = int(callback.data.split("_")[-1])
        db.delete_habit(callback.from_user.id, habit_id)
        await callback.message.edit_text(
            "✅ Привычка успешно удалена!",
            reply_markup=keyboards.get_habits_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error deleting habit for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при удалении привычки. Попробуйте позже.",
            reply_markup=keyboards.get_habits_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "goals_delete")
async def cq_delete_goals_menu(callback: CallbackQuery):
    """
    Показывает список целей для выбора удаления.
    """
    logger.info(f"Received callback goals_delete from user_id: {callback.from_user.id}")
    try:
        with db.get_db() as db_session:
            stmt = text("""
                SELECT id, goal_name, goal_type, target_value, current_value, start_date, end_date, is_completed, streak
                FROM goals WHERE user_id = :uid ORDER BY start_date
            """)
            goals = db_session.execute(stmt, {'uid': callback.from_user.id}).fetchall()
            if not goals:
                await callback.message.edit_text(
                    "🎯 У вас пока нет целей для удаления.",
                    reply_markup=keyboards.get_goals_menu_keyboard()
                )
                await callback.answer()
                return
            keyboard = keyboards.get_delete_goals_keyboard(callback.from_user.id)
            await callback.message.edit_text(
                "Выберите цель для удаления:",
                reply_markup=keyboard
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in goals_delete for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при загрузке целей для удаления. Попробуйте позже.",
            reply_markup=keyboards.get_goals_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_goal_"))
async def cq_delete_goal(callback: CallbackQuery):
    """
    Удаляет выбранную цель.
    """
    logger.info(f"Received callback delete_goal for user_id: {callback.from_user.id}: {callback.data}")
    try:
        goal_id = int(callback.data.split("_")[-1])
        db.delete_goal(callback.from_user.id, goal_id)
        await callback.message.edit_text(
            "🎯 Цель успешно удалена!",
            reply_markup=keyboards.get_goals_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error deleting goal for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка при удалении цели. Попробуйте позже.",
            reply_markup=keyboards.get_goals_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_tips", StateFilter("*"))
async def cq_tips_menu(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback menu_tips from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text("Выберите категорию советов:", reply_markup=keyboards.get_tips_categories_keyboard())
        await state.set_state(TipsSelection.choosing_category)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_tips for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data.startswith("tip_category_"), StateFilter(TipsSelection.choosing_category))
async def cq_tip_category_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Tip category chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        category = callback.data.split('_')[2]
        await state.update_data(category=category)
        tips = db.get_tips_by_category(category)
        if not tips:
            await callback.message.edit_text(
                f"Советов в категории '{category}' пока нет.",
                reply_markup=keyboards.get_tips_categories_keyboard()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            f"Советы в категории '{category}':",
            reply_markup=keyboards.get_tips_by_category_keyboard(tips)
        )
        await state.set_state(TipsSelection.choosing_tip)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in tip_category_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data.startswith("tip_") or c.data == "category" or c.data.startswith("tip_category_"), StateFilter(TipsSelection.choosing_tip))
async def cq_tip_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Tip chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        if callback.data == 'category':
            # Возвращаем пользователя к списку категорий
            logger.debug(f"User {callback.from_user.id} requested to return to categories")
            await callback.message.edit_text(
                "Выберите категорию совета:",
                reply_markup=keyboards.get_tips_categories_keyboard()
            )
            await state.set_state(TipsSelection.choosing_category)
            await callback.answer()
            return

        if callback.data.startswith('tip_category_'):
            # Возвращаем пользователя к списку советов в категории
            category = callback.data.replace("tip_category_", "")
            logger.debug(f"User {callback.from_user.id} requested tips for category: {category}")
            await state.update_data(category=category)
            tips = db.get_tips_by_category(category)
            if not tips:
                logger.warning(f"No tips found for category {category} for user_id {callback.from_user.id}")
                await callback.message.edit_text(
                    f"Советов в категории '{category}' пока нет.",
                    reply_markup=keyboards.get_tips_categories_keyboard()
                )
                await state.set_state(TipsSelection.choosing_category)
                await callback.answer()
                return
            await callback.message.edit_text(
                f"Советы в категории '{category}':",
                reply_markup=keyboards.get_tips_by_category_keyboard(tips)
            )
            await state.set_state(TipsSelection.choosing_tip)
            await callback.answer()
            return

        # Обрабатываем выбор конкретного совета
        tip_id = int(callback.data.split('_')[1])  # Извлекаем ID из callback_data (tip_<id>)
        user_data = await state.get_data()
        category = user_data.get('category')
        if not category:
            logger.error(f"No category found in state for user_id {callback.from_user.id}")
            await callback.message.edit_text(
                "⚠️ Ошибка: категория не выбрана. Попробуйте снова.",
                reply_markup=keyboards.get_tips_categories_keyboard()
            )
            await state.set_state(TipsSelection.choosing_category)
            await callback.answer()
            return
        with db.get_db() as db_session:
            stmt = text("SELECT tip FROM tips WHERE id = :tip_id")
            tip = db_session.execute(stmt, {'tip_id': tip_id}).first()
            if not tip:
                logger.warning(f"Tip with id {tip_id} not found for user_id {callback.from_user.id}")
                await callback.message.edit_text(
                    "Совет не найден.",
                    reply_markup=keyboards.get_tips_categories_keyboard()
                )
                await state.set_state(TipsSelection.choosing_category)
                await callback.answer()
                return
            await callback.message.edit_text(
                f"💡 {category}: {tip.tip}",
                reply_markup=keyboards.get_tip_content_keyboard(category)
            )
        await state.set_state(TipsSelection.choosing_tip)
        await callback.answer()
    except ValueError as e:
        logger.error(f"Invalid callback data in cq_tip_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Неверный выбор. Попробуйте снова.",
            reply_markup=keyboards.get_tips_categories_keyboard()
        )
        await state.set_state(TipsSelection.choosing_category)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cq_tip_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )
        await state.set_state(TipsSelection.choosing_category)
        await callback.answer()

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
        db.update_goal_progress(callback.from_user.id, activity_type, 1)
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
        activity_type = callback.data.split('_')[2]
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
        day_type = callback.data.split('_')[2]
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
                f"🤔 Размышление: {'✅' if user_plans[callback.from_user.id]['reflection'] else '❌'}",
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
                'reflection': 'Размышление',
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
                return
            except Exception as e:
                logger.error(f"Error saving morning plan for user_id {user_id}: {e}")
                await callback.message.edit_text("⚠️ Ошибка сохранения плана. Попробуйте позже.")
                db_session.rollback()
                await callback.answer()
                return
        plan = user_plans[user_id]
        time_text = f"{plan['time'] // 60}ч" if plan['time'] else "не выбрано"
        activities = [
            f"🏋️ Тренировка: {'✅' if plan['workout'] else '❌'}",
            f"🗣 Язык: {'✅' if plan['english'] else '❌'}",
            f"💻 Программирование: {'✅' if plan['coding'] else '❌'}",
            f"📝 Планирование: {'✅' if plan['planning'] else '❌'}",
            f"🧘 Растяжка: {'✅' if plan['stretching'] else '❌'}",
            f"🤔 Размышление: {'✅' if plan['reflection'] else '❌'}",
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

@dp.callback_query(lambda c: c.data.startswith("habit_answer_"), StateFilter(EveningHabitPoll.answering_habit))
async def handle_habit_answer(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Habit answer received from user_id: {callback.from_user.id}: {callback.data}")
    try:
        user_id = callback.from_user.id
        habit_id, answer = callback.data.split('_')[2:4]
        habit_id = int(habit_id)
        is_completed = answer == 'yes'
        if user_id not in user_habit_answers:
            user_habit_answers[user_id] = {}
        user_habit_answers[user_id][habit_id] = is_completed
        with db.get_db() as db_session:
            stmt = text("SELECT habit_name, id FROM habits WHERE user_id = :uid AND id > :current_id ORDER BY id LIMIT 1")
            next_habit = db_session.execute(stmt, {'uid': user_id, 'current_id': habit_id}).first()
            if next_habit:
                habit_name, next_habit_id = next_habit
                await callback.message.edit_text(
                    f"📋 Выполнили ли вы привычку '{habit_name}' сегодня?",
                    reply_markup=keyboards.get_habit_answer_keyboard(next_habit_id)
                )
                await callback.answer()
            else:
                for h_id, completed in user_habit_answers[user_id].items():
                    db.log_habit_completion(user_id, int(h_id), completed)
                del user_habit_answers[user_id]
                await callback.message.edit_text(
                    "🌙 Все привычки отмечены! Переходим к целям.",
                    reply_markup=None
                )
                # Запуск опроса целей
                stmt = text("SELECT id, goal_name FROM goals WHERE user_id = :uid AND is_completed = false ORDER BY id LIMIT 1")
                first_goal = db_session.execute(stmt, {'uid': user_id}).first()
                if first_goal:
                    user_goal_answers[user_id] = {}
                    goal_id, goal_name = first_goal
                    await state.set_state(EveningGoalPoll.answering_goal)
                    await callback.message.answer(
                        f"🎯 Выполнили ли вы цель '{goal_name}' сегодня?",
                        reply_markup=keyboards.get_goal_answer_keyboard(goal_id)
                    )
                else:
                    await callback.message.answer(
                        "🌙 Нет активных целей. Переходим к вопросам продуктивности.",
                        reply_markup=None
                    )
                    questions = [
                        "Что сегодня мешало быть продуктивным?",
                        "Что дало тебе силу двигаться?",
                        "Что ты сделаешь завтра лучше?"
                    ]
                    user_productivity_answers[user_id] = {}
                    await state.set_state(ProductivityPoll.answering_question)
                    await state.update_data(current_question=0, questions=questions)
                    await callback.message.answer(
                        questions[0],
                        reply_markup=keyboards.get_cancel_keyboard()
                    )
                await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_habit_answer for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.callback_query(lambda c: c.data.startswith("goal_answer_"), StateFilter(EveningGoalPoll.answering_goal))
async def handle_goal_answer(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Goal answer received from user_id: {callback.from_user.id}: {callback.data}")
    try:
        user_id = callback.from_user.id
        goal_id, answer = callback.data.split('_')[2:4]
        goal_id = int(goal_id)
        is_completed = answer == 'yes'
        if user_id not in user_goal_answers:
            user_goal_answers[user_id] = {}
        user_goal_answers[user_id][goal_id] = is_completed
        with db.get_db() as db_session:
            stmt = text("SELECT goal_name, id, goal_type, target_value FROM goals WHERE user_id = :uid AND id > :current_id AND is_completed = false ORDER BY id LIMIT 1")
            next_goal = db_session.execute(stmt, {'uid': user_id, 'current_id': goal_id}).first()
            if is_completed:
                db.log_goal_completion(user_id, goal_id, is_completed)
                db.update_goal_streak(user_id, goal_id)
            if next_goal:
                goal_name, next_goal_id, _, _ = next_goal
                await callback.message.edit_text(
                    f"🎯 Выполнили ли вы цель '{goal_name}' сегодня?",
                    reply_markup=keyboards.get_goal_answer_keyboard(next_goal_id)
                )
                await callback.answer()
            else:
                for g_id, completed in user_goal_answers[user_id].items():
                    db.log_goal_completion(user_id, int(g_id), completed)
                    if completed:
                        db.update_goal_streak(user_id, int(g_id))
                del user_goal_answers[user_id]
                await callback.message.edit_text(
                    "🌙 Все цели отмечены! Переходим к вопросам продуктивности.",
                    reply_markup=None
                )
                questions = [
                    "Что сегодня мешало быть продуктивным?",
                    "Что дало тебе силу двигаться?",
                    "Что ты сделаешь завтра лучше?"
                ]
                user_productivity_answers[user_id] = {}
                await state.set_state(ProductivityPoll.answering_question)
                await state.update_data(current_question=0, questions=questions)
                await callback.message.answer(
                    questions[0],
                    reply_markup=keyboards.get_cancel_keyboard()
                )
                await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_goal_answer for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.")

@dp.message(StateFilter(ProductivityPoll.answering_question))
async def handle_productivity_answer(message: Message, state: FSMContext):
    logger.info(f"Productivity answer received from user_id: {message.from_user.id}: {message.text}")
    try:
        user_id = message.from_user.id
        user_data = await state.get_data()
        current_question_idx = user_data.get('current_question', 0)
        questions = user_data.get('questions', [])
        if user_id not in user_productivity_answers:
            user_productivity_answers[user_id] = {}
        user_productivity_answers[user_id][questions[current_question_idx]] = message.text.strip()
        if current_question_idx + 1 < len(questions):
            await state.update_data(current_question=current_question_idx + 1)
            await message.answer(
                questions[current_question_idx + 1],
                reply_markup=keyboards.get_cancel_keyboard()
            )
        else:
            with db.get_db() as db_session:
                for question, answer in user_productivity_answers[user_id].items():
                    db.save_productivity_answer(user_id, question, answer)
                db_session.commit()
            del user_productivity_answers[user_id]
            await message.answer(
                "🌙 Все вопросы продуктивности отмечены! Спасибо за продуктивный день, командир!",
                reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
            )
            await state.clear()
    except Exception as e:
        logger.error(f"Error in handle_productivity_answer for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

# FSM состояние для справки
class HelpSection(StatesGroup):
    choosing_section = State()

@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    logger.info(f"Received /help from user_id: {message.from_user.id}")
    try:
        await state.clear()
        await message.answer(
            "Выберите раздел справки:",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await state.set_state(HelpSection.choosing_section)
    except Exception as e:
        logger.error(f"Error in /help for user_id {message.from_user.id}: {e}")
        await message.answer(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )

@dp.callback_query(lambda c: c.data == "menu_help", StateFilter("*"))
async def cq_help_menu(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback menu_help from user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text(
            "Выберите раздел справки:",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await state.set_state(HelpSection.choosing_section)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_help for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_general", StateFilter(HelpSection.choosing_section))
async def cq_help_general(callback: CallbackQuery):
    logger.info(f"Received callback help_general from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "📖 <b>Общее</b>\n\n"
            "Данный бот служит помощником в становлении лучшей версией себя. "
            "Я расчитываю на то, что вы будете не просто слепо выполнять опросы и задачи, но и работать над собой, анализировать свои дни и улучшать их.\n"
            "Для начала нужно пройти утренний опрос через /morning, после чего записывать ваши активности и работать над собой. "
            "И помните, что ни один подобный бот не сможет улучшить вас если вы не приложите своих усилий."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_general for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_activities", StateFilter(HelpSection.choosing_section))
async def cq_help_activities(callback: CallbackQuery):
    logger.info(f"Received callback help_activities from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "🏃 <b>Активности</b>\n\n"
            "Есть 2 типа активностей. 1. Главные или предустановленные. Они выбираются в утреннем опросе в качестве запланированных на день.\n"
            "2. Это свободные или те, которые вы сами можете записать. Они делятся на полезные и не полезные.\n"
            "Не полезные активности это игры, соцсети. В общем всё то, что не приносит явной пользы и выполняется в гаджетах.\n"
            "Полезные же это наоборот те, которые приносят пользу. То же чтение или работа могут быть в гаджетах но они явно полезные."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_activities for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_goals", StateFilter(HelpSection.choosing_section))
async def cq_help_goals(callback: CallbackQuery):
    logger.info(f"Received callback help_goals from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "🎯 <b>Цели</b>\n\n"
            "Вы можете планировать 2 типа целей в этом боте: ежедневные и еженедельные.\n"
            "Ежедневные цели это те, которые вы выполняете каждый день. Пример: пить 2л воды.\n"
            "Еженедельные, в свою очередь, это те, которые вы выполняете каждую неделю. Пример: тренироваться 3 раза."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_goals for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_tips", StateFilter(HelpSection.choosing_section))
async def cq_help_tips(callback: CallbackQuery):
    logger.info(f"Received callback help_tips from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "💡 <b>Советы</b>\n\n"
            "Все советы, изложенные здесь, это часть моего опыта. "
            "Если реально хотите изменить себя , вы должны применить их в жизни, а не просто прочесть и забыть."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_tips for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_achievements", StateFilter(HelpSection.choosing_section))
async def cq_help_achievements(callback: CallbackQuery):
    logger.info(f"Received callback help_achievements from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "🏆 <b>Достижения</b>\n\n"
            "Вы можете добавлять сюда свои личные достижения на вашем пути и гордиться ими."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_achievements for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_habits", StateFilter(HelpSection.choosing_section))
async def cq_help_habits(callback: CallbackQuery):
    logger.info(f"Received callback help_habits from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "📋 <b>Привычки</b>\n\n"
            "Привычки - это неотъемлемая часть жизни всех людей. "
            "Даже такая привычка как терпеть очень важна в жизни, так как в каждой тренировке пресса или ног надо терпеть."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_habits for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "help_stats", StateFilter(HelpSection.choosing_section))
async def cq_help_stats(callback: CallbackQuery):
    logger.info(f"Received callback help_stats from user_id: {callback.from_user.id}")
    try:
        help_text = (
            "📊 <b>Статистика</b>\n\n"
            "Тут вы можете посмотреть как диаграммы вашего экранного времени по расчетам не полезных активностей, так и чек-листы. "
            "Анализируйте время экрана, продуктивность, полезное время."
        )
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help_stats for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_help_menu_keyboard()
        )
        await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_back", StateFilter(HelpSection.choosing_section))
async def cq_back_from_help(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Received callback menu_back from help for user_id: {callback.from_user.id}")
    try:
        await state.clear()
        await callback.message.edit_text(
            "Выберите действие:",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in back_from_help for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Ошибка. Попробуйте позже.",
            reply_markup=keyboards.get_main_menu_keyboard(include_settings=True)
        )
        await callback.answer()

# API endpoints
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
            
            stmt = text("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = :uid AND activity_date = :today")
            today_screen_activities = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            screen_breakdown = {row._asdict()['activity_name']: row._asdict()['duration_minutes'] for row in today_screen_activities}
            total_screen_minutes_today = sum(screen_breakdown.values())
            
            stmt = text("SELECT activity_name, duration_minutes FROM productive_activities WHERE user_id = :uid AND activity_date = :today")
            today_productive_activities = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            productive_breakdown = {row._asdict()['activity_name']: row._asdict()['duration_minutes'] for row in today_productive_activities}
            total_productive_minutes_today = sum(productive_breakdown.values())
            
            stmt = text("""
                SELECT g.goal_name, gc.completed
                FROM goal_completions gc
                JOIN goals g ON gc.goal_id = g.id
                WHERE gc.user_id = :uid AND gc.completion_date = :today
            """)
            today_goals = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            goals = {row._asdict()['goal_name']: row._asdict()['completed'] for row in today_goals}
            
            stmt = text("""
                SELECT h.habit_name, hc.completed
                FROM habit_completions hc
                JOIN habits h ON hc.habit_id = h.id
                WHERE hc.user_id = :uid AND hc.completion_date = :today
            """)
            today_habits = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            habits = {row._asdict()['habit_name']: row._asdict()['completed'] for row in today_habits}
            
            stmt = text("SELECT question, answer FROM productivity_questions WHERE user_id = :uid AND answer_date = :today")
            productivity_questions = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
            productivity_answers = {row._asdict()['question']: row._asdict()['answer'] for row in productivity_questions}
            
            stmt = text("SELECT * FROM goals WHERE user_id = :uid AND is_completed = false")
            goals_data = db_session.execute(stmt, {'uid': user_id}).fetchall()
            goals_response = [
                Goal(
                    id=goal.id,
                    goal_name=goal.goal_name,
                    goal_type=goal.goal_type,
                    target_value=goal.target_value,
                    current_value=goal.current_value,
                    start_date=goal.start_date.isoformat(),
                    end_date=goal.end_date.isoformat(),
                    is_completed=goal.is_completed,
                    streak=goal.streak
                ) for goal in goals_data
            ]
            
            stmt = text("SELECT habit_name, id FROM habits WHERE user_id = :uid")
            user_habits = db_session.execute(stmt, {'uid': user_id}).fetchall()
            habits_data = [{'id': habit.id, 'name': habit.habit_name} for habit in user_habits]
            
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
                walk_planned=today_main_stats_dict['walk_planned'],
                walk_done=today_main_stats_dict['walk_done'],
                morning_poll_completed=today_main_stats_dict['morning_poll_completed'],
                is_rest_day=today_main_stats_dict['is_rest_day'],
                habits=habits,
                goals=goals,  # Добавлено
                productivity_questions=productivity_answers
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
                    walk_done=day_stats._asdict()['walk_done'],
                    is_rest_day=day_stats._asdict()['is_rest_day']
                )
                for day_stats in history_main_stats
            ]
            
            db_session.commit()
            
            return UserStatsResponse(user_id=user_id, today=today_data, history=history_data, goals=goals_response, habits=habits_data)
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
                        f"🤔 Размышление: {get_status(stats['reflection_planned'], stats['reflection_done'])}",
                        f"🚶 Прогулка: {get_status(stats['walk_planned'], stats['walk_done'])}",
                        "\n🎯 Ваши цели:"
                    ])
                    goal_stmt = text("""
                        SELECT g.goal_name, gc.completed
                        FROM goal_completions gc
                        JOIN goals g ON gc.goal_id = g.id
                        WHERE gc.user_id = :uid AND gc.completion_date = :today
                    """)
                    goals = db_session.execute(goal_stmt, {'uid': user_id, 'today': date.today()}).fetchall()
                    if goals:
                        for goal in goals:
                            status = "✅ Выполнено!" if goal.completed else "❌ Пропущено"
                            summary_lines.append(f"• {goal.goal_name}: {status}")
                    else:
                        summary_lines.append("• Нет данных о целях за сегодня.")
                    summary_lines.append("\n📋 Ваши привычки:")
                    habit_stmt = text("""
                        SELECT h.habit_name, hc.completed
                        FROM habit_completions hc
                        JOIN habits h ON hc.habit_id = h.id
                        WHERE hc.user_id = :uid AND hc.completion_date = :today
                    """)
                    habits = db_session.execute(habit_stmt, {'uid': user_id, 'today': date.today()}).fetchall()
                    if habits:
                        for habit in habits:
                            status = "✅ Выполнено!" if habit.completed else "❌ Пропущено"
                            summary_lines.append(f"• {habit.habit_name}: {status}")
                    else:
                        summary_lines.append("• Нет данных о привычках за сегодня.")
                    summary_lines.extend([
                        "\n🤔 Вопросы для размышления:",
                        "1. Что сегодня мешало быть продуктивным?",
                        "2. Что дало тебе силу двигаться?",
                        "3. Что ты сделаешь завтра лучше?"
                    ])
                    await bot.send_message(user_id, "\n".join(summary_lines))
                    db.check_and_award_achievements(user_id)
                    habit_stmt = text("SELECT habit_name, id FROM habits WHERE user_id = :uid ORDER BY id LIMIT 1")
                    first_habit = db_session.execute(habit_stmt, {'uid': user_id}).first()
                    if first_habit:
                        user_habit_answers[user_id] = {}
                        habit_name, habit_id = first_habit
                        dp.storage.set_state(chat_id=user_id, user_id=user_id, state=EveningHabitPoll.answering_habit)
                        await bot.send_message(
                            user_id,
                            f"📋 Выполнили ли вы привычку '{habit_name}' сегодня?",
                            reply_markup=keyboards.get_habit_answer_keyboard(habit_id)
                        )
                    else:
                        # Если привычек нет, переходим к опросу целей
                        goal_stmt = text("SELECT id, goal_name FROM goals WHERE user_id = :uid AND is_completed = false ORDER BY id LIMIT 1")
                        first_goal = db_session.execute(goal_stmt, {'uid': user_id}).first()
                        if first_goal:
                            user_goal_answers[user_id] = {}
                            goal_id, goal_name = first_goal
                            dp.storage.set_state(chat_id=user_id, user_id=user_id, state=EveningGoalPoll.answering_goal)
                            await bot.send_message(
                                user_id,
                                f"🎯 Выполнили ли вы цель '{goal_name}' сегодня?",
                                reply_markup=keyboards.get_goal_answer_keyboard(goal_id)
                            )
                        else:
                            # Если целей нет, переходим к вопросам продуктивности
                            questions = [
                                "Что сегодня мешало быть продуктивным?",
                                "Что дало тебе силу двигаться?",
                                "Что ты сделаешь завтра лучше?"
                            ]
                            user_productivity_answers[user_id] = {}
                            # Создаём объект FSMContext для текущего пользователя
                            state = FSMContext(
                                storage=dp.storage,
                                key=types.StorageKey(
                                    bot_id=bot.id,
                                    chat_id=user_id,
                                    user_id=user_id
                                )
                            )
                            await state.set_state(ProductivityPoll.answering_question)
                            await state.update_data(current_question=0, questions=questions)
                            await bot.send_message(
                                user_id,
                                questions[0],
                                reply_markup=keyboards.get_cancel_keyboard()
                            )
                    logger.info(f"Sent evening summary to user_id: {user_id}")
                except TelegramAPIError as e:
                    logger.error(f"Failed to send evening summary to user_id {user_id}: {e}")
            db_session.commit()
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Error in evening summary CRON: {e}")
        db_session.rollback()
        return {"status": "error", "message": str(e)}

# Webhook setup
async def on_startup():
    logger.info("Starting up bot...")
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"Webhook set to {WEBHOOK_URL}")
        else:
            logger.info("Webhook already set correctly")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

async def on_shutdown():
    logger.info("Shutting down bot...")
    # Пропускаем удаление вебхука для работы 24/7
    await bot.session.close()

# FastAPI webhook endpoint
@fastapi_app.post(WEBHOOK_PATH)
async def handle_webhook_update(request: Request):
    try:
        update = types.Update(**await request.json())
        await dp.feed_update(bot=bot, update=update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        return {"status": "error", "message": str(e)}

# Monitor system resources
def monitor_resources():
    while True:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        logger.debug(f"CPU Usage: {cpu_percent}% | Memory Usage: {memory_percent}%")
        if cpu_percent > 80 or memory_percent > 80:
            logger.warning(f"High resource usage detected: CPU {cpu_percent}%, Memory {memory_percent}%")
        time.sleep(60)

# Start resource monitoring in a separate thread
resource_monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
resource_monitor_thread.start()

# Main entry point
if __name__ == "__main__":
    import uvicorn
    fastapi_app.add_event_handler("startup", on_startup)
    fastapi_app.add_event_handler("shutdown", on_shutdown)
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))