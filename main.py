import asyncio
import json
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Загружаем переменные окружения из .env файла
load_dotenv()

logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")

# --- БЕЛЫЙ СПИСОК ПОЛЬЗОВАТЕЛЕЙ (разрешены только эти user_id) ---
ALLOWED_USERS = [
    7118929376,     # Artem личный тема
    1428288113,     # Artem основной (@A_rtemK)
    8481047835,     # Майя (@poqqg)
]

# Соответствие между user_id и именами
USER_NAMES = {
    7118929376: "Тёма",
    1428288113: "Артём",
    8481047835: "Майя",
}

logging.info(f"🔧 TELEGRAM_TOKEN set: {bool(TELEGRAM_TOKEN)}")
logging.info(f"🔧 OPENROUTER_KEY set: {bool(OPENROUTER_KEY)}")

if not TELEGRAM_TOKEN or not OPENROUTER_KEY:
    logging.error("❌ Missing TELEGRAM_TOKEN or OPENROUTER_KEY environment variables!")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# OpenRouter API configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class MyStates(StatesGroup):
    waiting_for_wish = State()
    waiting_for_quote = State()
    waiting_for_ai = State()
    deleting_wish = State()
    deleting_quote = State()
    selecting_message_recipient = State()
    waiting_for_secret_message = State()
    setting_relationship_date = State()
    adding_memory = State()

# --- РАБОТА С ДАННЫМИ ---
def get_data(name):
    """Получить все данные из JSON файла"""
    try:
        with open(f"{name}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logging.error(f"❌ JSON corrupted in {name}.json, returning empty dict")
        return {}

def save_data(name, data):
    """Сохранить данные в JSON файл"""
    try:
        with open(f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"❌ Failed to save {name}.json: {e}")
        raise

def get_user_wishes(user_id):
    """Получить хотелки конкретного пользователя"""
    data = get_data("wishlist")
    return data.get(str(user_id), [])

def get_user_quotes(user_id):
    """Получить цитаты конкретного пользователя"""
    data = get_data("quotes")
    return data.get(str(user_id), [])

def add_wish(user_id, wish_text):
    """Добавить хотелку пользователю"""
    data = get_data("wishlist")
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = []
    data[user_id_str].append(wish_text)
    save_data("wishlist", data)

def add_quote(user_id, quote_text):
    """Добавить цитату пользователю"""
    data = get_data("quotes")
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = []
    data[user_id_str].append(quote_text)
    save_data("quotes", data)

def delete_wish(user_id, idx):
    """Удалить хотелку пользователя по индексу"""
    data = get_data("wishlist")
    user_id_str = str(user_id)
    if user_id_str in data and 0 <= idx < len(data[user_id_str]):
        data[user_id_str].pop(idx)
        save_data("wishlist", data)
        return True
    return False

def delete_quote(user_id, idx):
    """Удалить цитату пользователя по индексу"""
    data = get_data("quotes")
    user_id_str = str(user_id)
    if user_id_str in data and 0 <= idx < len(data[user_id_str]):
        data[user_id_str].pop(idx)
        save_data("quotes", data)
        return True
    return False

def get_relationship_date():
    """Получить дату начала отношений"""
    try:
        with open("relationship.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("start_date")
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        logging.error("❌ JSON corrupted in relationship.json")
        return None

def set_relationship_date(date_str):
    """Установить дату начала отношений (формат: YYYY-MM-DD)"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        data = {"start_date": date_str}
        with open("relationship.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except ValueError:
        return False
    except IOError as e:
        logging.error(f"❌ Failed to save relationship.json: {e}")
        return False

def calculate_relationship_stats():
    """Вычислить статистику отношений"""
    start_date_str = get_relationship_date()
    if not start_date_str:
        return None
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        today = datetime.now()
        days_together = (today - start_date).days
        
        months = days_together // 30
        remaining_days = days_together % 30
        
        return {
            "days": days_together,
            "months": months,
            "days_in_month": remaining_days,
            "start_date": start_date_str,
            "formatted_date": start_date.strftime("%d.%m.%y")
        }
    except ValueError:
        return None

def add_memory(memory_text):
    """Добавить воспоминание"""
    try:
        data = get_data("memories")
        if "memories_list" not in data:
            data["memories_list"] = []
        
        memory_entry = {
            "text": memory_text,
            "date": datetime.now().strftime("%d.%m.%y %H:%M")
        }
        data["memories_list"].append(memory_entry)
        save_data("memories", data)
        return True
    except Exception as e:
        logging.error(f"❌ Error saving memory: {e}")
        return False

def get_memories():
    """Получить все воспоминания"""
    data = get_data("memories")
    return data.get("memories_list", [])

def delete_memory(idx):
    """Удалить воспоминание по индексу"""
    data = get_data("memories")
    if "memories_list" in data and 0 <= idx < len(data["memories_list"]):
        data["memories_list"].pop(idx)
        save_data("memories", data)
        return True
    return False

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✨ Факт про Майю")
    builder.button(text="🎁 В виш-лист")
    builder.button(text="🤣 В цитаты")
    builder.button(text="🤖 Спросить ИИ")
    builder.button(text="💌 Тайное сообщение")
    builder.button(text="📂 Посмотреть списки")
    builder.button(text="� Отношения")
    builder.button(text="📸 Воспоминания")
    builder.button(text="�🗑️ Удалить элемент")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

# --- АСИНХРОННЫЙ ВЫЗОВ ИИ (не блокирует цикл событий) ---
async def call_ai(prompt):
    """Вызывает OpenRouter в отдельном потоке."""
    def sync_call():
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "MayaBot"
        }
        data = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            logging.info(f"📤 Sending request to OpenRouter...")
            response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
            logging.info(f"📥 Response status: {response.status_code}")
            
            if response.status_code != 200:
                logging.error(f"❌ OpenRouter error {response.status_code}: {response.text}")
                return None
            
            result = response.json()
            if "choices" not in result:
                logging.error(f"❌ Unexpected response format: {result}")
                return None
                
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logging.error(f"❌ AI error: {type(e).__name__}: {e}")
            return None
    
    try:
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        logging.error(f"❌ AI thread error: {e}")
        return None

# --- ПРОВЕРКА ДОСТУПА ---
async def check_access(message: types.Message) -> bool:
    """Проверяет, разрешён ли доступ пользователю."""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    
    if user_id not in ALLOWED_USERS:
        logging.warning(f"🚫 DENIED access for user {user_id} (@{username})")
        await message.answer("❌ У вас нет доступа к этому боту. Доступ разрешен только для определённых пользователей.")
        return False
    
    logging.info(f"✅ ALLOWED access for user {user_id} (@{username})")
    return True

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    logging.info(f"🆔 USER_ID: {user_id} | Username: @{username}")
    await state.clear()
    await message.answer("Бот запущен! Что хочешь сделать?", reply_markup=main_menu())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not await check_access(message):
        return
    help_text = """
📚 <b>Доступные команды:</b>

✨ <b>Факт про Майю</b> - случайный позитивный факт
🎁 <b>В виш-лист</b> - добавить желание
🤣 <b>В цитаты</b> - сохранить интересную цитату
🤖 <b>Спросить ИИ</b> - спросить что-нибудь у ИИ
💌 <b>Тайное сообщение</b> - отправить скрытое сообщение
📂 <b>Посмотреть списки</b> - показать все желания и цитаты
🗑️ <b>Удалить элемент</b> - удалить желание или цитату

/start - главное меню
/help - эта справка
"""
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    await message.answer("Вернулся в главное меню!", reply_markup=main_menu())

# 1. ФАКТ
@dp.message(F.text == "✨ Факт про Майю")
async def get_fact(message: types.Message):
    if not await check_access(message):
        return
    await message.answer("⏳ Сочиняю...")
    prompt = """Придумай один интересный и милый факт или комплимент о девушке по имени Майя. 
Факт должен быть:
- Позитивным и теплым
- Коротким (1-2 предложения)
- Оригинальным и смешным
- Не банальным

Пример стиля: "Майя умеет находить красоту в самых обычных моментах и делиться ей с окружающими."

Напиши один факт без предисловий:"""
    text = await call_ai(prompt)
    if text:
        # Обрезаем если очень длинный
        if len(text) > 1000:
            text = text[:1000] + "..."
        await message.answer(text)
    else:
        await message.answer("❌ Ошибка")

# 2. ВИШ-ЛИСТ
@dp.message(F.text == "🎁 В виш-лист")
async def add_wish_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    await state.set_state(MyStates.waiting_for_wish)
    await message.answer("Пиши свою хотелку (или нажми 'Отмена'):", reply_markup=builder.as_markup())

@dp.message(MyStates.waiting_for_wish, F.text == "❌ Отмена")
async def cancel_wish(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено ✌️", reply_markup=main_menu())

@dp.message(MyStates.waiting_for_wish, F.text)
async def save_wish(message: types.Message, state: FSMContext):
    # Проверяем, что текст не пустой
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Желание не может быть пустым!")
        return
    
    try:
        wish_text = message.text.strip()
        user_id = message.from_user.id
        user_name = USER_NAMES.get(user_id, "Пользователь")
        
        # Ограничиваем длину
        if len(wish_text) > 500:
            await message.answer("⚠️ Желание слишком длинное (макс 500 символов)")
            return
        
        add_wish(user_id, wish_text)
        await state.clear()
        await message.answer(f"✅ Добавлено в твой виш-лист: {wish_text}", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error saving wish: {e}")
        await message.answer(f"❌ Ошибка при сохранении: {e}", reply_markup=main_menu())
        await state.clear()

# 3. ЦИТАТЫ
@dp.message(F.text == "🤣 В цитаты")
async def add_quote_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    await state.set_state(MyStates.waiting_for_quote)
    await message.answer("Какую фразу сохраним для истории? (или нажми 'Отмена'):", reply_markup=builder.as_markup())

@dp.message(MyStates.waiting_for_quote, F.text == "❌ Отмена")
async def cancel_quote(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено ✌️", reply_markup=main_menu())

@dp.message(MyStates.waiting_for_quote, F.text)
async def save_quote(message: types.Message, state: FSMContext):
    # Проверяем, что текст не пустой
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Цитата не может быть пустой!")
        return
    
    try:
        quote_text = message.text.strip()
        user_id = message.from_user.id
        user_name = USER_NAMES.get(user_id, "Пользователь")
        
        # Ограничиваем длину
        if len(quote_text) > 500:
            await message.answer("⚠️ Цитата слишком длинная (макс 500 символов)")
            return
        
        add_quote(user_id, quote_text)
        await state.clear()
        await message.answer("🤣 Ха-ха, сохранил в твою коллекцию!", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error saving quote: {e}")
        await message.answer(f"❌ Ошибка при сохранении: {e}", reply_markup=main_menu())
        await state.clear()

# 4. ИИ АССИСТЕНТ
def ai_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Закончить общение")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

@dp.message(F.text == "🤖 Спросить ИИ")
async def ai_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_ai)
    await message.answer("Я тебя слушаю! Пиши свой вопрос (или нажми 'Закончить общение'):", reply_markup=ai_menu())

@dp.message(MyStates.waiting_for_ai, F.text == "🔙 Закончить общение")
async def ai_end(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Общение завершено! ✌️", reply_markup=main_menu())

@dp.message(MyStates.waiting_for_ai)
async def ai_answer(message: types.Message, state: FSMContext):
    # Проверяем, что текст не пустой
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Вопрос не может быть пустым!", reply_markup=ai_menu())
        return
    
    # Ограничиваем длину вопроса
    if len(message.text) > 2000:
        await message.answer("⚠️ Вопрос слишком длинный (макс 2000 символов)", reply_markup=ai_menu())
        return
    
    await message.answer("⏳ Думаю...")
    text = await call_ai(message.text)
    if text:
        # Ограничиваем длину ответа для читаемости
        if len(text) > 3000:
            text = text[:3000] + "\n\n... (ответ обрезан)"
        await message.answer(text, reply_markup=ai_menu())
    else:
        await message.answer("❌ Ошибка", reply_markup=ai_menu())

# 5. ТАЙНЫЕ СООБЩЕНИЯ ОТ МАЙИ
@dp.message(F.text == "💌 Тайное сообщение")
async def secret_message_start(message: types.Message, state: FSMContext):
    logging.info(f"💌 User requested secret message: {message.from_user.id}")
    if not await check_access(message):
        return
    
    # Показываем кнопки для выбора получателя (только Тёма и Майя)
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Тёма")
    builder.button(text="👩 Майя")
    builder.button(text="❌ Отмена")
    builder.adjust(2)
    
    await state.set_state(MyStates.selecting_message_recipient)
    logging.info(f"✅ Showing recipient selection to user {message.from_user.id}")
    await message.answer("💌 Кому отправить сообщение?", reply_markup=builder.as_markup())

@dp.message(MyStates.selecting_message_recipient, F.text)
async def select_recipient(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено ✌️", reply_markup=main_menu())
        return
    
    recipient_id = None
    recipient_name = None
    
    if message.text == "👤 Тёма":
        recipient_id = 7118929376
        recipient_name = "Тёма"
    elif message.text == "👩 Майя":
        recipient_id = 8481047835
        recipient_name = "Майя"
    else:
        # Пользователь ввел что-то неожиданное
        await message.answer("⚠️ Пожалуйста, выбери кнопку: 'Тёма' или 'Майя'")
        return
    
    await state.update_data(recipient=recipient_name, recipient_id=recipient_id)
    await state.set_state(MyStates.waiting_for_secret_message)
    await message.answer(f"✍️ Напиши тайное сообщение для {recipient_name}:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(MyStates.waiting_for_secret_message, F.text)
async def send_secret_message(message: types.Message, state: FSMContext):
    try:
        # Проверяем, что сообщение не пустое
        if not message.text or not message.text.strip():
            await message.answer("⚠️ Сообщение не может быть пустым!")
            return
        
        data = await state.get_data()
        sender_id = message.from_user.id
        sender_name = USER_NAMES.get(sender_id, f"Пользователь {sender_id}")
        recipient_id = data.get('recipient_id')
        recipient_name = data.get('recipient', 'unknown')
        
        if not recipient_id:
            await state.clear()
            await message.answer("❌ Ошибка: получатель не выбран", reply_markup=main_menu())
            return
        
        # Ограничиваем длину сообщения
        message_text = message.text.strip()
        if len(message_text) > 2000:
            await message.answer("⚠️ Сообщение слишком длинное (макс 2000 символов)")
            return
        
        # Отправляем сообщение получателю (используем HTML вместо Markdown)
        await bot.send_message(
            recipient_id,
            f"💌 <b>Тайное сообщение от {sender_name}:</b>\n\n<i>{message_text}</i>",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Сообщение отправлено {recipient_name}!", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error sending secret message: {e}")
        await message.answer(f"❌ Ошибка при отправке сообщения: {e}", reply_markup=main_menu())
    
    await state.clear()

# 6. ПРОСМОТР СПИСКОВ
@dp.message(F.text == "📂 Посмотреть списки")
async def show_all(message: types.Message):
    logging.info(f"📂 User requested to view lists: {message.from_user.id}")
    if not await check_access(message):
        return
    
    user_id = message.from_user.id
    
    # Получаем данные для всех пользователей
    all_wishes = get_data("wishlist")
    all_quotes = get_data("quotes")
    
    # Формируем текст с разделением
    text = "<b>🎁 ВИШИРЦЫ:</b>\n\n"
    
    wishes_empty = True
    for uid in ALLOWED_USERS:
        uid_str = str(uid)
        uid_name = USER_NAMES.get(uid, "Неизвестный")
        uid_wishes = all_wishes.get(uid_str, [])
        
        if uid_wishes:
            wishes_empty = False
            text += f"<b>{uid_name}:</b>\n"
            for i, wish in enumerate(uid_wishes, 1):
                text += f"  {i}. {wish}\n"
            text += "\n"
    
    if wishes_empty:
        text += "<i>Все виш-листы пусты</i>\n"
    
    text += "\n<b>🤣 ЦИТАТЫ:</b>\n\n"
    
    quotes_empty = True
    for uid in ALLOWED_USERS:
        uid_str = str(uid)
        uid_name = USER_NAMES.get(uid, "Неизвестный")
        uid_quotes = all_quotes.get(uid_str, [])
        
        if uid_quotes:
            quotes_empty = False
            text += f"<b>{uid_name}:</b>\n"
            for i, quote in enumerate(uid_quotes, 1):
                text += f"  {i}. {quote}\n"
            text += "\n"
    
    if quotes_empty:
        text += "<i>Все цитаты пусты</i>"
    
    logging.info(f"✅ Sending lists to user {message.from_user.id}")
    await message.answer(text, parse_mode="HTML")

# 7. УДАЛЕНИЕ
@dp.message(F.text == "🗑️ Удалить элемент")
async def delete_menu(message: types.Message):
    if not await check_access(message):
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Удалить из виш-листа", callback_data="delete_wish_menu")
    builder.button(text="🤣 Удалить из цитат", callback_data="delete_quote_menu")
    builder.button(text="❌ Отмена", callback_data="cancel_delete")
    builder.adjust(1)
    await message.answer("Что удаляем?", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "delete_wish_menu")
async def show_wishes_to_delete(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    wishes = get_user_wishes(user_id)
    if not wishes:
        await callback.answer("У тебя нет хотелок!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for i, wish in enumerate(wishes):
        # Ограничиваем длину текста кнопки для совместимости с Telegram
        display_text = wish[:40] + "..." if len(wish) > 40 else wish
        builder.button(text=f"❌ {display_text}", callback_data=f"del_wish_{i}")
    builder.button(text="🔙 Назад", callback_data="cancel_delete")
    builder.adjust(1)
    
    await callback.message.edit_text("Какую хотелку удалить?", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "delete_quote_menu")
async def show_quotes_to_delete(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    quotes = get_user_quotes(user_id)
    if not quotes:
        await callback.answer("У тебя нет цитат!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for i, quote in enumerate(quotes):
        # Ограничиваем длину текста кнопки для совместимости с Telegram
        display_text = quote[:40] + "..." if len(quote) > 40 else quote
        builder.button(text=f"❌ {display_text}", callback_data=f"del_quote_{i}")
    builder.button(text="🔙 Назад", callback_data="cancel_delete")
    builder.adjust(1)
    
    await callback.message.edit_text("Какую цитату удалить?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_wish_"))
async def delete_wish_cb(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        # Парсим индекс - берем все после последнего underscore
        idx_str = callback.data.rsplit("_", 1)[-1]
        idx = int(idx_str)
        
        # Получаем хотелку перед удалением (для сообщения)
        wishes = get_user_wishes(user_id)
        if 0 <= idx < len(wishes):
            removed = wishes[idx]
            delete_wish(user_id, idx)
            await callback.message.edit_text(f"✅ Удалено: {removed}\n\nОсталось {len(wishes)-1} хотелок")
        else:
            await callback.answer("❌ Хотелка не найдена!", show_alert=True)
    except ValueError:
        logging.error(f"❌ Invalid callback data format: {callback.data}")
        await callback.answer(f"❌ Ошибка: неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error deleting wish: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("del_quote_"))
async def delete_quote_cb(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        # Парсим индекс - берем все после последнего underscore
        idx_str = callback.data.rsplit("_", 1)[-1]
        idx = int(idx_str)
        
        # Получаем цитату перед удалением (для сообщения)
        quotes = get_user_quotes(user_id)
        if 0 <= idx < len(quotes):
            removed = quotes[idx]
            delete_quote(user_id, idx)
            await callback.message.edit_text(f"✅ Удалено: {removed}\n\nОсталось {len(quotes)-1} цитат")
        else:
            await callback.answer("❌ Цитата не найдена!", show_alert=True)
    except ValueError:
        logging.error(f"❌ Invalid callback data format: {callback.data}")
        await callback.answer(f"❌ Ошибка: неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error deleting quote: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await callback.message.edit_text("Отменено ✌️", reply_markup=None)

# 8. ОТСЛЕЖИВАНИЕ ОТНОШЕНИЙ
@dp.message(F.text == "💕 Отношения")
async def relationship_menu(message: types.Message):
    if not await check_access(message):
        return
    
    stats = calculate_relationship_stats()
    
    if stats:
        text = f"""💕 <b>Наши отношения:</b>

<b>Вместе уже:</b>
🕐 <b>{stats['days']} дней</b>
📅 <b>{stats['months']} месяцев {stats['days_in_month']} дней</b>

<b>Начало:</b> {stats['formatted_date']}
"""
    else:
        text = """💕 <b>Отношения</b>

Дата начала отношений еще не установлена.
Хочешь её добавить?
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Установить дату", callback_data="set_relationship_date")
    if stats:
        builder.button(text="✏️ Изменить дату", callback_data="change_relationship_date")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "set_relationship_date")
async def set_date_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await state.set_state(MyStates.setting_relationship_date)
    await callback.message.edit_text(
        "📅 Напиши дату начала отношений в формате: <b>YYYY-MM-DD</b>\n\n"
        "Пример: <b>2026-01-28</b>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "change_relationship_date")
async def change_date_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await state.set_state(MyStates.setting_relationship_date)
    await callback.message.edit_text(
        "📅 Введи новую дату в формате: <b>YYYY-MM-DD</b>\n\n"
        "Пример: <b>2026-01-28</b>",
        parse_mode="HTML"
    )

@dp.message(MyStates.setting_relationship_date)
async def save_relationship_date(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Дата не может быть пустой!")
        return
    
    date_str = message.text.strip()
    
    if set_relationship_date(date_str):
        stats = calculate_relationship_stats()
        await state.clear()
        text = f"""✅ <b>Дата установлена!</b>

💕 <b>Вместе уже:</b>
🕐 <b>{stats['days']} дней</b>
📅 <b>{stats['months']} месяцев {stats['days_in_month']} дней</b>

<b>Начало:</b> {stats['formatted_date']}
"""
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
    else:
        await message.answer("❌ Неверный формат даты! Используй YYYY-MM-DD (например: 2026-01-28)")

# 9. ВОСПОМИНАНИЯ
@dp.message(F.text == "📸 Воспоминания")
async def memories_menu(message: types.Message):
    if not await check_access(message):
        return
    
    memories = get_memories()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить воспоминание", callback_data="add_memory")
    if memories:
        builder.button(text="📖 Посмотреть все", callback_data="view_all_memories")
        builder.button(text="🗑️ Удалить воспоминание", callback_data="delete_memory_menu")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    text = f"""📸 <b>Воспоминания</b>

Всего сохранено: <b>{len(memories)} воспоминаний</b>
"""
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_memory")
async def add_memory_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await state.set_state(MyStates.adding_memory)
    await callback.message.edit_text("✍️ Напиши воспоминание:")

@dp.message(MyStates.adding_memory)
async def save_memory_text(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Воспоминание не может быть пустым!")
        return
    
    memory_text = message.text.strip()
    if len(memory_text) > 1000:
        await message.answer("⚠️ Воспоминание слишком длинное (макс 1000 символов)")
        return
    
    if add_memory(memory_text):
        await state.clear()
        await message.answer("✅ Воспоминание сохранено! 💕", reply_markup=main_menu())
    else:
        await message.answer("❌ Ошибка при сохранении воспоминания", reply_markup=main_menu())
        await state.clear()

@dp.callback_query(F.data == "view_all_memories")
async def view_all_memories(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    memories = get_memories()
    if not memories:
        await callback.answer("Нет воспоминаний!", show_alert=True)
        return
    
    text = "<b>📸 Все воспоминания:</b>\n\n"
    for i, memory in enumerate(memories, 1):
        text += f"<b>{i}.</b> <i>{memory['date']}</i>\n{memory['text']}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")

@dp.callback_query(F.data == "delete_memory_menu")
async def delete_memory_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    memories = get_memories()
    if not memories:
        await callback.answer("Нет воспоминаний!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for i, memory in enumerate(memories):
        display_text = memory['text'][:30] + "..." if len(memory['text']) > 30 else memory['text']
        builder.button(text=f"❌ {display_text}", callback_data=f"del_memory_{i}")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text("Какое воспоминание удалить?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_memory_"))
async def delete_memory_cb(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        idx_str = callback.data.rsplit("_", 1)[-1]
        idx = int(idx_str)
        
        memories = get_memories()
        if 0 <= idx < len(memories):
            removed = memories[idx]['text'][:50]
            delete_memory(idx)
            await callback.message.edit_text(f"✅ Воспоминание удалено\n\nОсталось {len(memories)-1} воспоминаний")
        else:
            await callback.answer("❌ Воспоминание не найдено!", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error deleting memory: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_cb(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await callback.message.delete()

# --- FALLBACK ОБРАБОТЧИКИ ДЛЯ ЗАБЫТЫХ СОСТОЯНИЙ ---
@dp.message(MyStates.waiting_for_secret_message)
async def fallback_secret_message(message: types.Message, state: FSMContext):
    """Дублируем основной обработчик отправки сообщений"""
    # Проверяем, что сообщение не пустое
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Сообщение не может быть пустым!")
        return
    
    try:
        data = await state.get_data()
        sender_id = message.from_user.id
        sender_name = USER_NAMES.get(sender_id, f"Пользователь {sender_id}")
        recipient_id = data.get('recipient_id')
        recipient_name = data.get('recipient', 'unknown')
        
        if not recipient_id:
            await state.clear()
            await message.answer("❌ Ошибка: получатель не выбран", reply_markup=main_menu())
            return
        
        # Ограничиваем длину сообщения
        message_text = message.text.strip()
        if len(message_text) > 2000:
            await message.answer("⚠️ Сообщение слишком длинное (макс 2000 символов)")
            return
        
        await bot.send_message(
            recipient_id,
            f"💌 <b>Тайное сообщение от {sender_name}:</b>\n\n<i>{message_text}</i>",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Сообщение отправлено {recipient_name}!", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error sending secret message (fallback): {e}")
        await message.answer(f"❌ Ошибка при отправке сообщения: {e}", reply_markup=main_menu())
    
    await state.clear()

# --- ОБРАБОТЧИК ДЛЯ НЕИЗВЕСТНЫХ КОМАНД И СООБЩЕНИЙ ---
@dp.message()
async def unknown_message(message: types.Message, state: FSMContext):
    """Обработчик для всех остальных сообщений"""
    current_state = await state.get_state()
    
    # Если пользователь не в состоянии, то это неизвестная команда
    if current_state is None:
        await message.answer("❌ Неизвестная команда. Нажми /start для начала.", reply_markup=main_menu())
    # Если в состоянии ввода wish
    elif current_state == MyStates.waiting_for_wish.state:
        # Уже обработано выше, это fallback
        pass
    # Если в состоянии ввода quote
    elif current_state == MyStates.waiting_for_quote.state:
        # Уже обработано выше, это fallback
        pass

async def main():
    logging.info("🚀 Bot starting... (v2.1 - fixed error messages)")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Bot crashed: {e}")
        raise
    finally:
        await bot.session.close()
        logging.info("🛑 Bot stopped")

if __name__ == '__main__':
    asyncio.run(main())