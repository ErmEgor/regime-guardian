import os
import logging
from contextlib import contextmanager
from datetime import date

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

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
    pass

def add_user(user_id: int, username: str, first_name: str):
    try:
        with get_db() as db:
            stmt = text("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (:uid, :uname, :fname)
                ON CONFLICT (user_id) DO NOTHING
            """)
            db.execute(stmt, {'uid': user_id, 'uname': username or 'unknown', 'fname': first_name})
            db.commit()
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
        raise

def save_morning_plan(user_id: int, screen_time: int, workout: int, english: int, coding: int, planning: int, stretching: int, reflection: int, is_rest_day: bool = False):
    try:
        with get_db() as db:
            values = {
                'user_id': user_id, 'stat_date': date.today(), 'screen_time_goal': screen_time,
                'workout_planned': workout, 'english_planned': english, 'coding_planned': coding,
                'planning_planned': planning, 'stretching_planned': stretching, 'reflection_planned': reflection,
                'is_rest_day': is_rest_day
            }
            stmt = text("""
                INSERT INTO daily_stats (
                    user_id, stat_date, screen_time_goal,
                    workout_planned, workout_done,
                    english_planned, english_done,
                    coding_planned, coding_done,
                    planning_planned, planning_done,
                    stretching_planned, stretching_done,
                    reflection_planned, reflection_done,
                    morning_poll_completed, is_rest_day
                )
                VALUES (
                    :user_id, :stat_date, :screen_time_goal,
                    :workout_planned, 0,
                    :english_planned, 0,
                    :coding_planned, 0,
                    :planning_planned, 0,
                    :stretching_planned, 0,
                    :reflection_planned, 0,
                    :morning_poll_completed, :is_rest_day
                )
                ON CONFLICT (user_id, stat_date) DO UPDATE SET
                    screen_time_goal = :screen_time_goal,
                    workout_planned = :workout_planned,
                    english_planned = :english_planned,
                    coding_planned = :coding_planned,
                    planning_planned = :planning_planned,
                    stretching_planned = :stretching_planned,
                    reflection_planned = :reflection_planned,
                    is_rest_day = :is_rest_day,
                    morning_poll_completed = :morning_poll_completed
            """)
            db.execute(stmt, {**values, 'morning_poll_completed': not is_rest_day})
            db.commit()
    except Exception as e:
        logger.error(f"Error saving morning plan for user {user_id}: {e}")
        raise

def mark_activity_done(user_id: int, activity_type: str):
    try:
        with get_db() as db:
            stmt = text("""
                INSERT INTO daily_stats (
                    user_id, stat_date, screen_time_goal,
                    workout_planned, workout_done,
                    english_planned, english_done,
                    coding_planned, coding_done,
                    planning_planned, planning_done,
                    stretching_planned, stretching_done,
                    reflection_planned, reflection_done,
                    is_rest_day
                )
                VALUES (:uid, :today, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, false)
                ON CONFLICT DO NOTHING
            """)
            db.execute(stmt, {'uid': user_id, 'today': date.today()})
            
            column_name = f"{activity_type}_done"
            stmt = text(f"UPDATE daily_stats SET {column_name} = 1 WHERE user_id = :uid AND stat_date = :today")
            db.execute(stmt, {'uid': user_id, 'today': date.today()})
            db.commit()
    except Exception as e:
        logger.error(f"Error marking activity {activity_type} for user {user_id}: {e}")
        raise

def get_today_stats_for_user(user_id: int):
    try:
        with get_db() as db:
            stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
            result = db.execute(stmt, {'uid': user_id, 'today': date.today()}).first()
            return result._asdict() if result else None
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        raise

def get_today_screen_time(user_id: int):
    try:
        with get_db() as db:
            stmt = text("SELECT SUM(duration_minutes) FROM screen_activities WHERE user_id = :uid AND activity_date = :today")
            result = db.execute(stmt, {'uid': user_id, 'today': date.today()}).scalar_one_or_none()
            return result or 0
    except Exception as e:
        logger.error(f"Error getting screen time for user {user_id}: {e}")
        raise

def log_custom_activity(user_id: int, activity_name: str, duration_minutes: int):
    try:
        with get_db() as db:
            stmt = text("""
                INSERT INTO screen_activities (user_id, activity_date, activity_name, duration_minutes)
                VALUES (:uid, :date, :name, :duration)
            """)
            db.execute(stmt, {'uid': user_id, 'date': date.today(), 'name': activity_name, 'duration': duration_minutes})
            db.commit()
    except Exception as e:
        logger.error(f"Error logging activity for user {user_id}: {e}")
        raise

def log_productive_activity(user_id: int, activity_name: str, duration_minutes: int):
    try:
        with get_db() as db:
            stmt = text("""
                INSERT INTO productive_activities (user_id, activity_date, activity_name, duration_minutes)
                VALUES (:uid, :date, :name, :duration)
            """)
            db.execute(stmt, {'uid': user_id, 'date': date.today(), 'name': activity_name, 'duration': duration_minutes})
            db.commit()
    except Exception as e:
        logger.error(f"Error logging productive activity for user {user_id}: {e}")
        raise

def clear_user_data(user_id: int):
    try:
        with get_db() as db:
            db.execute(text("DELETE FROM screen_activities WHERE user_id = :uid"), {'uid': user_id})
            db.execute(text("DELETE FROM productive_activities WHERE user_id = :uid"), {'uid': user_id})
            db.execute(text("DELETE FROM daily_stats WHERE user_id = :uid"), {'uid': user_id})
            db.execute(text("DELETE FROM achievements WHERE user_id = :uid"), {'uid': user_id})
            db.execute(text("DELETE FROM users WHERE user_id = :uid"), {'uid': user_id})
            db.commit()
    except Exception as e:
        logger.error(f"Error clearing data for user {user_id}: {e}")
        raise