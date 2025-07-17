import os
import sys
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError

# Временный обход для импорта keyboards и db
sys.path.append(os.path.dirname(__file__))

import db
import keyboards

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('aiogram').setLevel(logging.DEBUG)

# Конфигурация
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://your-frontend-render-url")

# Инициализация
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

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
    choosing_days_per_week = State()

class AddHabit(StatesGroup):
    choosing_habit_name = State()

class EveningHabitPoll(StatesGroup):
    answering_habit = State()

class EveningGoalPoll(StatesGroup):
    answering_goal = State()

class ProductivityPoll(StatesGroup):
    answering_question = State()

class TipsSelection(StatesGroup):
    choosing_category = State()
    choosing_tip = State()

# Глобальное хранилище
user_plans: Dict[int, Dict[str, Optional[int]]] = {}
user_habit_answers: Dict[int, Dict[str, bool]] = {}
user_goal_answers: Dict[int, Dict[str, bool]] = {}
user_productivity_answers: Dict[int, Dict[str, str]] = {}

# Логирование ошибок
def log_uncaught_exceptions(exctype, value, tb):
    logger.error("Uncaught exception", exc_info=(exctype, value, tb))

sys.excepthook = log_uncaught_exceptions

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
            from datetime import datetime
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
            from datetime import datetime
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
            stmt = text("SELECT * FROM goals WHERE user_id = :uid AND is_completed = false ORDER BY start_date")
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
                streak = db.get_goal_streak(callback.from_user.id, goal.id, goal.goal_type)
                streak_text = f" (🔥 {streak} {'дней' if goal.goal_type == 'daily' else 'недель'} подряд)" if streak > 0 else ""
                goal_lines.append(f"• {goal.goal_name} ({goal.goal_type}): {goal.current_value}/{goal.target_value} ({progress:.1f}%){streak_text}")
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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.message(StateFilter(SetGoal.choosing_goal_name))
async def goal_name_chosen(message: Message, state: FSMContext):
    logger.info(f"Goal name chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        await state.update_data(goal_name=message.text.strip())
        user_data = await state.get_data()
        goal_type = user_data.get('goal_type')
        if goal_type == 'weekly':
            await message.answer("Сколько дней в неделю вы хотите выполнять эту цель? (Введите число от 1 до 7):", reply_markup=keyboards.get_cancel_keyboard())
            await state.set_state(SetGoal.choosing_days_per_week)
        else:
            await message.answer("Введите целевое значение (например, 100 для 100г белка):", reply_markup=keyboards.get_cancel_keyboard())
            await state.set_state(SetGoal.choosing_target_value)
    except Exception as e:
        logger.error(f"Error in goal_name_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(StateFilter(SetGoal.choosing_days_per_week))
async def goal_days_per_week_chosen(message: Message, state: FSMContext):
    logger.info(f"Goal days per week chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        if not message.text.isdigit() or not 1 <= int(message.text) <= 7:
            await message.answer("Ошибка. Введите число от 1 до 7.", reply_markup=keyboards.get_cancel_keyboard())
            return
        await state.update_data(days_per_week=int(message.text))
        await message.answer("Введите целевое значение (например, 5 для 5 дней в неделю):", reply_markup=keyboards.get_cancel_keyboard())
        await state.set_state(SetGoal.choosing_target_value)
    except Exception as e:
        logger.error(f"Error in goal_days_per_week_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(StateFilter(SetGoal.choosing_target_value))
async def goal_target_chosen(message: Message, state: FSMContext):
    logger.info(f"Goal target chosen by user_id: {message.from_user.id}: {message.text}")
    try:
        if not message.text.isdigit():
            await message.answer("Ошибка. Введите число.", reply_markup=keyboards.get_cancel_keyboard())
            return
        await state.update_data(target_value=int(message.text))
        await message.answer("Выберите длительность цели:", reply_markup=keyboards.get_goal_duration_keyboard())
        await state.set_state(SetGoal.choosing_duration)
    except Exception as e:
        logger.error(f"Error in goal_target_chosen for user_id {message.from_user.id}: {e}")
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(lambda c: c.data.startswith("goal_duration_"), StateFilter(SetGoal.choosing_duration))
async def goal_duration_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Goal duration chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        duration = callback.data.split('_')[2]
        user_data = await state.get_data()
        goal_type = user_data.get('goal_type')
        goal_name = user_data.get('goal_name')
        target_value = user_data.get('target_value')
        days_per_week = user_data.get('days_per_week', None)
        start_date = date.today()
        end_date = start_date + timedelta(days=7 if duration == 'weekly' else 30)
        db.add_goal(
            user_id=callback.from_user.id,
            goal_name=goal_name,
            goal_type=goal_type,
            target_value=target_value,
            current_value=0,
            start_date=start_date,
            end_date=end_date,
            days_per_week=days_per_week
        )
        await callback.message.edit_text(
            f"🎯 Цель '{goal_name}' ({goal_type}) добавлена! Целевое значение: {target_value}, до {end_date.strftime('%d.%m.%Y')}",
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
                habit_lines.append(f"• {habit['name']} ({habit['progress']:.1f}%)")
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

@dp.callback_query(lambda c: c.data.startswith("tip_"), StateFilter(TipsSelection.choosing_tip))
async def cq_tip_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Tip chosen by user_id: {callback.from_user.id}: {callback.data}")
    try:
        tip_id = int(callback.data.split('_')[1])
        user_data = await state.get_data()
        category = user_data.get('category')
        with db.get_db() as db_session:
            stmt = text("SELECT tip FROM tips WHERE id = :tip_id")
            tip = db_session.execute(stmt, {'tip_id': tip_id}).first()
            if not tip:
                await callback.message.edit_text(
                    "Совет не найден.",
                    reply_markup=keyboards.get_tips_categories_keyboard()
                )
                await callback.answer()
                return
            await callback.message.edit_text(
                f"💡 {category}: {tip.tip}",
                reply_markup=keyboards.get_tip_content_keyboard(category)
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in tip_chosen for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "menu_mark_done")
async def cq_mark_done_menu(callback: CallbackQuery):
    logger.info(f"Received callback menu_mark_done from user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Какое достижение отметить?", reply_markup=keyboards.get_mark_done_keyboard(callback.from_user.id))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu_mark_done for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "confirm_clear_no")
async def cq_cancel_clear(callback: CallbackQuery):
    logger.info(f"Canceling clear data for user_id: {callback.from_user.id}")
    try:
        await callback.message.edit_text("Операция отменена. Возвращаю в главное меню.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_clear for user_id {callback.from_user.id}: {e}")
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
                stmt = text("SELECT goal_name, id FROM goals WHERE user_id = :uid AND is_completed = false ORDER BY id LIMIT 1")
                first_goal = db_session.execute(stmt, {'uid': user_id}).first()
                if first_goal:
                    user_goal_answers[user_id] = {}
                    goal_name, goal_id = first_goal
                    await state.set_state(EveningGoalPoll.answering_goal)
                    await callback.message.answer(
                        f"🎯 Выполнили ли вы цель '{goal_name}' сегодня?",
                        reply_markup=keyboards.get_goal_answer_keyboard(goal_id)
                    )
                else:
                    await callback.message.answer(
                        "🌙 Все цели отмечены! Переходим к вопросам продуктивности.",
                        reply_markup=None
                    )
                    # Запуск опроса продуктивности
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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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
            db.log_goal_completion(user_id, goal_id, is_completed)
            stmt = text("SELECT goal_name, id FROM goals WHERE user_id = :uid AND id > :current_id AND is_completed = false ORDER BY id LIMIT 1")
            next_goal = db_session.execute(stmt, {'uid': user_id, 'current_id': goal_id}).first()
            if next_goal:
                goal_name, next_goal_id = next_goal
                await callback.message.edit_text(
                    f"🎯 Выполнили ли вы цель '{goal_name}' сегодня?",
                    reply_markup=keyboards.get_goal_answer_keyboard(next_goal_id)
                )
                await callback.answer()
            else:
                for g_id, completed in user_goal_answers[user_id].items():
                    db.log_goal_completion(user_id, int(g_id), completed)
                del user_goal_answers[user_id]
                await callback.message.edit_text(
                    "🌙 Все цели отмечены! Переходим к вопросам продуктивности.",
                    reply_markup=None
                )
                # Запуск опроса продуктивности
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
        await callback.message.edit_text("⚠️ Ошибка. Попробуйте позже.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

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