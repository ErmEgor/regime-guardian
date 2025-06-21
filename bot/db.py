import sqlite3
from datetime import date

def init_db():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # ОБНОВЛЕНО: Добавлено поле timezone
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        timezone TEXT 
    )""")
    
     # ОБНОВЛЕНО: Добавлены растяжка и размышления
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stat_date TEXT,
        screen_time_goal INTEGER,
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
        UNIQUE(user_id, stat_date)
    )""")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS screen_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        activity_date TEXT,
        activity_name TEXT,
        duration_minutes INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        achievement_name TEXT,
        date_earned TEXT
    )""")

    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name))
    conn.commit()
    conn.close()

# НОВАЯ ФУНКЦИЯ: Установить часовой пояс
def set_user_timezone(user_id, timezone):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (timezone, user_id))
    conn.commit()
    conn.close()

# НОВАЯ ФУНКЦИЯ: Получить данные пользователя, включая пояс
def get_user(user_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Преобразуем sqlite3.Row в обычный словарь, если он не None
    return dict(user_row) if user_row else None

# НОВАЯ ФУНКЦИЯ: Получить всех пользователей с их поясами
def get_all_users_with_tz():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT user_id, timezone FROM users")
    users = cur.fetchall()
    conn.close()
    return users

# НОВАЯ ФУНКЦИЯ: для записи кастомной активности
def log_custom_activity(user_id, activity_name, duration_minutes):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute(
        "INSERT INTO screen_activities (user_id, activity_date, activity_name, duration_minutes) VALUES (?, ?, ?, ?)",
        (user_id, today, activity_name, duration_minutes)
    )
    conn.commit()
    conn.close()

# НОВАЯ ФУНКЦИЯ: для очистки статистики
def clear_user_data(user_id):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM daily_stats WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM screen_activities WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM achievements WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ОБНОВЛЕНА: Используем более надежный метод сохранения
def save_morning_plan(user_id, screen_time, workout, english, coding, planning, stretching, reflection):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    today = date.today().isoformat()
    
    # Этот запрос атомарный: он либо вставляет новую строку, либо, если
    # строка с такой датой и user_id уже существует, он обновляет её.
    # Это решает проблему в один шаг.
    cur.execute("""
    INSERT INTO daily_stats (
        user_id, stat_date, screen_time_goal, workout_planned, english_planned, 
        coding_planned, planning_planned, stretching_planned, reflection_planned
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id, stat_date) DO UPDATE SET
        screen_time_goal = excluded.screen_time_goal,
        workout_planned = excluded.workout_planned,
        english_planned = excluded.english_planned,
        coding_planned = excluded.coding_planned,
        planning_planned = excluded.planning_planned,
        stretching_planned = excluded.stretching_planned,
        reflection_planned = excluded.reflection_planned
    """, (
        user_id, today, screen_time, workout, english, coding, 
        planning, stretching, reflection
    ))
    
    conn.commit()
    conn.close()

# НОВАЯ ФУНКЦИЯ: получить суммарное экранное время за сегодня
def get_today_screen_time(user_id):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute(
        "SELECT SUM(duration_minutes) FROM screen_activities WHERE user_id = ? AND activity_date = ?",
        (user_id, today)
    )
    result = cur.fetchone()[0]
    conn.close()
    return result if result is not None else 0
    
# ОБНОВЛЕНА: отметка выполнения
def mark_activity_done(user_id, activity_type):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    today = date.today().isoformat()
    # Убедимся, что запись на сегодня существует
    cur.execute("INSERT OR IGNORE INTO daily_stats (user_id, stat_date) VALUES (?, ?)", (user_id, today))
    column_name = f"{activity_type}_done"
    cur.execute(f"UPDATE daily_stats SET {column_name} = 1 WHERE user_id = ? AND stat_date = ?", (user_id, today))
    conn.commit()
    conn.close()

def get_today_stats_for_user(user_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute("SELECT * FROM daily_stats WHERE user_id = ? AND stat_date = ?", (user_id, today))
    stats = cur.fetchone()
    conn.close()
    return stats

def get_all_users():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    return users