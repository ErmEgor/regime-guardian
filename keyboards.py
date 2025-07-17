from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from typing import Optional, List, Dict

def get_main_menu_keyboard(include_settings: bool = True) -> InlineKeyboardMarkup:
    """
    Создает основное меню бота с кнопками для всех функций, включая настройки (если включено).
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
        InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")
    )
    keyboard.add(
        InlineKeyboardButton("🎯 Цели", callback_data="menu_goals"),
        InlineKeyboardButton("📋 Привычки", callback_data="menu_habits")
    )
    keyboard.add(
        InlineKeyboardButton("💡 Советы", callback_data="menu_tips"),
        InlineKeyboardButton("✅ Отметить выполнение", callback_data="menu_mark_done")
    )
    keyboard.add(InlineKeyboardButton("📝 Записать активность", callback_data="menu_log_activity"))
    if include_settings:
        keyboard.add(InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"))
    keyboard.add(InlineKeyboardButton("🗑 Сбросить статистику", callback_data="menu_clear_stats"))
    return keyboard

def get_settings_keyboard(timezone: str) -> InlineKeyboardMarkup:
    """
    Создает меню настроек с текущей временной зоной.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(f"Часовой пояс: {timezone}", callback_data="settings_timezone"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_achievements_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает меню для работы с достижениями.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📜 Просмотреть", callback_data="achievements_view"),
        InlineKeyboardButton("➕ Добавить", callback_data="achievements_add")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_goals_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает меню для работы с целями.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📜 Просмотреть", callback_data="goals_view"),
        InlineKeyboardButton("➕ Добавить", callback_data="goals_add")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_habits_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает подменю для работы с привычками.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📜 Просмотреть", callback_data="habits_view"),
        InlineKeyboardButton("➕ Добавить", callback_data="habits_add")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_tips_categories_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с категориями советов.
    """
    categories = ["Продуктивность", "Здоровье", "Мотивация", "Саморазвитие"]
    keyboard = InlineKeyboardMarkup(row_width=2)
    for category in categories:
        keyboard.add(InlineKeyboardButton(category, callback_data=f"tip_category_{category}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_tips_by_category_keyboard(tips: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком советов для выбранной категории.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    for tip in tips:
        keyboard.add(InlineKeyboardButton(tip['title'], callback_data=f"tip_{tip['id']}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_tips"))
    return keyboard

def get_tip_content_keyboard(category: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для возврата к списку советов в категории.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Назад к советам", callback_data=f"tip_category_{category}"))
    keyboard.add(InlineKeyboardButton("🔙 В главное меню", callback_data="menu_back"))
    return keyboard

def get_goal_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа цели.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Еженедельная", callback_data="goal_type_weekly"),
        InlineKeyboardButton("Ежемесячная", callback_data="goal_type_monthly")
    )
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_goal_duration_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора длительности цели.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Неделя", callback_data="goal_duration_weekly"),
        InlineKeyboardButton("Месяц", callback_data="goal_duration_monthly")
    )
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_mark_done_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для отметки выполнения задач.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("🏋️ Тренировка", "done_workout"),
        ("🗣 Язык", "done_english"),
        ("💻 Программирование", "done_coding"),
        ("📝 Планирование", "done_planning"),
        ("🧘 Растяжка", "done_stretching"),
        ("🤔 Размышление", "done_reflection"),
        ("🚶 Прогулка", "done_walk")
    ]
    for text, callback in buttons:
        keyboard.add(InlineKeyboardButton(text, callback_data=callback))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_morning_day_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа дня.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Рабочий день", callback_data="plan_day_work"),
        InlineKeyboardButton("День отдыха", callback_data="plan_day_rest")
    )
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_morning_poll_keyboard(plan: Optional[Dict[str, Optional[int]]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для утреннего опроса.
    """
    keyboard = InlineKeyboardMarkup(row_width=3)
    time_buttons = [
        InlineKeyboardButton("2ч", callback_data="plan_time_2"),
        InlineKeyboardButton("3ч", callback_data="plan_time_3"),
        InlineKeyboardButton("4ч", callback_data="plan_time_4"),
        InlineKeyboardButton("5ч", callback_data="plan_time_5"),
        InlineKeyboardButton("6ч", callback_data="plan_time_6")
    ]
    keyboard.row(*time_buttons)
    habit_buttons = [
        InlineKeyboardButton("🏋️ Тренировка", callback_data="plan_toggle_workout"),
        InlineKeyboardButton("🗣 Язык", callback_data="plan_toggle_english"),
        InlineKeyboardButton("💻 Программирование", callback_data="plan_toggle_coding"),
        InlineKeyboardButton("📝 Планирование", callback_data="plan_toggle_planning"),
        InlineKeyboardButton("🧘 Растяжка", callback_data="plan_toggle_stretching"),
        InlineKeyboardButton("🤔 Размышление", callback_data="plan_toggle_reflection"),
        InlineKeyboardButton("🚶 Прогулка", callback_data="plan_toggle_walk")
    ]
    keyboard.add(*habit_buttons)
    keyboard.add(InlineKeyboardButton("✅ Готово", callback_data="plan_done"))
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_log_activity_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа активности (полезная/не полезная).
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📱 Не полезная", callback_data="log_type_screen"),
        InlineKeyboardButton("💪 Полезная", callback_data="log_type_productive")
    )
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_habit_answer_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для ответа на вопрос о выполнении привычки.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да", callback_data=f"habit_answer_{habit_id}_yes"),
        InlineKeyboardButton("❌ Нет", callback_data=f"habit_answer_{habit_id}_no")
    )
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard

def get_stats_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для перехода к статистике через веб-приложение.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            "📊 Открыть статистику",
            web_app=WebAppInfo(url=webapp_url)
        )
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
    return keyboard

def get_confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения сброса статистики.
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да", callback_data="confirm_clear_yes"),
        InlineKeyboardButton("❌ Нет", callback_data="confirm_clear_no")
    )
    return keyboard

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
    return keyboard