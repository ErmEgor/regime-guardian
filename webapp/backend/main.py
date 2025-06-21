import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import date, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Модель для одного дня в истории
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

# Модель для сегодняшнего дня
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

# Главная модель ответа API (теперь включает историю)
class UserStatsResponse(BaseModel):
    user_id: int
    today: TodayStats
    history: List[HistoryDayStats]

def get_db_connection():
    conn = sqlite3.connect('../../database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/stats/{user_id}", response_model=UserStatsResponse)
def read_user_stats(user_id: int):
    conn = get_db_connection()
    try:
        today_iso = date.today().isoformat()
        
        # --- БЛОК ДАННЫХ ЗА СЕГОДНЯ (остается без изменений) ---
        today_main_stats = conn.execute(
            "SELECT * FROM daily_stats WHERE user_id = ? AND stat_date = ?", (user_id, today_iso)
        ).fetchone()
        
        if not today_main_stats:
            raise HTTPException(status_code=404, detail="План на сегодня не найден. Вы прошли утренний опрос?")

        today_activities = conn.execute(
            "SELECT activity_name, duration_minutes FROM screen_activities WHERE user_id = ? AND activity_date = ?", (user_id, today_iso)
        ).fetchall()
        
        breakdown = {row['activity_name']: row['duration_minutes'] for row in today_activities}
        total_minutes_today = sum(breakdown.values())

        today_data = TodayStats(
            screen_time_goal=today_main_stats['screen_time_goal'],
            screen_time_actual=total_minutes_today,
            screen_time_breakdown=breakdown,
            workout_planned=today_main_stats['workout_planned'],
            workout_done=today_main_stats['workout_done'],
            english_planned=today_main_stats['english_planned'],
            english_done=today_main_stats['english_done'],
            coding_planned=today_main_stats['coding_planned'],
            coding_done=today_main_stats['coding_done'],
            planning_planned=today_main_stats['planning_planned'],
            planning_done=today_main_stats['planning_done'],
            stretching_planned=today_main_stats['stretching_planned'],
            stretching_done=today_main_stats['stretching_done'],
            reflection_planned=today_main_stats['reflection_planned'],
            reflection_done=today_main_stats['reflection_done'],
        )
        
        # --- ДОБАВЛЕН БЛОК: ИСТОРИЯ ЗА НЕДЕЛЮ ---
        history_data = []
        seven_days_ago = date.today() - timedelta(days=7)
        
        history_main_stats = conn.execute("""
            SELECT * FROM daily_stats WHERE user_id = ? AND stat_date >= ? AND stat_date < ? ORDER BY stat_date DESC
        """, (user_id, seven_days_ago.isoformat(), today_iso)).fetchall()
        
        history_screen_time = conn.execute("""
            SELECT activity_date, SUM(duration_minutes) as total_minutes
            FROM screen_activities WHERE user_id = ? AND activity_date >= ? AND activity_date < ? GROUP BY activity_date
        """, (user_id, seven_days_ago.isoformat(), today_iso)).fetchall()
        
        screen_time_map = {row['activity_date']: row['total_minutes'] for row in history_screen_time}

        for day_stats in history_main_stats:
            stat_date = day_stats['stat_date']
            history_data.append(HistoryDayStats(
                date=stat_date,
                screen_time_goal=day_stats['screen_time_goal'],
                screen_time_actual=screen_time_map.get(stat_date, 0),
                workout_done=day_stats['workout_done'],
                english_done=day_stats['english_done'],
                coding_done=day_stats['coding_done'],
                planning_done=day_stats['planning_done'],
                stretching_done=day_stats['stretching_done'],
                reflection_done=day_stats['reflection_done'],
            ))

        # Возвращаем и 'today', и 'history'
        return UserStatsResponse(user_id=user_id, today=today_data, history=history_data)
        
    finally:
        conn.close()