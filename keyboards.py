import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from typing import Optional, List, Dict

# Настройка логирования
logger = logging.getLogger(__name__)

def get_main_menu_keyboard(include_settings: bool = True) -> InlineKeyboardMarkup:
    """
    Создает основное меню бота с кнопками для всех функций, включая настройки (если включено).
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = [
            ("📊 Статистика", "menu_stats"),
            ("🏆 Достижения", "menu_achievements"),
            ("🎯 Цели", "menu_goals"),
            ("📋 Привычки", "menu_habits"),
            ("💡 Советы", "menu_tips"),
            ("✅ Отметить выполнение", "menu_mark_done"),
            ("📝 Записать активность", "menu_log_activity"),
        ]
        if include_settings:
            buttons.append(("⚙️ Настройки", "menu_settings"))
        buttons.append(("🗑 Сбросить статистику", "menu_clear_stats"))

        for text, callback_data in buttons:
            if not text or not callback_data:
                logger.error(f"Invalid button data: text='{text}', callback_data='{callback_data}'")
                raise ValueError("Button text or callback_data is empty")
            keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))
            logger.debug(f"Added button: {text} with callback_data: {callback_data}")

        logger.info("Main menu keyboard created successfully")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating main menu keyboard: {e}")
        raise

def get_settings_keyboard(timezone: str) -> InlineKeyboardMarkup:
    """
    Создает меню настроек с текущей временной зоной.
    """
    try:
        if not timezone:
            logger.error("Timezone is empty or None")
            raise ValueError("Timezone cannot be empty")
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton(f"Часовой пояс: {timezone}", callback_data="settings_timezone"))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug(f"Settings keyboard created with timezone: {timezone}")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating settings keyboard: {e}")
        raise

def get_achievements_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает меню для работы с достижениями.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📜 Просмотреть", callback_data="achievements_view"),
            InlineKeyboardButton("➕ Добавить", callback_data="achievements_add")
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug("Achievements menu keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating achievements menu keyboard: {e}")
        raise

def get_goals_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает меню для работы с целями.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📜 Просмотреть", callback_data="goals_view"),
            InlineKeyboardButton("➕ Добавить", callback_data="goals_add")
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug("Goals menu keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating goals menu keyboard: {e}")
        raise

def get_habits_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает подменю для работы с привычками.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📜 Просмотреть", callback_data="habits_view"),
            InlineKeyboardButton("➕ Добавить", callback_data="habits_add")
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug("Habits menu keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating habits menu keyboard: {e}")
        raise

def get_tips_categories_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с категориями советов.
    """
    try:
        categories = ["Продуктивность", "Здоровье", "Мотивация", "Саморазвитие"]
        keyboard = InlineKeyboardMarkup(row_width=2)
        for category in categories:
            if not category:
                logger.error("Empty category name detected")
                raise ValueError("Category name cannot be empty")
            keyboard.add(InlineKeyboardButton(category, callback_data=f"tip_category_{category}"))
            logger.debug(f"Added tip category button: {category}")
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug("Tips categories keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating tips categories keyboard: {e}")
        raise

def get_tips_by_category_keyboard(tips: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком советов для выбранной категории.
    """
    try:
        if not tips:
            logger.error("Tips list is empty")
            raise ValueError("Tips list cannot be empty")
        keyboard = InlineKeyboardMarkup(row_width=1)
        for tip in tips:
            title = tip.get('title')
            tip_id = tip.get('id')
            if not title or not tip_id:
                logger.error(f"Invalid tip data: title='{title}', id='{tip_id}'")
                raise ValueError("Tip title or id is missing")
            keyboard.add(InlineKeyboardButton(title, callback_data=f"tip_{tip_id}"))
            logger.debug(f"Added tip button: {title} with id: {tip_id}")
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_tips"))
        logger.debug("Tips by category keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating tips by category keyboard: {e}")
        raise

def get_tip_content_keyboard(category: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для возврата к списку советов в категории.
    """
    try:
        if not category:
            logger.error("Category is empty or None")
            raise ValueError("Category cannot be empty")
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад к советам", callback_data=f"tip_category_{category}"))
        keyboard.add(InlineKeyboardButton("🔙 В главное меню", callback_data="menu_back"))
        logger.debug(f"Tip content keyboard created for category: {category}")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating tip content keyboard: {e}")
        raise

def get_goal_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа цели.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Еженедельная", callback_data="goal_type_weekly"),
            InlineKeyboardButton("Ежемесячная", callback_data="goal_type_monthly")
        )
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug("Goal type keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating goal type keyboard: {e}")
        raise

def get_goal_duration_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора длительности цели.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Неделя", callback_data="goal_duration_weekly"),
            InlineKeyboardButton("Месяц", callback_data="goal_duration_monthly")
        )
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug("Goal duration keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating goal duration keyboard: {e}")
        raise

def get_mark_done_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для отметки выполнения задач.
    """
    try:
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
            if not text or not callback:
                logger.error(f"Invalid button data: text='{text}', callback_data='{callback}'")
                raise ValueError("Button text or callback_data is empty")
            keyboard.add(InlineKeyboardButton(text=text, callback_data=callback))
            logger.debug(f"Added mark done button: {text} with callback_data: {callback}")
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug(f"Mark done keyboard created for user_id: {user_id}")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating mark done keyboard: {e}")
        raise

def get_morning_day_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа дня.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Рабочий день", callback_data="plan_day_work"),
            InlineKeyboardButton("День отдыха", callback_data="plan_day_rest")
        )
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug("Morning day type keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating morning day type keyboard: {e}")
        raise

def get_morning_poll_keyboard(plan: Optional[Dict[str, Optional[int]]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для утреннего опроса.
    """
    try:
        if not plan:
            logger.error("Plan is None or empty")
            raise ValueError("Plan cannot be None or empty")
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
        logger.debug("Morning poll keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating morning poll keyboard: {e}")
        raise

def get_log_activity_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа активности (полезная/не полезная).
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📱 Не полезная", callback_data="log_type_screen"),
            InlineKeyboardButton("💪 Полезная", callback_data="log_type_productive")
        )
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug("Log activity type keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating log activity type keyboard: {e}")
        raise

def get_habit_answer_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для ответа на вопрос о выполнении привычки.
    """
    try:
        if not habit_id:
            logger.error("Habit ID is empty or None")
            raise ValueError("Habit ID cannot be empty")
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data=f"habit_answer_{habit_id}_yes"),
            InlineKeyboardButton("❌ Нет", callback_data=f"habit_answer_{habit_id}_no")
        )
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug(f"Habit answer keyboard created for habit_id: {habit_id}")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating habit answer keyboard: {e}")
        raise

def get_stats_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для перехода к статистике через веб-приложение.
    """
    try:
        if not webapp_url:
            logger.error("Webapp URL is empty or None")
            raise ValueError("Webapp URL cannot be empty")
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton(
                "📊 Открыть статистику",
                web_app=WebAppInfo(url=webapp_url)
            )
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_back"))
        logger.debug(f"Stats keyboard created with webapp_url: {webapp_url}")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating stats keyboard: {e}")
        raise

def get_confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения сброса статистики.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data="confirm_clear_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="confirm_clear_no")
        )
        logger.debug("Confirm clear keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating confirm clear keyboard: {e}")
        raise

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены.
    """
    try:
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="fsm_cancel"))
        logger.debug("Cancel keyboard created")
        return keyboard
    except Exception as e:
        logger.error(f"Error creating cancel keyboard: {e}")
        raise