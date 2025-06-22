import asyncio
import logging
import os
import sqlite3
from datetime import date, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Импортируем нашу логику из папки bot/
import bot.db as db
from bot.handlers import router as regime_handlers_router
from bot.scheduler import setup_scheduler

# --- 1. НАСТРОЙКА И КОНФИГУРАЦИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL")
RENDER_URL = os.getenv("RENDER_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"
# Порт, который будет слушать Render
PORT = int(os.getenv("PORT", 10000))

# --- 2. ИНИЦИАЛИЗАЦИЯ БОТА И FastAPI ---
bot_instance = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(regime_handlers_router)

# Создаем FastAPI приложение
fastapi_app = FastAPI()

# --- 3. ЛОГИКА БЭКЕНДА (API) ---
# Настраиваем CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели Pydantic
class HistoryDayStats(BaseModel):
    date: str; screen_time_goal: int; screen_time_actual: int; workout_done: int
    english_done: int; coding_done: int; planning_done: int
    stretching_done: int; reflection_done: int

class TodayStats(BaseModel):
    screen_time_goal: Optional[int] = 0; screen_time_actual: int = 0
    screen_time_breakdown: Dict[str, int] = {}
    workout_planned: int; workout_done: int; english_planned: int; english_done: int
    coding_planned: int; coding_done: int; planning_planned: int; planning_done: int
    stretching_planned: int; stretching_done: int; reflection_planned: int; reflection_done: int

class UserStatsResponse(BaseModel):
    user_id: int; today: TodayStats; history: List[HistoryDayStats]

# Функция для подключения к БД
def get_db_connection():
    conn = sqlite3.connect('./database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Эндпоинт API
@fastapi_app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
def read_user_stats(user_id: int):
    # (Здесь ваша полная рабочая логика для эндпоинта)
    conn = get_db_connection()
    try:
        today_iso = date.today().isoformat()
        today_main_stats = conn.execute("SELECT * FROM daily_stats WHERE user_id = ? AND stat_date = ?", (user_id, today_iso)).fetchone()
        if not today_main_stats: raise HTTPException(status_code=404, detail="План на сегодня не найден.")
        
        today_activities = conn.execute("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = ? AND activity_date = ?", (user_id, today_iso)).fetchall()
        breakdown = {row['activity_name']: row['duration_minutes'] for row in today_activities}
        total_minutes_today = sum(breakdown.values())
        
        # Преобразуем sqlite3.Row в dict перед передачей в Pydantic модель
        today_data = TodayStats(**dict(today_main_stats), screen_time_actual=total_minutes_today, screen_time_breakdown=breakdown)

        history_data = []
        seven_days_ago = date.today() - timedelta(days=7)
        history_main_stats = conn.execute("SELECT * FROM daily_stats WHERE user_id = ? AND stat_date >= ? AND stat_date < ? ORDER BY stat_date DESC", (user_id, seven_days_ago.isoformat(), today_iso)).fetchall()
        history_screen_time = conn.execute("SELECT activity_date, SUM(duration_minutes) as total_minutes FROM screen_activities WHERE user_id = ? AND activity_date >= ? AND activity_date < ? GROUP BY activity_date", (user_id, seven_days_ago.isoformat(), today_iso)).fetchall()
        screen_time_map = {row['activity_date']: row['total_minutes'] for row in history_screen_time}

        for day_stats in history_main_stats:
            history_data.append(HistoryDayStats(**dict(day_stats), screen_time_actual=screen_time_map.get(day_stats['stat_date'], 0)))
        
        return UserStatsResponse(user_id=user_id, today=today_data, history=history_data)
    finally:
        conn.close()

# Добавляем маршрут /ping для UptimeRobot в FastAPI
@fastapi_app.get("/ping")
async def handle_ping():
    logger.info("Ping request received.")
    return {"status": "ok", "message": "pong"}


# --- 4. НАСТРОЙКА ВЕБХУКА И ЗАПУСК ---

@fastapi_app.on_event("startup")
async def on_startup():
    """Действия при старте FastAPI: инициализация БД, установка вебхука, запуск планировщика."""
    logger.info("FastAPI startup: Initializing database...")
    db.init_db()
    # Устанавливаем реальный URL фронтенда
    import bot.handlers
    bot.handlers.WEBAPP_URL = FRONTEND_URL
    logger.info(f"FastAPI startup: Setting webhook to {WEBHOOK_URL}")
    await bot_instance.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info("FastAPI startup: Starting scheduler...")
    setup_scheduler(bot_instance)

@fastapi_app.on_event("shutdown")
async def on_shutdown():
    """Действия при остановке: удаление вебхука."""
    logger.warning("FastAPI shutdown: Deleting webhook...")
    await bot_instance.delete_webhook()

# Главный обработчик вебхукаs
@fastapi_app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    """Принимает апдейты от Telegram и передает их в диспетчер aiogram."""
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot_instance, update=telegram_update)