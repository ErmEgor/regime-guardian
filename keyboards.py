from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu_keyboard(include_settings: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отметить выполнение", callback_data="menu_mark_done")
    builder.button(text="✍️ Записать активность", callback_data="menu_log_activity")
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="🗑️ Очистить данные", callback_data="menu_clear_stats")
    if include_settings:
        builder.button(text="⚙️ Настройки", callback_data="menu_settings")
    builder.adjust(1)
    return builder.as_markup()

def get_mark_done_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="⚔️ Тренировка", callback_data="done_workout"),
            InlineKeyboardButton(text="🧘 Растяжка", callback_data="done_stretching")
        ],
        [
            InlineKeyboardButton(text="🎓 Английский", callback_data="done_english"),
            InlineKeyboardButton(text="🤔 Размышления", callback_data="done_reflection")
        ],
        [
            InlineKeyboardButton(text="💻 Кодинг", callback_data="done_coding"),
            InlineKeyboardButton(text="📝 План", callback_data="done_planning")
        ],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_clear_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🔴 Да, стереть всё", callback_data="confirm_clear_yes")],
        [InlineKeyboardButton(text="🟢 Отмена", callback_data="confirm_clear_no")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_morning_poll_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="< 2ч", callback_data="plan_time_2"),
            InlineKeyboardButton(text="< 3ч", callback_data="plan_time_3"),
            InlineKeyboardButton(text="< 4ч", callback_data="plan_time_4")
        ],
        [
            InlineKeyboardButton(text="⚔️ Тренировка", callback_data="plan_toggle_workout"),
            InlineKeyboardButton(text="🎓 Английский", callback_data="plan_toggle_english")
        ],
        [
            InlineKeyboardButton(text="💻 Кодинг", callback_data="plan_toggle_coding"),
            InlineKeyboardButton(text="📝 План", callback_data="plan_toggle_planning")
        ],
        [
            InlineKeyboardButton(text="🧘 Растяжка", callback_data="plan_toggle_stretching"),
            InlineKeyboardButton(text="🤔 Размышления", callback_data="plan_toggle_reflection")
        ],
        [InlineKeyboardButton(text="✅ Готово! Сохранить план", callback_data="plan_done")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stats_keyboard(webapp_url: str):
    buttons = [
        [InlineKeyboardButton(text="⚔️ Открыть Панель Командира", web_app=WebAppInfo(url=webapp_url))]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_timezone_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Asia/Almaty (UTC+5)", callback_data="tz_set_Asia/Almaty")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_settings_keyboard(current_tz: str):
    buttons = [
        [InlineKeyboardButton(text=f"Текущий пояс: {current_tz}", callback_data="inactive")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard():
    buttons = [
        [InlineKeyboardButton(text="« Отмена", callback_data="fsm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)