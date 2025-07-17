import os
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, IntegrityError
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=10, pool_timeout=30)
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
                    first_name TEXT
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
                    is_completed BOOLEAN DEFAULT FALSE
                )
            """))
            
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
            
            # Добавление начальных советов, если таблица пуста
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Продуктивность', 'Ставьте SMART-цели: конкретные, измеримые, достижимые, релевантные и ограниченные по времени.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Продуктивность')
            """))
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Здоровье', 'Пейте воду регулярно, чтобы поддерживать концентрацию.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Здоровье')
            """))
            db.execute(text("""
                INSERT INTO tips (category, tip)
                SELECT 'Мотивация', 'Разбейте большие задачи на маленькие шаги, чтобы не терять мотивацию.'
                WHERE NOT EXISTS (SELECT 1 FROM tips WHERE category = 'Мотивация')
            """))
            
            db.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def add_user(user_id: int, username: str, first_name: str):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (:user_id, :username, :first_name)
                ON CONFLICT (user_id) DO NOTHING
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

def add_goal(user_id: int, goal_name: str, goal_type: str, target_value: int, current_value: int, start_date: date, end_date: date):
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO goals (user_id, goal_name, goal_type, target_value, current_value, start_date, end_date)
                VALUES (:user_id, :goal_name, :goal_type, :target_value, :current_value, :start_date, :end_date)
            """), {
                'user_id': user_id,
                'goal_name': goal_name,
                'goal_type': goal_type,
                'target_value': target_value,
                'current_value': current_value,
                'start_date': start_date,
                'end_date': end_date
            })
            db.commit()
            logger.info(f"Added goal '{goal_name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Error adding goal for user {user_id}: {e}")
        raise

def update_goal_progress(user_id: int, goal_type: str, increment: int):
    try:
        with get_db() as db:
            db.execute(text("""
                UPDATE goals
                SET current_value = current_value + :increment
                WHERE user_id = :user_id AND goal_type = :goal_type AND is_completed = false
            """), {'user_id': user_id, 'goal_type': goal_type, 'increment': increment})
            db.execute(text("""
                UPDATE goals
                SET is_completed = true
                WHERE user_id = :user_id AND goal_type = :goal_type AND current_value >= target_value AND is_completed = false
            """), {'user_id': user_id, 'goal_type': goal_type})
            db.commit()
            logger.info(f"Updated goal progress for user {user_id}, type {goal_type}")
    except Exception as e:
        logger.error(f"Error updating goal progress for user {user_id}: {e}")
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
    try:
        with get_db() as db:
            db.execute(text("DELETE FROM daily_stats WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM sport_achievements WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM screen_activities WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM productive_activities WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM goals WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM habit_completions WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM habits WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM productivity_questions WHERE user_id = :user_id"), {'user_id': user_id})
            db.execute(text("DELETE FROM users WHERE user_id = :user_id"), {'user_id': user_id})
            db.commit()
            logger.info(f"Cleared all data for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing data for user {user_id}: {e}")
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
            # Проверка достижения "5 тренировок подряд"
            stmt = text("""
                SELECT COUNT(*) as streak
                FROM daily_stats
                WHERE user_id = :user_id
                AND stat_date > :start_date
                AND workout_done = 1
                AND is_rest_day = false
            """)
            streak = db.execute(stmt, {'user_id': user_id, 'start_date': date.today() - timedelta(days=5)}).first().streak
            if streak >= 5:
                db.execute(text("""
                    INSERT INTO sport_achievements (user_id, achievement_name, date_earned)
                    VALUES (:user_id, :achievement_name, :date_earned)
                    ON CONFLICT DO NOTHING
                """), {
                    'user_id': user_id,
                    'achievement_name': '5 тренировок подряд',
                    'date_earned': date.today()
                })
                logger.info(f"Awarded '5 workouts streak' achievement to user {user_id}")
            db.commit()
    except Exception as e:
        logger.error(f"Error checking achievements for user {user_id}: {e}")
        raise