import asyncio
import logging
import os
import sqlite3
import threading
from datetime import date, timedelta
from typing import Dict, List, Optional

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
WEBAPP_PORT = int(os.getenv("PORT", 10000))

# --- 2. ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПЕТЧЕРА ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(regime_handlers_router)

# --- 3. ЛОГИКА FastAPI БЭКЕНДА ---
fastapi_app = FastAPI()
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ВАШИ Pydantic МОДЕЛИ И ЛОГИКА API ---
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
    workout_planned: int; workout_done: int
    english_planned: int; english_done: int
    coding_planned: int; coding_done: int
    planning_planned: int; planning_done: int
    stretching_planned: int; stretching_done: int
    reflection_planned: int; reflection_done: int

class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]

def get_db_connection():
    conn = sqlite3.connect('./database.db')
    conn.row_factory = sqlite3.Row
    return conn

@fastapi_app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
def read_user_stats(user_id: int):
    # (Здесь ваша полная рабочая логика для эндпоинта)
    # Я вставлю её для полноты
    conn = get_db_connection()
    try:
        today_iso = date.today().isoformat()
        today_main_stats = conn.execute("SELECT * FROM daily_stats WHERE user_id = ? AND stat_date = ?", (user_id, today_iso)).fetchone()
        if not today_main_stats: raise HTTPException(status_code=404, detail="План на сегодня не найден.")
        
        today_activities = conn.execute("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = ? AND activity_date = ?", (user_id, today_iso)).fetchall()
        breakdown = {row['activity_name']: row['duration_minutes'] for row in today_activities}
        total_minutes_today = sum(breakdown.values())

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


# --- 4. НАСТРОЙКА И ЗАПУСК ВЕБ-СЕРВЕРА AIOHTTP (ДЛЯ ВЕБХУКА) ---
async def on_startup(bot_instance: Bot):
    logger.info("Initializing database...")
    db.init_db()
    import bot.handlers
    bot.handlers.WEBAPP_URL = FRONTEND_URL
    logger.info(f"Setting webhook to {WEBHOOK_URL}")
    await bot_instance.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info("Starting scheduler...")
    setup_scheduler(bot_instance)

async def on_shutdown(bot_instance: Bot):
    logger.warning("Shutting down..")
    await bot_instance.delete_webhook()

# Оборачиваем FastAPI в WSGI-приложение, чтобы его мог запустить Gunicorn
def run_fastapi():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=WEBAPP_PORT)

# Запускаем FastAPI в отдельном потоке
fastapi_thread = threading.Thread(target=run_fastapi)
fastapi_thread.daemon = True
fastapi_thread.start()

# Запускаем основного бота с вебхуком
def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    webhook_request_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_request_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    # Отдельный маршрут для пинга
    async def handle_ping(request):
        return web.Response(text="Pong")
    app.add_routes([web.get('/ping', handle_ping)])
    
    logger.info("Starting aiohttp server for webhook...")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("AIOHTTP_PORT", 8080)))

# Этот код больше не нужен, так как FastAPI запускается в потоке
# if __name__ == "__main__":
#     main()