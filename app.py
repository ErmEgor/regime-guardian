import os
import sys
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

# Временный обход для импорта keyboards
sys.path.append(os.path.dirname(__file__))

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, WebAppInfo
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.sql import text

import db
import keyboards

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('aiogram').setLevel(logging.DEBUG)
logging.getLogger('fastapi').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

load_dotenv()

# --- Конфигурация ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
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
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели Pydantic для API ---
class HistoryDayStats(BaseModel):
    date: str
    screen_time_goal: int
    screen_time_actual: int
    workout_done: int
    english_done: int
    coding_done: int
    planning_done: int
    stretching_done: int
    reflection_done: int

class TodayStats(BaseModel):
    screen_time_goal: Optional[int] = 0
    screen_time_actual: int = 0
    screen_time_breakdown: Dict[str, int] = {}
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

class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]

# --- FSM для логирования активности ---
class LogActivity(StatesGroup):
    choosing_activity_name = State()
    choosing_duration = State()

# --- Глобальное хранилище планов ---
user_plans = {}

# --- Обработчики Telegram ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        "⚔️ Добро пожаловать, командир!\n\n"
        "Используй /menu, чтобы отдать приказ."
    )

@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer("Меню настроек:", reply_markup=keyboards.get_settings_keyboard("Asia/Almaty"))

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data == "menu_settings")
async def cq_menu_settings(callback: CallbackQuery):
    await callback.message.edit_text("Меню настроек:", reply_markup=keyboards.get_settings_keyboard("Asia/Almaty"))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_mark_done")
async def cq_mark_done_menu(callback: CallbackQuery):
    await callback.message.edit_text("Какое достижение отметить?", reply_markup=keyboards.get_mark_done_keyboard())
    await callback.answer()

@dp.message(Command("stats"))
@dp.callback_query(lambda c: c.data == "menu_stats")
async def show_stats(update: Message | CallbackQuery):
    user_id = update.from_user.id if isinstance(update, Message) else update.from_user.id
    webapp_url = f"{FRONTEND_URL}?user_id={user_id}"
    message_to_answer = update if isinstance(update, Message) else update.message
    await message_to_answer.answer(
        "Аналитические данные готовы, командир. Панель доступна по кнопке ниже.",
        reply_markup=keyboards.get_stats_keyboard(webapp_url)
    )
    if isinstance(update, CallbackQuery):
        await update.answer()

@dp.callback_query(lambda c: c.data == "menu_back")
async def cq_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выберите действие:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("done_"))
async def cq_mark_activity_done(callback: CallbackQuery):
    activity_type = callback.data.split('_')[1]
    db.mark_activity_done(callback.from_user.id, activity_type)
    await callback.answer(f"✅ {activity_type.capitalize()} засчитано!", show_alert=True)

@dp.message(Command("clear_stats"))
@dp.callback_query(lambda c: c.data == "menu_clear_stats")
async def cmd_clear_stats(update: Message | CallbackQuery):
    text = "Вы уверены, что хотите удалить ВСЕ свои данные безвозвратно? Это действие необратимо."
    markup = keyboards.get_confirm_clear_keyboard()
    message_to_edit = update if isinstance(update, Message) else update.message
    await message_to_edit.answer(text, reply_markup=markup)
    if isinstance(update, CallbackQuery):
        await update.answer()

@dp.callback_query(lambda c: c.data == "confirm_clear_yes")
async def cq_confirm_clear(callback: CallbackQuery):
    db.clear_user_data(callback.from_user.id)
    await callback.message.edit_text("⚔️ Все ваши данные были стерты. Начнем с чистого листа. /start")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_clear_no")
async def cq_cancel_clear(callback: CallbackQuery):
    await callback.message.edit_text("Операция отменена. Возвращаю в главное меню.", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "fsm_cancel", StateFilter("*"))
async def cq_cancel_fsm(callback: CallbackQuery, state: FSMContext):
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

@dp.message(Command("log"))
@dp.callback_query(lambda c: c.data == "menu_log_activity")
async def start_log_activity(update: Message | CallbackQuery, state: FSMContext):
    message_to_use = update if isinstance(update, Message) else update.message
    await message_to_use.answer("Какую активность вы хотите записать? (например: YouTube, Соцсети)", reply_markup=keyboards.get_cancel_keyboard())
    await state.set_state(LogActivity.choosing_activity_name)
    if isinstance(update, CallbackQuery):
        await update.answer()

@dp.message(StateFilter(LogActivity.choosing_activity_name))
async def activity_name_chosen(message: Message, state: FSMContext):
    await state.update_data(activity_name=message.text)
    await message.answer("Сколько минут это заняло? Введите только число.", reply_markup=keyboards.get_cancel_keyboard())
    await state.set_state(LogActivity.choosing_duration)

@dp.message(StateFilter(LogActivity.choosing_duration))
async def duration_chosen(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Ошибка. Пожалуйста, введите число (количество минут).", reply_markup=keyboards.get_cancel_keyboard())
        return
    user_data = await state.get_data()
    activity_name = user_data.get('activity_name', 'Неизвестная активность')
    duration_minutes = int(message.text)
    db.log_custom_activity(message.from_user.id, activity_name, duration_minutes)
    await message.answer(f"Записано: '{activity_name}' - {duration_minutes} мин.")
    await state.clear()
    await message.answer("Главное меню:", reply_markup=keyboards.get_main_menu_keyboard(include_settings=True))

@dp.callback_query(lambda c: c.data.startswith("plan_"))
async def handle_morning_plan(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split('_')
    if user_id not in user_plans:
        user_plans[user_id] = {'time': None, 'workout': 0, 'english': 0, 'coding': 0, 'planning': 0, 'stretching': 0, 'reflection': 0}

    if action[1] == 'time':
        user_plans[user_id]['time'] = int(action[2])
        await callback.answer(f"Лимит времени: < {action[2]}ч")
    elif action[1] == 'toggle':
        habit = action[2]
        user_plans[user_id][habit] = 1 - user_plans[user_id][habit]
        status_text = "в планах" if user_plans[user_id][habit] == 1 else "не в планах"
        await callback.answer(f"{habit.capitalize()} {status_text}")
    elif action[1] == 'done':
        plan = user_plans.get(user_id)
        if plan is None or plan['time'] is None:
            await callback.answer("Пожалуйста, выберите лимит времени.", show_alert=True)
            return
        db.save_morning_plan(
            user_id, plan['time'], plan['workout'], plan['english'], plan['coding'],
            plan['planning'], plan['stretching'], plan['reflection']
        )
        del user_plans[user_id]
        await callback.message.edit_text("⚔️ План на день сохранён. Продуктивного дня, командир!")
    await callback.answer()

@dp.message(Command("morning"))
async def cmd_morning_test(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in user_plans:
        del user_plans[user_id]
    await message.answer("☀️ Составьте план на сегодня:", reply_markup=keyboards.get_morning_poll_keyboard())

# --- API для веб-приложения ---
@fastapi_app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
def read_user_stats(user_id: int):
    with db.get_db() as db_session:
        today = date.today()
        today_iso = today.isoformat()
        stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
        today_main_stats = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).first()
        if not today_main_stats:
            raise HTTPException(status_code=404, detail="План на сегодня не найден.")
        stmt = text("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = :uid AND activity_date = :today")
        today_activities = db_session.execute(stmt, {'uid': user_id, 'today': today_iso}).fetchall()
        breakdown = {row['activity_name']: row['duration_minutes'] for row in today_activities}
        total_minutes_today = sum(breakdown.values())
        today_data = TodayStats(**today_main_stats._asdict(), screen_time_actual=total_minutes_today, screen_time_breakdown=breakdown)
        seven_days_ago = today - timedelta(days=7)
        stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date >= :start AND stat_date < :today ORDER BY stat_date DESC")
        history_main_stats = db_session.execute(stmt, {'uid': user_id, 'start': seven_days_ago.isoformat(), 'today': today_iso}).fetchall()
        stmt = text("SELECT activity_date, SUM(duration_minutes) as total_minutes FROM screen_activities WHERE user_id = :uid AND activity_date >= :start AND activity_date < :today GROUP BY activity_date")
        history_screen_time = db_session.execute(stmt, {'uid': user_id, 'start': seven_days_ago.isoformat(), 'today': today_iso}).fetchall()
        screen_time_map = {row['activity_date']: row['total_minutes'] for row in history_screen_time}
        history_data = [
            HistoryDayStats(**day_stats._asdict(), screen_time_actual=screen_time_map.get(day_stats['stat_date'], 0))
            for day_stats in history_main_stats
        ]
        return UserStatsResponse(user_id=user_id, today=today_data, history=history_data)

@fastapi_app.get("/ping")
async def handle_ping():
    return {"status": "ok"}

# --- CRON эндпоинты для утреннего опроса и вечерней сводки ---
@fastapi_app.post("/api/morning/cron")
async def morning_poll_cron():
    with db.get_db() as db_session:
        stmt = text("SELECT user_id FROM users")
        users = db_session.execute(stmt).fetchall()
        for user in users:
            try:
                await bot.send_message(
                    user['user_id'],
                    "☀️ Доброе утро, командир! Пора составить план боя на сегодня:",
                    reply_markup=keyboards.get_morning_poll_keyboard()
                )
            except Exception as e:
                logger.error(f"Failed to send morning poll to {user['user_id']}: {e}")
    return {"status": "sent"}

@fastapi_app.post("/api/evening/cron")
async def evening_summary_cron():
    with db.get_db() as db_session:
        stmt = text("SELECT user_id FROM daily_stats WHERE stat_date = :today")
        users = db_session.execute(stmt, {'today': date.today()}).fetchall()
        for user in users:
            try:
                stats = db.get_today_stats_for_user(user['user_id'])
                if not stats:
                    continue
                time_actual = db.get_today_screen_time(user['user_id'])
                time_goal = stats['screen_time_goal']
                time_status = "✅ В рамках!" if time_actual / 60 <= time_goal else "❌ Перелимит"
                summary_lines = [
                    "🌙 Вечерний рапорт, командир:\n",
                    f"📱 Экранное время: ~{round(time_actual / 60, 1)}ч из <{time_goal}ч ({time_status})\n"
                ]
                def get_status(planned, done):
                    return "не планировалась" if not planned else "✅ Выполнена" if done else "❌ Пропущена"
                summary_lines.extend([
                    f"⚔️ Тренировка: {get_status(stats['workout_planned'], stats['workout_done'])}",
                    f"🎓 Английский: {get_status(stats['english_planned'], stats['english_done'])}",
                    f"💻 Кодинг: {get_status(stats['coding_planned'], stats['coding_done'])}",
                    f"📝 План: {get_status(stats['planning_planned'], stats['planning_done'])}",
                    f"🧘 Растяжка: {get_status(stats['stretching_planned'], stats['stretching_done'])}",
                    f"🤔 Размышления: {get_status(stats['reflection_planned'], stats['reflection_done'])}",
                    "\nСпокойной ночи. Завтра — новая битва."
                ])
                await bot.send_message(user['user_id'], "\n".join(summary_lines))
            except Exception as e:
                logger.error(f"Failed to send evening summary to {user['user_id']}: {e}")
    return {"status": "sent"}

# --- Вебхук и запуск ---
@fastapi_app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    return response

@fastapi_app.on_event("startup")
async def on_startup():
    logger.info(f"Setting webhook to {WEBHOOK_URL}")
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True, max_connections=40)
    db.init_db()

@fastapi_app.on_event("shutdown")
async def on_shutdown():
    logger.warning("Deleting webhook...")
    await bot.delete_webhook()

@fastapi_app.post(f"/webhook/{BOT_TOKEN}")
async def bot_webhook(update: dict):
    logger.info(f"Received update: {update}")
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:fastapi_app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10
    )