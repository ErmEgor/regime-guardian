from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date
from sqlalchemy import text
from db import get_db
import logging
from typing import Optional, List, Dict

# Настройка логирования
logger = logging.getLogger(__name__)

def get_main_menu_keyboard(include_settings: bool = False) -> InlineKeyboardMarkup:
    """
    Создает основное меню бота с кнопками для всех функций, включая настройки (если включено).
    """
    logger.debug("Creating main menu keyboard")
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отметить выполнение", callback_data="menu_mark_done")
    builder.button(text="✍️ Записать активность", callback_data="menu_log_activity")
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="🏆 Достижения", callback_data="menu_achievements")
    builder.button(text="📋 Привычки", callback_data="menu_habits")
    builder.button(text="💡 Советы", callback_data="menu_tips")
    builder.button(text="🗑️ Очистить данные", callback_data="menu_clear_stats")
    if include_settings:
        builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.adjust(1)
    logger.debug("Main menu keyboard created successfully")
    return builder.as_markup()

def get_achievements_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает меню для работы с достижениями.
    """
    logger.debug("Creating achievements menu keyboard")
    buttons = [
        [InlineKeyboardButton(text="📜 Просмотреть достижения", callback_data="achievements_view")],
        [InlineKeyboardButton(text="✍️ Добавить достижение", callback_data="achievements_add")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_habits_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает подменю для работы с привычками.
    """
    logger.debug("Creating habits menu keyboard")
    buttons = [
        [InlineKeyboardButton(text="📜 Просмотреть привычки", callback_data="habits_view")],
        [InlineKeyboardButton(text="✍️ Добавить привычку", callback_data="habits_add")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_goals_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает подменю для работы с целями.
    """
    logger.debug("Creating goals menu keyboard")
    buttons = [
        [InlineKeyboardButton(text="📜 Просмотреть цели", callback_data="goals_view")],
        [InlineKeyboardButton(text="✍️ Добавить цель", callback_data="goals_add")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tips_categories_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с категориями советов.
    """
    logger.debug("Creating tips categories keyboard")
    categories = ["Продуктивность", "Здоровье", "Мотивация", "Саморазвитие"]
    buttons = [[InlineKeyboardButton(text=category, callback_data=f"tip_category_{category}")] for category in categories]
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tips_by_category_keyboard(tips: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком советов для выбранной категории.
    """
    logger.debug("Creating tips by category keyboard")
    buttons = [[InlineKeyboardButton(text=tip['title'], callback_data=f"tip_{tip['id']}")] for tip in tips]
    buttons.append([InlineKeyboardButton(text="« Назад к категориям", callback_data="menu_tips")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_tip_content_keyboard(category: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для возврата к списку советов в категории.
    """
    logger.debug(f"Creating tip content keyboard for category: {category}")
    buttons = [
        [InlineKeyboardButton(text="« Назад к советам", callback_data=f"tip_category_{category}")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_log_activity_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа активности (полезная/не полезная).
    """
    logger.debug("Creating log activity type keyboard")
    buttons = [
        [InlineKeyboardButton(text="📱 Не полезная", callback_data="log_type_screen")],
        [InlineKeyboardButton(text="💡 Полезная", callback_data="log_type_productive")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_mark_done_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для отметки выполнения задач.
    """
    try:
        logger.debug(f"Creating mark done keyboard for user_id: {user_id}")
        with get_db() as db_session:
            stmt = text("SELECT * FROM daily_stats WHERE user_id = :uid AND stat_date = :today")
            result = db_session.execute(stmt, {'uid': user_id, 'today': date.today()}).first()
            if not result:
                logger.debug(f"No daily stats found for user_id: {user_id}")
                return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]])
            stats = result._asdict()
            buttons = []
            activities = [
                ('workout', '⚔️ Тренировка', 'done_workout'),
                ('stretching', '🧘 Растяжка', 'done_stretching'),
                ('english', '🎓 Язык', 'done_english'),
                ('reflection', '🤔 Размышления', 'done_reflection'),
                ('coding', '💻 Кодинг', 'done_coding'),
                ('planning', '📝 План', 'done_planning'),
                ('walk', '🚶 Прогулка', 'done_walk'),
            ]
            row = []
            for key, label, callback in activities:
                if stats.get(f"{key}_planned", 0) == 1:
                    row.append(InlineKeyboardButton(text=label, callback_data=callback))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")])
            logger.debug("Mark done keyboard created successfully")
            return InlineKeyboardMarkup(inline_keyboard=buttons)
    except Exception as e:
        logger.error(f"Error generating mark done keyboard for user_id {user_id}: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]])

def get_confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения сброса статистики.
    """
    logger.debug("Creating confirm clear keyboard")
    buttons = [
        [InlineKeyboardButton(text="🔴 Да, стереть всё", callback_data="confirm_clear_yes")],
        [InlineKeyboardButton(text="🟢 Отмена", callback_data="confirm_clear_no")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_morning_day_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа дня.
    """
    logger.debug("Creating morning day type keyboard")
    buttons = [
        [InlineKeyboardButton(text="🏖️ Отдых", callback_data="plan_day_rest")],
        [InlineKeyboardButton(text="💼 Будни", callback_data="plan_day_workday")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_morning_poll_keyboard(user_plan: dict = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для утреннего опроса.
    """
    logger.debug("Creating morning poll keyboard")
    if user_plan is None:
        user_plan = {
            'time': None,
            'workout': 0,
            'english': 0,
            'coding': 0,
            'planning': 0,
            'stretching': 0,
            'reflection': 0,
            'walk': 0
        }
    buttons = [
        [InlineKeyboardButton(text="Экранное время", callback_data="inactive")],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['time'] == 4*60 else ''}4ч",
                callback_data="plan_time_4"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['time'] == 5*60 else ''}5ч",
                callback_data="plan_time_5"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['time'] == 6*60 else ''}6ч",
                callback_data="plan_time_6"
            )
        ],
        [InlineKeyboardButton(text="Главные активности", callback_data="inactive")],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['workout'] else ''}⚔️ Тренировка",
                callback_data="plan_toggle_workout"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['english'] else ''}🎓 Язык",
                callback_data="plan_toggle_english"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['coding'] else ''}💻 Кодинг",
                callback_data="plan_toggle_coding"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['planning'] else ''}📝 План",
                callback_data="plan_toggle_planning"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['stretching'] else ''}🧘 Растяжка",
                callback_data="plan_toggle_stretching"
            ),
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['reflection'] else ''}🤔 Размышления",
                callback_data="plan_toggle_reflection"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if user_plan['walk'] else ''}🚶 Прогулка",
                callback_data="plan_toggle_walk"
            )
        ],
        [InlineKeyboardButton(text="✅ Готово! Сохранить план", callback_data="plan_done")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stats_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для перехода к статистике через веб-приложение.
    """
    logger.debug(f"Creating stats keyboard with webapp_url: {webapp_url}")
    buttons = [
        [InlineKeyboardButton(text="⚔️ Открыть Панель Командира", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора часового пояса.
    """
    logger.debug("Creating timezone keyboard")
    buttons = [
        [InlineKeyboardButton(text="Asia/Almaty (UTC+5)", callback_data="tz_set_Asia/Almaty")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_settings_keyboard(current_tz: str) -> InlineKeyboardMarkup:
    """
    Создает меню настроек с текущей временной зоной.
    """
    logger.debug(f"Creating settings keyboard with timezone: {current_tz}")
    buttons = [
        [InlineKeyboardButton(text=f"Текущий пояс: {current_tz or 'Не установлен'}", callback_data="inactive")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены.
    """
    logger.debug("Creating cancel keyboard")
    buttons = [
        [InlineKeyboardButton(text="« Отмена", callback_data="fsm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_goal_answer_keyboard(goal_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для ответа на вопрос о выполнении цели.
    """
    logger.debug(f"Creating goal answer keyboard for goal_id: {goal_id}")
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"goal_answer_{goal_id}_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"goal_answer_{goal_id}_no")
        ],
        [InlineKeyboardButton(text="« Отмена", callback_data="fsm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_goal_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора типа цели (ежедневная или еженедельная).
    """
    logger.debug("Creating goal type keyboard")
    buttons = [
        [InlineKeyboardButton(text="Ежедневная", callback_data="goal_type_daily")],
        [InlineKeyboardButton(text="Еженедельная", callback_data="goal_type_weekly")],
        [InlineKeyboardButton(text="« Отмена", callback_data="fsm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_goal_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения создания цели.
    """
    logger.debug("Creating goal confirm keyboard")
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="goal_confirm")],
        [InlineKeyboardButton(text="« Отмена", callback_data="fsm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)