from aiogram import Bot
from datetime import datetime
import pytz # Библиотека для работы с часовыми поясами
import bot.db as db
import bot.keyboards as kb
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def send_morning_poll_to_user(bot: Bot, user_id: int):
    """Отправляет утренний опрос конкретному пользователю."""
    try:
        await bot.send_message(
            user_id,
            "☀️ Доброе утро, командир! Пора составить план боя на сегодня:",
            reply_markup=kb.get_morning_poll_keyboard()
        )
    except Exception as e:
        print(f"Не удалось отправить утренний опрос пользователю {user_id}: {e}")
        
# ОБНОВЛЕНО: Вечерняя сводка с анализом экранного времени
async def send_evening_summary_to_user(bot: Bot, user_id: int):
    """Отправляет вечернюю сводку конкретному пользователю."""
    try:
        stats = db.get_today_stats_for_user(user_id)
        if not stats: return

        summary_lines = ["🌙 Вечерний рапорт, командир:\n"]
        
        # Анализ экранного времени
        time_goal_hours = stats.get('screen_time_goal', 0)
        time_actual_minutes = db.get_today_screen_time(user_id)
        time_actual_hours = round(time_actual_minutes / 60, 1)

        time_status = "✅ В рамках!" if time_actual_hours <= time_goal_hours else "❌ Перелимит"
        summary_lines.append(f"📱 Экранное время: ~{time_actual_hours}ч из <{time_goal_hours}ч. ({time_status})")
        
        summary_lines.append("") # Пустая строка для разделения

        def get_status(planned, done):
            if not planned: return "не планировалась"
            return "✅ Выполнена" if done else "❌ Пропущена"

        summary_lines.append(f"⚔️ Тренировка: {get_status(stats['workout_planned'], stats['workout_done'])}")
        summary_lines.append(f"🎓 Английский: {get_status(stats['english_planned'], stats['english_done'])}")
        summary_lines.append(f"💻 Кодинг: {get_status(stats['coding_planned'], stats['coding_done'])}")
        summary_lines.append(f"📝 План: {get_status(stats['planning_planned'], stats['planning_done'])}")
        summary_lines.append(f"🧘 Растяжка: {get_status(stats['stretching_planned'], stats['stretching_done'])}")
        summary_lines.append(f"🤔 Размышления: {get_status(stats['reflection_planned'], stats['reflection_done'])}")
        
        summary_lines.append("\nСпокойной ночи. Завтра — новая битва.")
        await bot.send_message(user_id, "\n".join(summary_lines))
    except Exception as e:
        print(f"Не удалось отправить вечернюю сводку пользователю {user_id}: {e}")

async def check_and_send_messages(bot: Bot):
    """
    Главная функция планировщика. Запускается каждую минуту.
    Проверяет время для каждого пользователя и отправляет сообщения.
    """
    users = db.get_all_users_with_tz()
    for user in users:
        user_id = user['user_id']
        try:
            # Получаем текущее время в часовом поясе пользователя
            user_tz = pytz.timezone(user['timezone'])
            user_time = datetime.now(user_tz)

            # Проверяем, наступило ли время для утреннего опроса (8:00)
            if user_time.hour == 8 and user_time.minute == 0:
                await send_morning_poll_to_user(bot, user_id)
            
            # Проверяем, наступило ли время для вечерней сводки (20:00)
            if user_time.hour == 20 and user_time.minute == 0:
                await send_evening_summary_to_user(bot, user_id)

        except Exception as e:
            print(f"Ошибка при обработке пользователя {user_id}: {e}")


def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик."""
    scheduler = AsyncIOScheduler()
    # Запускаем нашу главную функцию проверки каждую минуту
    scheduler.add_job(check_and_send_messages, 'interval', minutes=1, args=[bot])
    scheduler.start()