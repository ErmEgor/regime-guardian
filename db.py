import os
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, IntegrityError
import random
from typing import List, Dict, Tuple, Any 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=10, pool_timeout=30, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    except OperationalError as e:
        logger.error(f"Database error: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()

def init_db():
    try:
        with get_db() as db:
            # Создание таблицы users
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    timezone TEXT DEFAULT 'Asia/Almaty'
                )
            """))
            
            # Создание таблицы daily_stats
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    stat_date DATE NOT NULL,
                    screen_time_goal INTEGER DEFAULT 0,
                    screen_time_actual INTEGER DEFAULT 0,
                    workout_planned INTEGER DEFAULT 0,
                    workout_done INTEGER DEFAULT 0,
                    english_planned INTEGER DEFAULT 0,
                    english_done INTEGER DEFAULT 0,
                    coding_planned INTEGER DEFAULT 0,
                    coding_done INTEGER DEFAULT 0,
                    planning_planned INTEGER DEFAULT 0,
                    planning_done INTEGER DEFAULT 0,
                    stretching_planned INTEGER DEFAULT 0,
                    stretching_done INTEGER DEFAULT 0,
                    reflection_planned INTEGER DEFAULT 0,
                    reflection_done INTEGER DEFAULT 0,
                    walk_planned INTEGER DEFAULT 0,
                    walk_done INTEGER DEFAULT 0,
                    morning_poll_completed BOOLEAN DEFAULT FALSE,
                    is_rest_day BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, stat_date)
                )
            """))
            
            # Создание таблицы sport_achievements
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS sport_achievements (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    achievement_name TEXT NOT NULL,
                    date_earned DATE NOT NULL
                )
            """))
            
            # Создание таблицы screen_activities
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS screen_activities (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    activity_date DATE NOT NULL,
                    activity_name TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL
                )
            """))
            
            # Создание таблицы productive_activities
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS productive_activities (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    activity_date DATE NOT NULL,
                    activity_name TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL
                )
            """))
            
            # Создание таблицы goals
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS goals (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    goal_name TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_value INTEGER DEFAULT 0,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    streak INTEGER DEFAULT 0
                )
            """))
            
            # Создание таблицы goal_completions
            print("Инициализация таблицы goal_completions...")
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS goal_completions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    goal_id INTEGER NOT NULL,
                    completion_date DATE NOT NULL,
                    completed BOOLEAN NOT NULL,
                    UNIQUE(user_id, goal_id, completion_date)
                )
            """))
            print("Таблица goal_completions создана или уже существует")
            
            # Создание таблицы habits
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS habits (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    habit_name TEXT NOT NULL,
                    UNIQUE(user_id, habit_name)
                )
            """))
            
            # Создание таблицы habit_completions
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS habit_completions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    habit_id INTEGER NOT NULL,
                    completion_date DATE NOT NULL,
                    completed BOOLEAN NOT NULL,
                    UNIQUE(user_id, habit_id, completion_date)
                )
            """))
            
            # Создание таблицы productivity_questions
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS productivity_questions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    answer_date DATE NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    UNIQUE(user_id, answer_date, question)
                )
            """))
            
            # Создание таблицы tips
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS tips (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    tip TEXT NOT NULL
                )
            """))
            
            # Добавление начальных советов для каждой категории
            # Чтобы добавить новый совет, используйте следующий формат:
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Категория', 'Текст нового совета'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Категория' AND tip = 'Текст нового совета')
            # """))
            
            # Мотивация
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Мотивация', 'Начните день с визуализации своих целей, чтобы оставаться мотивированным.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Мотивация')
            """))
            # Пример добавления нового совета для категории "Мотивация":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Мотивация', 'Верьте в себя, каждый маленький шаг приближает вас к большой цели.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Мотивация' AND tip = 'Верьте в себя, каждый маленький шаг приближает вас к большой цели.')
            # """))
            
            # Дисциплина
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Дисциплина', 'Создайте утреннюю рутину, чтобы задавать тон продуктивному дню.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Дисциплина')
            """))
            # Пример добавления нового совета для категории "Дисциплина":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Дисциплина', 'Ставьте таймер на задачи, чтобы избежать прокрастинации.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Дисциплина' AND tip = 'Ставьте таймер на задачи, чтобы избежать прокрастинации.')
            # """))
            
            # Фокус
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Фокус', 'Используйте метод Помодоро для поддержания концентрации.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Фокус')
            """))
            # Пример добавления нового совета для категории "Фокус":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Фокус', 'Уберите отвлекающие факторы, такие как телефон, во время работы.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Фокус' AND tip = 'Уберите отвлекающие факторы, такие как телефон, во время работы.')
            # """))
            
            # Спорт
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Спорт', 'Начните с коротких тренировок, чтобы сформировать привычку.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Спорт')
            """))
            # Пример добавления нового совета для категории "Спорт":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Спорт', 'Слушайте энергичную музыку во время тренировок для повышения мотивации.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Спорт' AND tip = 'Слушайте энергичную музыку во время тренировок для повышения мотивации.')
            # """))
            
            # Продуктивность
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Продуктивность', 'Ставьте SMART-цели: конкретные, измеримые, достижимые, релевантные и ограниченные по времени.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Продуктивность')
            """))
            # Пример добавления нового совета для категории "Продуктивность":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Продуктивность', 'Планируйте свой день с вечера, чтобы начать утро с ясной целью.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Продуктивность' AND tip = 'Планируйте свой день с вечера, чтобы начать утро с ясной целью.')
            # """))
            
            # Мышление
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Мышление', 'Практикуйте осознанность, чтобы лучше понимать свои мысли и эмоции.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Мышление')
            """))
            # Пример добавления нового совета для категории "Мышление":
            # db.execute(text("""
            #     INSERT INTO tips (category, tip)
            #     SELECT 'Мышление', 'Задавайте себе вопрос "Почему?" для анализа своих решений.'
            #     WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Мышление' AND tip = 'Задавайте себе вопрос "Почему?" для анализа своих решений.')
            # """))
            
            db.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def add_user(user_id: int, username: str, first_name: str):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO users (user_id, username, first_name, timezone)
                VALUES (:user_id, :username, :first_name, 'Asia/Almaty')
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name;
            """), {'user_id': user_id, 'username': username, 'first_name': first_name})
            db.commit()
            logger.info(f"Added/updated user {user_id}")
    except IntegrityError:
        logger.warning(f"User {user_id} already exists")
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
        raise

def save_morning_plan(user_id: int, screen_time: int, workout: int, english: int, coding: int, planning: int, stretching: int, reflection: int, walk: int, is_rest_day: bool):
    try:
        with get_db() as db:
            stmt = text("""
                INSERT INTO daily_stats (
                    user_id, stat_date, screen_time_goal, screen_time_actual,
                    workout_planned, workout_done, english_planned, english_done,
                    coding_planned, coding_done, planning_planned, planning_done,
                    stretching_planned, stretching_done, reflection_planned, reflection_done,
                    walk_planned, walk_done, morning_poll_completed, is_rest_day
                ) VALUES (
                    :user_id, :stat_date, :screen_time_goal, 0,
                    :workout_planned, 0, :english_planned, 0,
                    :coding_planned, 0, :planning_planned, 0,
                    :stretching_planned, 0, :reflection_planned, 0,
                    :walk_planned, 0, true, :is_rest_day
                ) ON CONFLICT (user_id, stat_date)
                DO UPDATE SET
                    screen_time_goal = :screen_time_goal,
                    workout_planned = :workout_planned,
                    english_planned = :english_planned,
                    coding_planned = :coding_planned,
                    planning_planned = :planning_planned,
                    stretching_planned = :stretching_planned,
                    reflection_planned = :reflection_planned,
                    walk_planned = :walk_planned,
                    morning_poll_completed = true,
                    is_rest_day = :is_rest_day
            """)
            db.execute(stmt, {
                'user_id': user_id,
                'stat_date': date.today(),
                'screen_time_goal': screen_time,
                'workout_planned': workout,
                'english_planned': english,
                'coding_planned': coding,
                'planning_planned': planning,
                'stretching_planned': stretching,
                'reflection_planned': reflection,
                'walk_planned': walk,
                'is_rest_day': is_rest_day
            })
            db.commit()
            logger.info(f"Saved morning plan for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving morning plan for user {user_id}: {e}")
        raise

def mark_activity_done(user_id: int, activity_type: str):
    try:
        with get_db() as db:
            activity_field = f"{activity_type}_done"
            stmt = text(f"""
                UPDATE daily_stats
                SET {activity_field} = 1
                WHERE user_id = :user_id AND stat_date = :stat_date
            """)
            db.execute(stmt, {'user_id': user_id, 'stat_date': date.today()})
            db.commit()
            logger.info(f"Marked {activity_type} as done for user {user_id}")
    except Exception as e:
        logger.error(f"Error marking activity {activity_type} for user {user_id}: {e}")
        raise

def add_sport_achievement(user_id: int, achievement_name: str, date_earned: date):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO sport_achievements (user_id, achievement_name, date_earned)
                VALUES (:user_id, :achievement_name, :date_earned)
            """), {'user_id': user_id, 'achievement_name': achievement_name, 'date_earned': date_earned})
            db.commit()
            logger.info(f"Added sport achievement '{achievement_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error adding sport achievement for user {user_id}: {e}")
        raise

def log_custom_activity(user_id: int, activity_name: str, duration_minutes: int):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO screen_activities (user_id, activity_date, activity_name, duration_minutes)
                VALUES (:user_id, :activity_date, :activity_name, :duration_minutes)
            """), {
                'user_id': user_id,
                'activity_date': date.today(),
                'activity_name': activity_name,
                'duration_minutes': duration_minutes
            })
            db.execute(text("""
                UPDATE daily_stats
                SET screen_time_actual = screen_time_actual + :duration_minutes
                WHERE user_id = :user_id AND stat_date = :activity_date
            """), {
                'user_id': user_id,
                'activity_date': date.today(),
                'duration_minutes': duration_minutes
            })
            db.commit()
            logger.info(f"Logged screen activity '{activity_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error logging screen activity for user {user_id}: {e}")
        raise

def log_productive_activity(user_id: int, activity_name: str, duration_minutes: int):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO productive_activities (user_id, activity_date, activity_name, duration_minutes)
                VALUES (:user_id, :activity_date, :activity_name, :duration_minutes)
            """), {
                'user_id': user_id,
                'activity_date': date.today(),
                'activity_name': activity_name,
                'duration_minutes': duration_minutes
            })
            db.commit()
            logger.info(f"Logged productive activity '{activity_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error logging productive activity for user {user_id}: {e}")
        raise

def add_goal(user_id: int, goal_name: str, goal_type: str, target_value: int, current_value: int, start_date: date, end_date: date, streak: int = 0):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO goals (user_id, goal_name, goal_type, target_value, current_value, start_date, end_date, is_completed, streak)
                VALUES (:user_id, :goal_name, :goal_type, :target_value, :current_value, :start_date, :end_date, :is_completed, :streak)
            """), {
                'user_id': user_id,
                'goal_name': goal_name,
                'goal_type': goal_type,
                'target_value': target_value,
                'current_value': current_value,
                'start_date': start_date,
                'end_date': end_date,
                'is_completed': False,
                'streak': streak
            })
            db.commit()
            logger.info(f"Added goal '{goal_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error adding goal for user {user_id}: {e}")
        raise

def log_goal_completion(user_id: int, goal_id: int, completed: bool):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO goal_completions (user_id, goal_id, completion_date, completed)
                VALUES (:user_id, :goal_id, :completion_date, :completed)
                ON CONFLICT (user_id, goal_id, completion_date)
                DO UPDATE SET completed = :completed
            """), {
                'user_id': user_id,
                'goal_id': goal_id,
                'completion_date': date.today(),
                'completed': completed
            })
            db.commit()
            logger.info(f"Logged goal completion for user {user_id}, goal {goal_id}")
    except Exception as e:
        logger.error(f"Error logging goal completion for user {user_id}: {e}")
        raise

def update_goal_progress(user_id: int, activity_type: str, value: int):
    try:
        with get_db() as db:
            # Проверяем, есть ли цели, связанные с этой активностью
            stmt = text("""
                SELECT id, goal_name, goal_type, target_value, current_value
                FROM goals
                WHERE user_id = :uid AND is_completed = false
            """)
            goals = db.execute(stmt, {'uid': user_id}).fetchall()
            for goal in goals:
                goal_id = goal.id
                goal_type = goal.goal_type
                target_value = goal.target_value
                current_value = goal.current_value
                # Пример: связываем активность "workout" с целями, связанными с тренировками
                if activity_type == 'workout' and 'трениров' in goal.goal_name.lower():
                    new_value = current_value + value
                    if goal_type == 'daily' or (goal_type == 'weekly' and new_value <= target_value):
                        db.execute(text("""
                            UPDATE goals
                            SET current_value = :new_value
                            WHERE id = :goal_id
                        """), {
                            'new_value': min(new_value, target_value),
                            'goal_id': goal_id
                        })
                        if new_value >= target_value:
                            db.execute(text("""
                                UPDATE goals
                                SET is_completed = true
                                WHERE id = :goal_id
                            """), {'goal_id': goal_id})
            db.commit()
            logger.info(f"Updated goal progress for user {user_id}, activity {activity_type}")
    except Exception as e:
        logger.error(f"Error updating goal progress for user {user_id}: {e}")
        raise

def update_goal_streak(user_id: int, goal_id: int):
    try:
        with get_db() as db:
            # Получаем тип цели и текущий стрик
            stmt = text("""
                SELECT goal_type, streak, start_date, target_value
                FROM goals
                WHERE id = :goal_id AND user_id = :uid
            """)
            goal = db.execute(stmt, {'goal_id': goal_id, 'uid': user_id}).first()
            if not goal:
                logger.warning(f"Goal {goal_id} not found for user {user_id}")
                return
            goal_type, current_streak, start_date, target_value = goal
            today = date.today()
            
            # Проверяем, был ли предыдущий день/неделя успешной
            if goal_type == 'daily':
                stmt = text("""
                    SELECT completed
                    FROM goal_completions
                    WHERE goal_id = :goal_id AND completion_date = :prev_date
                """)
                prev_date = today - timedelta(days=1)
                prev_completion = db.execute(stmt, {'goal_id': goal_id, 'prev_date': prev_date}).first()
                new_streak = current_streak + 1 if prev_completion and prev_completion.completed else 1
            else:  # weekly
                week_start = today - timedelta(days=today.weekday())
                week_number = (today - start_date).days // 7
                stmt = text("""
                    SELECT COUNT(*) as completed_days
                    FROM goal_completions
                    WHERE goal_id = :goal_id AND completion_date >= :week_start AND completion_date <= :today AND completed = true
                """)
                completed_days = db.execute(stmt, {'goal_id': goal_id, 'week_start': week_start, 'today': today}).first().completed_days
                prev_week_start = week_start - timedelta(days=7)
                stmt = text("""
                    SELECT COUNT(*) as prev_completed_days
                    FROM goal_completions
                    WHERE goal_id = :goal_id AND completion_date >= :prev_week_start AND completion_date < :week_start AND completed = true
                """)
                prev_completed_days = db.execute(stmt, {'goal_id': goal_id, 'prev_week_start': prev_week_start, 'week_start': week_start}).first().prev_completed_days
                new_streak = current_streak + 1 if completed_days >= target_value and prev_completed_days >= target_value else (1 if completed_days >= target_value else 0)
            
            db.execute(text("""
                UPDATE goals
                SET streak = :new_streak
                WHERE id = :goal_id
            """), {'new_streak': new_streak, 'goal_id': goal_id})
            db.commit()
            logger.info(f"Updated goal streak for user {user_id}, goal {goal_id}")
    except Exception as e:
        logger.error(f"Error updating goal streak for user {user_id}: {e}")
        raise

def add_habit(user_id: int, habit_name: str):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO habits (user_id, habit_name)
                VALUES (:user_id, :habit_name)
                ON CONFLICT (user_id, habit_name) DO NOTHING
            """), {'user_id': user_id, 'habit_name': habit_name})
            db.commit()
            logger.info(f"Added habit '{habit_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error adding habit for user {user_id}: {e}")
        raise

def log_habit_completion(user_id: int, habit_id: int, completed: bool):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO habit_completions (user_id, habit_id, completion_date, completed)
                VALUES (:user_id, :habit_id, :completion_date, :completed)
                ON CONFLICT (user_id, habit_id, completion_date)
                DO UPDATE SET completed = :completed
            """), {
                'user_id': user_id,
                'habit_id': habit_id,
                'completion_date': date.today(),
                'completed': completed
            })
            db.commit()
            logger.info(f"Logged habit completion for user {user_id}, habit {habit_id}")
    except Exception as e:
        logger.error(f"Error logging habit completion for user {user_id}: {e}")
        raise

def save_productivity_answer(user_id: int, question: str, answer: str):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO productivity_questions (user_id, answer_date, question, answer)
                VALUES (:user_id, :answer_date, :question, :answer)
                ON CONFLICT (user_id, answer_date, question)
                DO UPDATE SET answer = :answer
            """), {
                'user_id': user_id,
                'answer_date': date.today(),
                'question': question,
                'answer': answer
            })
            db.commit()
            logger.info(f"Saved productivity answer for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving productivity answer for user {user_id}: {e}")
        raise

def get_today_stats_for_user(user_id: int):
    try:
        with get_db() as db:
            stmt = text("""
                SELECT * FROM daily_stats
                WHERE user_id = :user_id AND stat_date = :stat_date
            """)
            result = db.execute(stmt, {'user_id': user_id, 'stat_date': date.today()}).first()
            if result:
                return result._asdict()
            return None
    except Exception as e:
        logger.error(f"Error fetching today stats for user {user_id}: {e}")
        raise

def get_today_screen_time(user_id: int):
    try:
        with get_db() as db:
            stmt = text("""
                SELECT SUM(duration_minutes) as total
                FROM screen_activities
                WHERE user_id = :user_id AND activity_date = :activity_date
            """)
            result = db.execute(stmt, {'user_id': user_id, 'activity_date': date.today()}).first()
            return result.total or 0
    except Exception as e:
        logger.error(f"Error fetching screen time for user {user_id}: {e}")
        raise

def clear_user_data(user_id: int):
    """
    Очищает все данные пользователя из всех связанных таблиц.
    Проверяет существование таблиц перед выполнением запросов.
    Учитывает порядок удаления для соблюдения ссылочной целостности.
    """
    try:
        with get_db() as db:
            # Список таблиц в порядке, учитывающем зависимости (сначала дочерние, затем родительские)
            tables: List[Tuple[str, str]] = [
                ('habit_completions', 'DELETE FROM habit_completions WHERE user_id = :user_id'),
                ('goal_completions', 'DELETE FROM goal_completions WHERE user_id = :user_id'),
                ('daily_stats', 'DELETE FROM daily_stats WHERE user_id = :user_id'),
                ('sport_achievements', 'DELETE FROM sport_achievements WHERE user_id = :user_id'),
                ('screen_activities', 'DELETE FROM screen_activities WHERE user_id = :user_id'),
                ('productive_activities', 'DELETE FROM productive_activities WHERE user_id = :user_id'),
                ('productivity_questions', 'DELETE FROM productivity_questions WHERE user_id = :user_id'),
                ('habits', 'DELETE FROM habits WHERE user_id = :user_id'),
                ('goals', 'DELETE FROM goals WHERE user_id = :user_id'),
                ('users', 'DELETE FROM users WHERE user_id = :user_id'),
            ]

            # Проверка и удаление данных из каждой таблицы
            for table_name, delete_query in tables:
                # Проверяем, существует ли таблица
                check_table_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """)
                table_exists = db.execute(check_table_query, {'table_name': table_name}).scalar()

                if table_exists:
                    db.execute(text(delete_query), {'user_id': user_id})
                    logger.info(f"Deleted data from {table_name} for user_id {user_id}")
                else:
                    logger.warning(f"Table {table_name} does not exist, skipping deletion for user_id {user_id}")

            db.commit()
            logger.info(f"Successfully cleared all data for user_id {user_id}")
    except Exception as e:
        logger.error(f"Error clearing data for user_id {user_id}: {e}")
        raise

def get_random_tip():
    try:
        with get_db() as db:
            stmt = text("SELECT category, tip FROM tips ORDER BY RANDOM() LIMIT 1")
            result = db.execute(stmt).first()
            if result:
                return result._asdict()['category'], result._asdict()['tip']
            return None
    except Exception as e:
        logger.error(f"Error fetching random tip: {e}")
        raise

def check_and_award_achievements(user_id: int):
    try:
        with get_db() as db:
            today = date.today()
            # Периоды для проверки стрика
            streak_periods = [3, 7, 14, 30]

            # 1. Достижение: Выполнение всех главных активностей
            activities = ['workout', 'english', 'coding', 'planning', 'stretching', 'reflection', 'walk']
            for days in streak_periods:
                start_date = today - timedelta(days=days)
                stmt = text("""
                    SELECT stat_date
                    FROM daily_stats
                    WHERE user_id = :user_id
                    AND stat_date > :start_date
                    AND stat_date <= :today
                    AND is_rest_day = false
                    AND (
                        (workout_planned = 0 OR workout_done = 1) AND
                        (english_planned = 0 OR english_done = 1) AND
                        (coding_planned = 0 OR coding_done = 1) AND
                        (planning_planned = 0 OR planning_done = 1) AND
                        (stretching_planned = 0 OR stretching_done = 1) AND
                        (reflection_planned = 0 OR reflection_done = 1) AND
                        (walk_planned = 0 OR walk_done = 1)
                    )
                """)
                completed_days = db.execute(stmt, {'user_id': user_id, 'start_date': start_date, 'today': today}).fetchall()
                if len(completed_days) >= days:
                    achievement_name = f"Выполнение всех главных активностей {days} дней"
                    db.execute(text("""
                        INSERT INTO sport_achievements (user_id, achievement_name, date_earned)
                        VALUES (:user_id, :achievement_name, :date_earned)
                        ON CONFLICT DO NOTHING
                    """), {
                        'user_id': user_id,
                        'achievement_name': achievement_name,
                        'date_earned': today
                    })
                    logger.info(f"Awarded '{achievement_name}' achievement to user {user_id}")

            # 2. Достижение: Держал экранное время в лимите
            for days in streak_periods:
                start_date = today - timedelta(days=days)
                stmt = text("""
                    SELECT stat_date
                    FROM daily_stats
                    WHERE user_id = :user_id
                    AND stat_date > :start_date
                    AND stat_date <= :today
                    AND is_rest_day = false
                    AND screen_time_actual <= screen_time_goal
                """)
                compliant_days = db.execute(stmt, {'user_id': user_id, 'start_date': start_date, 'today': today}).fetchall()
                if len(compliant_days) >= days:
                    achievement_name = f"Держал экранное время в лимите {days} дней"
                    db.execute(text("""
                        INSERT INTO sport_achievements (user_id, achievement_name, date_earned)
                        VALUES (:user_id, :achievement_name, :date_earned)
                        ON CONFLICT DO NOTHING
                    """), {
                        'user_id': user_id,
                        'achievement_name': achievement_name,
                        'date_earned': today
                    })
                    logger.info(f"Awarded '{achievement_name}' achievement to user {user_id}")

            # 3. Достижение: Записывал хотя бы 60 минут полезных активностей
            for days in streak_periods:
                start_date = today - timedelta(days=days)
                stmt = text("""
                    SELECT pa.activity_date
                    FROM productive_activities pa
                    WHERE pa.user_id = :user_id
                    AND pa.activity_date > :start_date
                    AND pa.activity_date <= :today
                    GROUP BY pa.activity_date
                    HAVING SUM(pa.duration_minutes) >= 60
                """)
                productive_days = db.execute(stmt, {'user_id': user_id, 'start_date': start_date, 'today': today}).fetchall()
                if len(productive_days) >= days:
                    achievement_name = f"Записывал хотя бы 60 минут полезных активностей {days} дней"
                    db.execute(text("""
                        INSERT INTO sport_achievements (user_id, achievement_name, date_earned)
                        VALUES (:user_id, :achievement_name, :date_earned)
                        ON CONFLICT DO NOTHING
                    """), {
                        'user_id': user_id,
                        'achievement_name': achievement_name,
                        'date_earned': today
                    })
                    logger.info(f"Awarded '{achievement_name}' achievement to user {user_id}")
            db.commit()
    except Exception as e:
        logger.error(f"Error checking achievements for user {user_id}: {e}")
        raise

def get_tips_by_category(category: str) -> List[Dict[str, str]]:
    try:
        with get_db() as db:
            stmt = text("SELECT id, tip AS title FROM tips WHERE category = :category")
            tips = db.execute(stmt, {'category': category}).fetchall()
            return [{'id': tip.id, 'title': tip.title} for tip in tips]
    except Exception as e:
        logger.error(f"Error fetching tips for category {category}: {e}")
        raise

def get_habits_with_progress(user_id: int) -> List[Dict[str, any]]:
    try:
        with get_db() as db:
            stmt = text("""
                SELECT id, habit_name AS name
                FROM habits
                WHERE user_id = :user_id
            """)
            habits = db.execute(stmt, {'user_id': user_id}).fetchall()
            result = []
            for habit in habits:
                streak = get_habit_streak(user_id, habit.id)
                result.append({
                    'id': habit.id,
                    'name': habit.name,
                    'streak': streak
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching habits with progress for user_id {user_id}: {e}")
        raise

def get_habit_streak(user_id: int, habit_id: int) -> int:
    try:
        with get_db() as db:
            today = date.today()
            streak = 0
            current_date = today
            while True:
                stmt = text("""
                    SELECT completed
                    FROM habit_completions
                    WHERE user_id = :user_id AND habit_id = :habit_id AND completion_date = :date
                """)
                result = db.execute(stmt, {'user_id': user_id, 'habit_id': habit_id, 'date': current_date}).first()
                if not result or not result.completed:
                    break
                streak += 1
                current_date -= timedelta(days=1)
            return streak
    except Exception as e:
        logger.error(f"Error calculating habit streak for user {user_id}, habit {habit_id}: {e}")
        raise
 
def delete_sport_achievement(user_id: int, achievement_id: int):
    """
    Удаляет конкретное спортивное достижение пользователя по его ID.
    """
    try:
        with get_db() as db:
            stmt = text("DELETE FROM sport_achievements WHERE user_id = :user_id AND id = :achievement_id")
            result = db.execute(stmt, {'user_id': user_id, 'achievement_id': achievement_id})
            db.commit()
            if result.rowcount > 0:
                logger.info(f"Deleted sport achievement {achievement_id} for user {user_id}")
            else:
                logger.warning(f"No sport achievement {achievement_id} found for user {user_id}")
    except Exception as e:
        logger.error(f"Error deleting sport achievement {achievement_id} for user {user_id}: {e}")
        raise

def delete_habit(user_id: int, habit_id: int):
    """
    Удаляет конкретную привычку пользователя по её ID, включая связанные записи в habit_completions.
    """
    try:
        with get_db() as db:
            db.execute(text("DELETE FROM habit_completions WHERE user_id = :user_id AND habit_id = :habit_id"),
                      {'user_id': user_id, 'habit_id': habit_id})
            stmt = text("DELETE FROM habits WHERE user_id = :user_id AND id = :habit_id")
            result = db.execute(stmt, {'user_id': user_id, 'habit_id': habit_id})
            db.commit()
            if result.rowcount > 0:
                logger.info(f"Deleted habit {habit_id} for user {user_id}")
            else:
                logger.warning(f"No habit {habit_id} found for user {user_id}")
    except Exception as e:
        logger.error(f"Error deleting habit {habit_id} for user {user_id}: {e}")
        raise

def delete_goal(user_id: int, goal_id: int):
    """
    Удаляет конкретную цель пользователя по её ID, включая связанные записи в goal_completions.
    """
    try:
        with get_db() as db:
            db.execute(text("DELETE FROM goal_completions WHERE user_id = :user_id AND goal_id = :goal_id"),
                      {'user_id': user_id, 'goal_id': goal_id})
            stmt = text("DELETE FROM goals WHERE user_id = :user_id AND id = :goal_id")
            result = db.execute(stmt, {'user_id': user_id, 'goal_id': goal_id})
            db.commit()
            if result.rowcount > 0:
                logger.info(f"Deleted goal {goal_id} for user {user_id}")
            else:
                logger.warning(f"No goal {goal_id} found for user {user_id}")
    except Exception as e:
        logger.error(f"Error deleting goal {goal_id} for user {user_id}: {e}")
        raise

def get_sport_achievements(user_id: int) -> List[Dict[str, any]]:
    """
    Получает список спортивных достижений пользователя.
    """
    try:
        with get_db() as db:
            stmt = text("""
                SELECT id, achievement_name AS name, date_earned
                FROM sport_achievements
                WHERE user_id = :user_id
                ORDER BY date_earned DESC
            """)
            achievements = db.execute(stmt, {'user_id': user_id}).fetchall()
            return [{'id': ach.id, 'name': ach.name, 'date_earned': ach.date_earned} for ach in achievements]
    except Exception as e:
        logger.error(f"Error fetching sport achievements for user_id {user_id}: {e}")
        raise

def get_habits(user_id: int) -> List[Dict[str, any]]:
    """
    Получает список привычек пользователя.
    """
    try:
        with get_db() as db:
            stmt = text("""
                SELECT id, habit_name AS name
                FROM habits
                WHERE user_id = :user_id
                ORDER BY id
            """)
            habits = db.execute(stmt, {'user_id': user_id}).fetchall()
            return [{'id': habit.id, 'name': habit.name} for habit in habits]
    except Exception as e:
        logger.error(f"Error fetching habits for user_id {user_id}: {e}")
        raise

def get_goals(user_id: int) -> List[Dict[str, any]]:
    """
    Получает список активных целей пользователя.
    """
    try:
        with get_db() as db:
            stmt = text("""
                SELECT id, goal_name AS name, goal_type, target_value, current_value, start_date, end_date, streak
                FROM goals
                WHERE user_id = :user_id AND is_completed = false
                ORDER BY start_date
            """)
            goals = db.execute(stmt, {'user_id': user_id}).fetchall()
            return [{
                'id': goal.id,
                'name': goal.name,
                'goal_type': goal.goal_type,
                'target_value': goal.target_value,
                'current_value': goal.current_value,
                'start_date': goal.start_date,
                'end_date': goal.end_date,
                'streak': goal.streak
            } for goal in goals]
    except Exception as e:
        logger.error(f"Error fetching goals for user_id {user_id}: {e}")
        raise

def reset_goals():
    """
    Сбрасывает прогресс для ежедневных и еженедельных целей.
    Ежедневные сбрасываются каждый день.
    Еженедельные сбрасываются в понедельник.
    """
    try:
        with get_db() as db:
            today = date.today()
            
            # Сброс всех ежедневных целей
            db.execute(text("""
                UPDATE goals SET current_value = 0, is_completed = false 
                WHERE goal_type = 'daily' AND is_completed = true
            """))
            logger.info("Reset progress for daily goals.")

            # Если сегодня понедельник (weekday() == 0), сбрасываем еженедельные цели
            if today.weekday() == 0:
                db.execute(text("""
                    UPDATE goals SET current_value = 0, is_completed = false 
                    WHERE goal_type = 'weekly'
                """))
                logger.info("Reset progress for weekly goals because it's Monday.")
            
            db.commit()
    except Exception as e:
        logger.error(f"Error resetting goals: {e}")
        raise

def set_user_timezone(user_id: int, timezone: str):
    """Устанавливает часовой пояс для пользователя."""
    try:
        with get_db() as db:
            stmt = text("UPDATE users SET timezone = :timezone WHERE user_id = :user_id")
            db.execute(stmt, {'timezone': timezone, 'user_id': user_id})
            db.commit()
            logger.info(f"Set timezone for user {user_id} to {timezone}")
    except Exception as e:
        logger.error(f"Error setting timezone for user {user_id}: {e}")
        raise

def get_user_timezone(user_id: int) -> str:
    """Получает часовой пояс пользователя из базы данных."""
    try:
        with get_db() as db:
            stmt = text("SELECT timezone FROM users WHERE user_id = :user_id")
            result = db.execute(stmt, {'user_id': user_id}).scalar_one_or_none()
            return result or 'Asia/Almaty'
    except Exception as e:
        logger.error(f"Error getting timezone for user {user_id}: {e}")
        return 'Asia/Almaty'
    
def get_paginated_achievements(user_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * per_page
    with get_db() as db:
        stmt_items = text("SELECT id, achievement_name AS name FROM sport_achievements WHERE user_id = :uid ORDER BY date_earned DESC LIMIT :limit OFFSET :offset")
        items = db.execute(stmt_items, {'uid': user_id, 'limit': per_page, 'offset': offset}).fetchall()
        stmt_total = text("SELECT COUNT(id) FROM sport_achievements WHERE user_id = :uid")
        total = db.execute(stmt_total, {'uid': user_id}).scalar_one()
        return [{'id': item.id, 'name': item.name} for item in items], total

def get_paginated_habits(user_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * per_page
    with get_db() as db:
        stmt_items = text("SELECT id, habit_name AS name FROM habits WHERE user_id = :uid ORDER BY id LIMIT :limit OFFSET :offset")
        items = db.execute(stmt_items, {'uid': user_id, 'limit': per_page, 'offset': offset}).fetchall()
        stmt_total = text("SELECT COUNT(id) FROM habits WHERE user_id = :uid")
        total = db.execute(stmt_total, {'uid': user_id}).scalar_one()
        return [{'id': item.id, 'name': item.name} for item in items], total

def get_paginated_goals(user_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * per_page
    with get_db() as db:
        stmt_items = text("SELECT id, goal_name AS name FROM goals WHERE user_id = :uid ORDER BY start_date LIMIT :limit OFFSET :offset")
        items = db.execute(stmt_items, {'uid': user_id, 'limit': per_page, 'offset': offset}).fetchall()
        stmt_total = text("SELECT COUNT(id) FROM goals WHERE user_id = :uid")
        total = db.execute(stmt_total, {'uid': user_id}).scalar_one()
        return [{'id': item.id, 'name': item.name} for item in items], total

def reset_missed_streaks():
    """Сбрасывает стрики для целей, которые не были выполнены. Вызывается ежедневно."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    with get_db() as db:
        try:
            # Сброс для ежедневных целей, не выполненных вчера
            stmt_daily = text("""
                UPDATE goals SET streak = 0 WHERE goal_type = 'daily' AND streak > 0 AND id NOT IN (
                    SELECT goal_id FROM goal_completions WHERE completion_date = :yesterday AND completed = true AND goal_id IS NOT NULL
                )
            """)
            db.execute(stmt_daily, {'yesterday': yesterday})
            logger.info("Reset streaks for missed daily goals.")

            # Если сегодня понедельник, сброс для еженедельных целей
            if today.weekday() == 0:
                last_week_start = today - timedelta(days=7)
                last_week_end = today - timedelta(days=1)
                stmt_weekly = text("""
                    UPDATE goals g SET streak = 0 WHERE g.goal_type = 'weekly' AND g.streak > 0 AND (
                        SELECT COUNT(id) FROM goal_completions gc 
                        WHERE gc.goal_id = g.id AND gc.completion_date BETWEEN :start_date AND :end_date AND gc.completed = true
                    ) < g.target_value
                """)
                db.execute(stmt_weekly, {'start_date': last_week_start, 'end_date': last_week_end})
                logger.info("Reset streaks for missed weekly goals.")
            db.commit()
        except Exception as e:
            logger.error(f"Error in reset_missed_streaks: {e}")
            db.rollback()
            raise

def get_full_user_stats(user_id: int) -> Dict[str, Any]:
    """Собирает всю статистику для API одним вызовом."""
    with get_db() as db:
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        
        today_main_stats = db.execute(text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date = :today"), {'uid': user_id, 'today': today}).first()
        if not today_main_stats: return {'today_main_stats': None}
        
        screen_breakdown = {r.activity_name: r.duration_minutes for r in db.execute(text("SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = :uid AND activity_date = :today"), {'uid': user_id, 'today': today})}
        productive_breakdown = {r.activity_name: r.duration_minutes for r in db.execute(text("SELECT activity_name, duration_minutes FROM productive_activities WHERE user_id = :uid AND activity_date = :today"), {'uid': user_id, 'today': today})}
        
        today_goals = {r.goal_name: r.completed for r in db.execute(text("SELECT g.goal_name, gc.completed FROM goal_completions gc JOIN goals g ON gc.goal_id = g.id WHERE gc.user_id = :uid AND gc.completion_date = :today"), {'uid': user_id, 'today': today})}
        today_habits = {r.habit_name: r.completed for r in db.execute(text("SELECT h.habit_name, hc.completed FROM habit_completions hc JOIN habits h ON hc.habit_id = h.id WHERE hc.user_id = :uid AND hc.completion_date = :today"), {'uid': user_id, 'today': today})}
        productivity_questions = {r.question: r.answer for r in db.execute(text("SELECT question, answer FROM productivity_questions WHERE user_id = :uid AND answer_date = :today"), {'uid': user_id, 'today': today})}
        
        goals_data = db.execute(text("SELECT * FROM goals WHERE user_id = :uid AND is_completed = false"), {'uid': user_id}).fetchall()
        habits_data = db.execute(text("SELECT id, habit_name as name FROM habits WHERE user_id = :uid"), {'uid': user_id}).fetchall()

        history_main_stats = db.execute(text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date >= :start AND stat_date < :today ORDER BY stat_date DESC"), {'uid': user_id, 'start': seven_days_ago, 'today': today}).fetchall()
        history_screen_time_map = {r.activity_date: r.total for r in db.execute(text("SELECT activity_date, SUM(duration_minutes) as total FROM screen_activities WHERE user_id = :uid AND activity_date >= :start AND activity_date < :today GROUP BY activity_date"), {'uid': user_id, 'start': seven_days_ago, 'today': today})}
        history_productive_time_map = {r.activity_date: r.total for r in db.execute(text("SELECT activity_date, SUM(duration_minutes) as total FROM productive_activities WHERE user_id = :uid AND activity_date >= :start AND activity_date < :today GROUP BY activity_date"), {'uid': user_id, 'start': seven_days_ago, 'today': today})}

        return {
            'today_main_stats': today_main_stats._asdict(),
            'today_screen_time_total': sum(screen_breakdown.values()),
            'screen_time_breakdown': screen_breakdown,
            'productive_time_actual': sum(productive_breakdown.values()),
            'productive_time_breakdown': productive_breakdown,
            'today_goals': today_goals, 'habits': today_habits,
            'productivity_questions': productivity_questions,
            'goals': [{'id': g.id, 'goal_name': g.goal_name, 'goal_type': g.goal_type, 'target_value': g.target_value, 'current_value': g.current_value, 'start_date': g.start_date.isoformat(), 'end_date': g.end_date.isoformat(), 'is_completed': g.is_completed, 'streak': g.streak} for g in goals_data],
            'habits_data': [h._asdict() for h in habits_data],
            'history': [h._asdict() for h in history_main_stats],
            'history_screen_time_map': history_screen_time_map,
            'history_productive_time_map': history_productive_time_map,
        }