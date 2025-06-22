import asyncio
import logging
import os
import threading
import uvicorn
from os import getenv
from dotenv import load_dotenv

# --- Импорты для Вебхука и Веб-сервера ---
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- Импорты для FastAPI (бэкенд) ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# (импорты pydantic и другие для API)
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import date, timedelta
import sqlite3

# --- Импорты для нашего бота "Страж Режима" ---
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import bot.db as db
from bot.handlers import router as regime_handlers_router
from bot.scheduler import setup_scheduler

# --- 1. НАСТРОЙКА И КОНФИГУРАЦИЯ ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# Переменные окружения для Render
BOT_TOKEN = getenv("BOT_TOKEN")
# Адрес нашего фронтенда на Vercel
FRONTEND_URL = getenv("FRONTEND_URL")
# Адрес, который Render выдаст для этого сервиса
RENDER_URL = getenv("RENDER_URL")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# Порт, который будет слушать Render
WEBAPP_PORT = int(getenv("PORT", 10000))

# --- 2. ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПЕТЧЕРА ---

# Наш бот "Страж Режима"
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
# Подключаем все наши хэндлеры из папки /bot
dp.include_router(regime_handlers_router)

# --- 3. ЛОГИКА FastAPI БЭКЕНДА ---

# Создаем экземпляр FastAPI
fastapi_app = FastAPI()

# Настраиваем CORS, чтобы фронтенд мог делать запросы
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Вставляем сюда все Pydantic модели и эндпоинты из вашего webapp/backend/main.py ---

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
    workout_planned: int = 0
    workout_done: int = 0
    english_planned: int = 0
    english_done: int = 0
    coding_planned: int = 0
    coding_done: int = 0
    planning_planned: int = 0
    planning_done: int = 0
    stretching_planned: int = 0
    stretching_done: int = 0
    reflection_planned: int = 0
    reflection_done: int = 0

class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]

def get_db_connection():
    # На Render база данных будет создана в корневом каталоге проекта
    conn = sqlite3.connect('./database.db')
    conn.row_factory = sqlite3.Row
    return conn

@fastapi_app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
def read_user_stats(user_id: int):
    # (Здесь вся ваша рабочая логика для эндпоинта, я не буду ее повторять, но она должна быть здесь)
    conn = get_db_connection()
    try:
        # ... вся ваша логика получения today и history ...
        # Пример заглушки, замените на ваш код
        today_iso = date.today().isoformat()
        today_main_stats = conn.execute("SELECT * FROM daily_stats WHERE user_id = ? AND stat_date = ?", (user_id, today_iso)).fetchone()
        if not today_main_stats: raise HTTPException(404)
        today_data = TodayStats(**today_main_stats) # Упрощенно
        history_data = [] # Упрощенно
        return UserStatsResponse(user_id=user_id, today=today_data, history=history_data)
    finally:
        conn.close()

# --- 4. НАСТРОЙКА И ЗАПУСК ВЕБ-СЕРВЕРА AIOHTTP (ДЛЯ ВЕБХУКА) ---

async def on_startup(bot: Bot):
    """Действия при старте: инициализация БД, установка вебхука, запуск планировщика."""
    logger.info("Initializing database...")
    db.init_db()

    # ВАЖНО: Передаем реальный URL фронтенда в хэндлеры
    import bot.handlers
    bot.handlers.WEBAPP_URL = FRONTEND_URL

    logger.info(f"Setting webhook to {WEBHOOK_URL}")
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)

    logger.info("Starting scheduler...")
    setup_scheduler(bot)
    logger.info("Bot and scheduler are running.")

async def on_shutdown(bot: Bot):
    """Действия при остановке: удаление вебхука."""
    logger.warning("Shutting down..")
    await bot.delete_webhook()
    logger.warning("Bot webhook deleted. Bye!")

# Создаем веб-приложение aiohttp
aiohttp_app = web.Application()

# Регистрируем обработчик для вебхука Telegram
webhook_request_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_request_handler.register(aiohttp_app, path=WEBHOOK_PATH)

# Встраиваем FastAPI приложение как под-приложение в aiohttp
# Это позволит FastAPI обрабатывать свои маршруты (например, /api/stats/...)
# Внимание: uvicorn и gunicorn нужны для запуска этого под-приложения
from fastapi.middleware.wsgi import WSGIMiddleware
aiohttp_app.add_subapp("/api/", WSGIMiddleware(fastapi_app))

# Добавляем маршрут /ping для мониторинга
async def handle_ping(request):
    return web.Response(text="Pong")

aiohttp_app.add_routes([web.get('/ping', handle_ping)])

# Передаем действия при старте и остановке в диспетчер
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

# --- 5. ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---

def main():
    """Точка входа. Запускает веб-сервер aiohttp."""
    logger.info("Starting web server...")
    setup_application(aiohttp_app, dp, bot=bot)
    web.run_app(aiohttp_app, host="0.0.0.0", port=WEBAPP_PORT)

if __name__ == "__main__":
    main()