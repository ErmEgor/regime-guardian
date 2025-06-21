from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, StateFilter
import bot.db as db
import bot.keyboards as kb

# ⚠️ Убедитесь, что здесь ваш правильный URL от ngrok или домен
WEBAPP_URL = "https://917b-95-182-105-110.ngrok-free.app" 

router = Router()

class LogActivity(StatesGroup):
    choosing_activity_name = State()
    choosing_duration = State()

user_plans = {}

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    user_data = db.get_user(user_id)
    if user_data is None or 'timezone' not in user_data or not user_data['timezone']:
        await message.answer(
            "⚔️ Добро пожаловать, командир!\n\n"
            "Прежде чем мы начнем, выбери свой часовой пояс. Это нужно, чтобы я присылал напоминания вовремя.",
            reply_markup=kb.get_timezone_keyboard()
        )
    else:
        await message.answer(
            f"С возвращением, командир! Твой текущий часовой пояс: {user_data['timezone'].split('/')[-1]}.\n\n"
            "Используй /menu, чтобы отдать приказ.",
        )

@router.callback_query(F.data.startswith("tz_set_"))
async def cq_set_timezone(callback: CallbackQuery):
    timezone = callback.data.split("tz_set_")[1]
    db.set_user_timezone(callback.from_user.id, timezone)
    await callback.message.edit_text(
        f"✅ Отлично! Твой часовой пояс установлен: {timezone.split('/')[-1]}.\n\n"
        "Теперь ты можешь использовать главное меню. Нажми /menu, чтобы начать.",
        reply_markup=None
    )
    await callback.answer()

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    user_data = db.get_user(message.from_user.id)
    current_tz_db = user_data.get('timezone', "Не установлен") if user_data else "Не установлен"
    current_tz_display = current_tz_db.replace("_", " ").split("/")[-1]
    await message.answer("Меню настроек:", reply_markup=kb.get_settings_keyboard(current_tz_display))

@router.callback_query(F.data == "settings_change_tz")
async def cq_change_timezone(callback: CallbackQuery):
    await callback.message.edit_text("Выбери новый часовой пояс:", reply_markup=kb.get_timezone_keyboard())
    await callback.answer()

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=kb.get_main_menu_keyboard(include_settings=True))

@router.callback_query(F.data == "menu_settings")
async def cq_menu_settings(callback: CallbackQuery):
    user_data = db.get_user(callback.from_user.id)
    current_tz_db = user_data.get('timezone', "Не установлен") if user_data else "Не установлен"
    current_tz_display = current_tz_db.replace("_", " ").split("/")[-1]
    await callback.message.edit_text("Меню настроек:", reply_markup=kb.get_settings_keyboard(current_tz_display))
    await callback.answer()

@router.callback_query(F.data == "menu_mark_done")
async def cq_mark_done_menu(callback: CallbackQuery):
    await callback.message.edit_text("Какое достижение отметить?", reply_markup=kb.get_mark_done_keyboard())


# --- ИСПРАВЛЕНО: ВОТ ПРАВИЛЬНЫЙ И ЕДИНСТВЕННЫЙ ОБРАБОТЧИК СТАТИСТИКИ ---
@router.message(Command("stats"))
@router.callback_query(F.data == "menu_stats")
async def show_stats(update: Message | CallbackQuery):
    user_id = update.from_user.id
    user_webapp_url = f"{WEBAPP_URL}?user_id={user_id}"
    
    # Определяем, откуда пришел запрос, чтобы правильно ответить
    message_to_answer = update if isinstance(update, Message) else update.message
    
    await message_to_answer.answer(
        "Аналитические данные готовы, командир. Панель доступна по кнопке ниже.",
        reply_markup=kb.get_stats_keyboard(user_webapp_url)
    )
    
    # Отвечаем на колбэк, чтобы убрать "часики" с кнопки
    if isinstance(update, CallbackQuery):
        await update.answer()

@router.callback_query(F.data == "menu_back")
async def cq_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выберите действие:", reply_markup=kb.get_main_menu_keyboard(include_settings=True))

@router.callback_query(F.data.startswith("done_"))
async def cq_mark_activity_done(callback: CallbackQuery):
    activity_type = callback.data.split('_')[1]
    db.mark_activity_done(callback.from_user.id, activity_type)
    await callback.answer(f"✅ {activity_type.capitalize()} засчитано!", show_alert=True)

@router.message(Command("clear_stats"))
@router.callback_query(F.data == "menu_clear_stats")
async def cmd_clear_stats(update: Message | CallbackQuery):
    text = "Вы уверены, что хотите удалить ВСЕ свои данные безвозвратно? Это действие необратимо."
    markup = kb.get_confirm_clear_keyboard()
    message_to_edit = update.message if isinstance(update, CallbackQuery) else update
    await message_to_edit.answer(text, reply_markup=markup)
    if isinstance(update, CallbackQuery): await update.answer()

@router.callback_query(F.data == "confirm_clear_yes")
async def cq_confirm_clear(callback: CallbackQuery):
    db.clear_user_data(callback.from_user.id)
    await callback.message.edit_text("⚔️ Все ваши данные были стерты. Начнем с чистого листа. /start")

@router.callback_query(F.data == "confirm_clear_no")
async def cq_cancel_clear(callback: CallbackQuery):
    await callback.message.edit_text("Операция отменена. Возвращаю в главное меню.", reply_markup=kb.get_main_menu_keyboard(include_settings=True))

# --- РАБОЧИЙ БЛОК FSM ---
@router.callback_query(F.data == "fsm_cancel", StateFilter("*"))
async def cq_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await callback.message.delete()
        await callback.answer("Здесь нечего отменять.")
        return
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено. Возвращаю в главное меню.",
        reply_markup=kb.get_main_menu_keyboard(include_settings=True)
    )
    await callback.answer()

@router.message(Command("log"))
@router.callback_query(F.data == "menu_log_activity")
async def start_log_activity(update: Message | CallbackQuery, state: FSMContext):
    message_to_use = update.message if isinstance(update, CallbackQuery) else update
    await message_to_use.answer("Какую активность вы хотите записать? (например: YouTube, Соцсети)", reply_markup=kb.get_cancel_keyboard())
    await state.set_state(LogActivity.choosing_activity_name)
    if isinstance(update, CallbackQuery): await update.answer()

@router.message(StateFilter(LogActivity.choosing_activity_name))
async def activity_name_chosen(message: Message, state: FSMContext):
    await state.update_data(activity_name=message.text)
    await message.answer("Сколько минут это заняло? Введите только число.", reply_markup=kb.get_cancel_keyboard())
    await state.set_state(LogActivity.choosing_duration)

@router.message(StateFilter(LogActivity.choosing_duration))
async def duration_chosen(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("Ошибка. Пожалуйста, введите число (количество минут).", reply_markup=kb.get_cancel_keyboard())
        return
    
    user_data = await state.get_data()
    activity_name = user_data.get('activity_name', 'Неизвестная активность')
    duration_minutes = int(message.text)
    
    db.log_custom_activity(message.from_user.id, activity_name, duration_minutes)
    
    await message.answer(f"Записано: '{activity_name}' - {duration_minutes} мин.")
    await state.clear()
    await message.answer("Главное меню:", reply_markup=kb.get_main_menu_keyboard(include_settings=True))

# --- Логика утреннего опроса ---
@router.callback_query(F.data.startswith("plan_"))
async def handle_morning_plan(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data.split('_')
    if user_id not in user_plans:
        user_plans[user_id] = {'time': None, 'workout': 0, 'english': 0, 'coding': 0, 'planning': 0, 'stretching': 0, 'reflection': 0}

    if action[1] == 'time':
        user_plans[user_id]['time'] = int(action[2])
        await callback.answer(f"Лимит времени: < {action[2]}ч")
    elif action[1] == 'toggle':
        habit = action[2]
        current_status = user_plans[user_id][habit]
        user_plans[user_id][habit] = 1 - current_status
        status_text = "в планах" if user_plans[user_id][habit] == 1 else "не в планах"
        await callback.answer(f"{habit.capitalize()} {status_text}")
    elif action[1] == 'done':
        plan = user_plans.get(user_id)
        if plan is None or plan['time'] is None:
            await callback.answer("Пожалуйста, выберите лимит времени.", show_alert=True)
            return
        
        db.save_morning_plan(
            user_id, plan['time'], plan['workout'], plan['english'], plan['coding'],
            plan['planning'], plan['stretching'], plan['reflection']
        )
        del user_plans[user_id]
        await callback.message.edit_text("⚔️ План на день сохранён. Продуктивного дня, командир!")
        await callback.answer()

@router.message(Command("morning"))
async def cmd_morning_test(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in user_plans:
        del user_plans[user_id]
    await message.answer("☀️ Тестовый запуск утреннего опроса. Составьте план на сегодня:", reply_markup=kb.get_morning_poll_keyboard())