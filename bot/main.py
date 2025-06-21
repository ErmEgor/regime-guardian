import asyncio
import logging
from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
# Убираем APScheduler отсюда
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.handlers import router
from bot.scheduler import setup_scheduler # Импортируем нашу новую функцию
import bot.db as db

async def main():
    load_dotenv()
    db.init_db()

    bot = Bot(token=getenv("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)

    # Запускаем наш кастомный планировщик
    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Установка pytz
    # pip install pytz
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")