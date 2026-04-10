import asyncio
import json
import os
import logging
import requests
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

# --- ФУНКЦИИ ОТНОШЕНИЙ И ВОСПОМИНАНИЙ ---
def get_relationship_date():
    """Получить дату начала отношений"""
    data = get_data("relationship")
    return data.get("start_date", None)

def set_relationship_date(date_str):
    """Сохранить дату начала отношений (формат: YYYY-MM-DD)"""
    data = get_data("relationship")
    data["start_date"] = date_str
    save_data("relationship", data)

def calculate_relationship_stats():
    """Рассчитать статистику отношений"""
    from datetime import datetime
    start_date_str = get_relationship_date()
    
    if not start_date_str:
        return None
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        today = datetime.now()
        delta = today - start_date
        
        days = delta.days
        months = days // 30
        years = days // 365
        
        # Годовщины
        anniversaries = []
        if days >= 365:
            anniversaries.append(f"{years} год(а/ов)")
        if days >= 30:
            anniversaries.append(f"{months} месяц(ев)")
        anniversaries.append(f"{days} дней")
        
        return {
            "days": days,
            "months": months,
            "years": years,
            "start_date": start_date_str,
            "anniversaries": " • ".join(anniversaries)
        }
    except Exception as e:
        logging.error(f"❌ Error calculating relationship stats: {e}")
        return None

def add_memory(memory_data):
    """Добавить воспоминание с текстом и/или файлом"""
    data = get_data("memories")
    
    if "memories" not in data:
        data["memories"] = []
    
    # Каждое воспоминание имеет timestamp, текст и info о файле
    from datetime import datetime
    memory_entry = {
        "timestamp": datetime.now().isoformat(),
        "text": memory_data.get("text", ""),
        "file_id": memory_data.get("file_id", None),
        "file_type": memory_data.get("file_type", None),  # photo, audio, video, document
        "file_name": memory_data.get("file_name", "")
    }
    
    data["memories"].append(memory_entry)
    save_data("memories", data)
    return len(data["memories"])

def get_memories(limit=10):
    """Получить последние воспоминания"""
    data = get_data("memories")
    memories = data.get("memories", [])
    # Возвращаем последние 'limit' воспоминаний в обратном порядке
    return list(reversed(memories[-limit:]))

def delete_memory(idx):
    """Удалить воспоминание по индексу"""
    data = get_data("memories")
    memories = data.get("memories", [])
    
    if 0 <= idx < len(memories):
        memories.pop(idx)
        data["memories"] = memories
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
    builder.button(text="💕 Отношения")
    builder.button(text="📸 Воспоминания")
    builder.button(text="🗑️ Удалить элемент")
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
    """Генерирует случайный факт про Майю"""
    if not await check_access(message):
        return
    
    try:
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
            logging.info(f"✨ Fact generated for user {message.from_user.id}")
        else:
            await message.answer("❌ Ошибка")
            logging.error(f"❌ Fact generation failed: AI returned None")
    except Exception as e:
        logging.error(f"❌ Error in get_fact: {e}")
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
    """Сохраняет желание"""
    try:
        # Проверяем, что текст не пустой
        if not message.text or not message.text.strip():
            await message.answer("⚠️ Желание не может быть пустым!")
            return
        
        wish_text = message.text.strip()
        user_id = message.from_user.id
        user_name = USER_NAMES.get(user_id, "Пользователь")
        
        # Ограничиваем длину
        if len(wish_text) > 500:
            await message.answer("⚠️ Желание слишком длинное (макс 500 символов)")
            return
        
        # Сохраняем
        add_wish(user_id, wish_text)
        await state.clear()
        await message.answer(f"✅ Добавлено в твой виш-лист: {wish_text}", reply_markup=main_menu())
        logging.info(f"✅ Wish added for user {user_id}: {wish_text}")
    except Exception as e:
        logging.error(f"❌ Error in save_wish: {type(e).__name__}: {e}")
        await message.answer("❌ Ошибка при сохранении", reply_markup=main_menu())
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
    """Сохраняет цитату"""
    try:
        # Проверяем, что текст не пустой
        if not message.text or not message.text.strip():
            await message.answer("⚠️ Цитата не может быть пустой!")
            return
        
        quote_text = message.text.strip()
        user_id = message.from_user.id
        user_name = USER_NAMES.get(user_id, "Пользователь")
        
        # Ограничиваем длину
        if len(quote_text) > 500:
            await message.answer("⚠️ Цитата слишком длинная (макс 500 символов)")
            return
        
        # Сохраняем
        add_quote(user_id, quote_text)
        await state.clear()
        await message.answer("🤣 Ха-ха, сохранил в твою коллекцию!", reply_markup=main_menu())
        logging.info(f"✅ Quote added for user {user_id}: {quote_text}")
    except Exception as e:
        logging.error(f"❌ Error in save_quote: {type(e).__name__}: {e}")
        await message.answer("❌ Ошибка при сохранении", reply_markup=main_menu())
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
    """Ответ ИИ на вопрос"""
    try:
        # Проверяем, что текст не пустой
        if not message.text or not message.text.strip():
            await message.answer("⚠️ Вопрос не может быть пустым!", reply_markup=ai_menu())
            return
        
        question_text = message.text.strip()
        
        # Ограничиваем длину вопроса
        if len(question_text) > 2000:
            await message.answer("⚠️ Вопрос слишком длинный (макс 2000 символов)", reply_markup=ai_menu())
            return
        
        await message.answer("⏳ Думаю...", reply_markup=ai_menu())
        
        text = await call_ai(question_text)
        
        if text:
            # Ограничиваем длину ответа для читаемости
            if len(text) > 3000:
                text = text[:3000] + "\n\n... (ответ обрезан)"
            await message.answer(text, reply_markup=ai_menu())
            logging.info(f"🤖 AI answered question from user {message.from_user.id}")
        else:
            await message.answer("❌ Ошибка", reply_markup=ai_menu())
            logging.error(f"❌ AI response failed for user {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in ai_answer: {type(e).__name__}: {e}")
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
    """Отправка тайного сообщения"""
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
        
        # Отправляем сообщение получателю
        try:
            await bot.send_message(
                recipient_id,
                f"💌 <b>Тайное сообщение от {sender_name}:</b>\n\n<i>{message_text}</i>",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Сообщение отправлено {recipient_name}!", reply_markup=main_menu())
            logging.info(f"💌 Secret message sent from {sender_id} to {recipient_id}")
        except Exception as send_error:
            logging.error(f"❌ Failed to send message to recipient: {send_error}")
            await message.answer(f"❌ Не смог отправить сообщение. Попробуй позже.", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error in send_secret_message: {e}")
        await message.answer(f"❌ Ошибка", reply_markup=main_menu())
    finally:
        await state.clear()

# 6. ПРОСМОТР СПИСКОВ
@dp.message(F.text == "📂 Посмотреть списки")
async def show_all(message: types.Message):
    """Показывает все желания и цитаты всех пользователей"""
    logging.info(f"📂 User requested to view lists: {message.from_user.id}")
    if not await check_access(message):
        return
    
    try:
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
        
        logging.info(f"✅ Lists sent to user {message.from_user.id}")
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Error in show_all: {type(e).__name__}: {e}")
        await message.answer("❌ Ошибка при получении списков", reply_markup=main_menu())

# 7. УДАЛЕНИЕ
@dp.message(F.text == "🗑️ Удалить элемент")
async def delete_menu(message: types.Message):
    """Показывает меню удаления элементов"""
    if not await check_access(message):
        return
    
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🎁 Удалить из виш-листа", callback_data="delete_wish_menu")
        builder.button(text="🤣 Удалить из цитат", callback_data="delete_quote_menu")
        builder.button(text="❌ Отмена", callback_data="cancel_delete")
        builder.adjust(1)
        await message.answer("Что удаляем?", reply_markup=builder.as_markup())
        logging.info(f"🗑️ Delete menu shown to user {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in delete_menu: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())

@dp.callback_query(F.data == "delete_wish_menu")
async def show_wishes_to_delete(callback: types.CallbackQuery):
    """Показывает список желаний для удаления"""
    try:
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
        logging.info(f"📂 Wishes list shown to user {user_id}")
    except Exception as e:
        logging.error(f"❌ Error in show_wishes_to_delete: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "delete_quote_menu")
async def show_quotes_to_delete(callback: types.CallbackQuery):
    """Показывает список цитат для удаления"""
    try:
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
        logging.info(f"📂 Quotes list shown to user {user_id}")
    except Exception as e:
        logging.error(f"❌ Error in show_quotes_to_delete: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("del_wish_"))
async def delete_wish_cb(callback: types.CallbackQuery):
    """Удаление желания с обработкой ошибок"""
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        # Парсим индекс - берем все после "del_wish_"
        idx_str = callback.data.split("del_wish_")[1]
        idx = int(idx_str)
        
        # Получаем текущий список
        wishes = get_user_wishes(user_id)
        
        # Проверяем границы
        if not (0 <= idx < len(wishes)):
            await callback.answer("❌ Желание не найдено!", show_alert=True)
            return
        
        # Запоминаем текст ДО удаления
        removed_text = wishes[idx]
        wishes_count_before = len(wishes)
        
        # Удаляем
        if delete_wish(user_id, idx):
            wishes_count_after = wishes_count_before - 1
            await callback.message.edit_text(
                f"✅ Удалено: {removed_text}\n\nОсталось {wishes_count_after} хотелок",
                reply_markup=None
            )
            logging.info(f"✅ Wish deleted for user {user_id}: {removed_text}")
        else:
            await callback.answer("❌ Не удалось удалить!", show_alert=True)
            
    except ValueError as e:
        logging.error(f"❌ Invalid callback data: {callback.data}")
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error in delete_wish_cb: {type(e).__name__}: {e}")
        await callback.answer(f"❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("del_quote_"))
async def delete_quote_cb(callback: types.CallbackQuery):
    """Удаление цитаты с обработкой ошибок"""
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        # Парсим индекс - берем все после "del_quote_"
        idx_str = callback.data.split("del_quote_")[1]
        idx = int(idx_str)
        
        # Получаем текущий список
        quotes = get_user_quotes(user_id)
        
        # Проверяем границы
        if not (0 <= idx < len(quotes)):
            await callback.answer("❌ Цитата не найдена!", show_alert=True)
            return
        
        # Запоминаем текст ДО удаления
        removed_text = quotes[idx]
        quotes_count_before = len(quotes)
        
        # Удаляем
        if delete_quote(user_id, idx):
            quotes_count_after = quotes_count_before - 1
            await callback.message.edit_text(
                f"✅ Удалено: {removed_text}\n\nОсталось {quotes_count_after} цитат",
                reply_markup=None
            )
            logging.info(f"✅ Quote deleted for user {user_id}: {removed_text}")
        else:
            await callback.answer("❌ Не удалось удалить!", show_alert=True)
            
    except ValueError as e:
        logging.error(f"❌ Invalid callback data: {callback.data}")
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error in delete_quote_cb: {type(e).__name__}: {e}")
        await callback.answer(f"❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    """Отмена удаления"""
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return
        
        await callback.message.edit_text("Отменено ✌️", reply_markup=None)
        logging.info(f"❌ Delete operation cancelled by user {user_id}")
    except Exception as e:
        logging.error(f"❌ Error in cancel_delete: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# 8. ОТНОШЕНИЯ И ГОДОВЩИНЫ
@dp.message(F.text == "💕 Отношения")
async def show_relationship_menu(message: types.Message):
    """Показывает меню отношений"""
    if not await check_access(message):
        return
    
    try:
        stats = calculate_relationship_stats()
        
        if stats:
            # Если дата уже установлена, показываем статистику
            text = f"""💕 <b>НАШИ ОТНОШЕНИЯ</b> 💕

📅 Дата начала: <b>{stats['start_date']}</b>

🎉 <b>Статистика:</b>
   {stats['anniversaries']}

Это чудесное путешествие длится уже столько времени вместе! ❤️"""
            
            builder = InlineKeyboardBuilder()
            builder.button(text="📝 Изменить дату", callback_data="edit_relationship_date")
            builder.button(text="📸 Добавить воспоминание", callback_data="add_memory_button")
            builder.button(text="📂 Все воспоминания", callback_data="show_all_memories")
            builder.button(text="🔙 Назад", callback_data="back_to_menu")
            builder.adjust(1)
            
            await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
            logging.info(f"💕 Relationship stats shown to user {message.from_user.id}")
        else:
            # Если дата не установлена, предлагаем ее добавить
            text = "💕 <b>Отношения не установлены!</b>\n\nДавай установим дату начала наших отношений?"
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Установить дату", callback_data="set_relationship_date")
            builder.button(text="🔙 Назад", callback_data="back_to_menu")
            builder.adjust(1)
            
            await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
            logging.info(f"💕 Relationship setup prompt shown to user {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in show_relationship_menu: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())

@dp.callback_query(F.data == "set_relationship_date")
async def set_relationship_date_cb(callback: types.CallbackQuery, state: FSMContext):
    """Начало установки даты отношений"""
    try:
        await state.set_state(MyStates.setting_relationship_date)
        await callback.message.edit_text(
            "📅 Напиши дату начала отношений в формате: <b>YYYY-MM-DD</b>\n\nНапример: <b>2023-06-15</b>",
            parse_mode="HTML"
        )
        logging.info(f"📅 Awaiting relationship date from user {callback.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in set_relationship_date_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.message(MyStates.setting_relationship_date)
async def save_relationship_date(message: types.Message, state: FSMContext):
    """Сохранение даты отношений"""
    try:
        date_text = message.text.strip()
        
        # Проверяем формат YYYY-MM-DD
        from datetime import datetime
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ Неверный формат! Используй: YYYY-MM-DD (например, 2023-06-15)")
            return
        
        set_relationship_date(date_text)
        await state.clear()
        
        stats = calculate_relationship_stats()
        text = f"""✅ <b>Дата установлена!</b>

💕 Наши отношения:
📅 {stats['start_date']}

🎉 Статистика:
   {stats['anniversaries']}"""
        
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
        logging.info(f"✅ Relationship date set for user {message.from_user.id}: {date_text}")
    except Exception as e:
        logging.error(f"❌ Error in save_relationship_date: {e}")
        await message.answer("❌ Ошибка при сохранении даты", reply_markup=main_menu())
        await state.clear()

@dp.callback_query(F.data == "edit_relationship_date")
async def edit_relationship_date_cb(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование даты отношений"""
    try:
        await state.set_state(MyStates.setting_relationship_date)
        await callback.message.edit_text(
            "📅 Напиши новую дату в формате: <b>YYYY-MM-DD</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"❌ Error in edit_relationship_date_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# 9. ВОСПОМИНАНИЯ
@dp.callback_query(F.data == "add_memory_button")
async def add_memory_button(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления воспоминания"""
    try:
        await state.set_state(MyStates.adding_memory)
        await callback.message.edit_text(
            "📸 Поделись воспоминанием!\n\nМожешь:\n• Написать текст\n• Отправить фото\n• Отправить видео\n• Отправить аудио\n• Отправить документ\n\nОтправь свое воспоминание:",
            parse_mode="HTML"
        )
        logging.info(f"📸 Memory adding started for user {callback.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in add_memory_button: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.message(MyStates.adding_memory)
async def save_memory(message: types.Message, state: FSMContext):
    """Сохранение воспоминания"""
    try:
        memory_data = {}
        
        # Обрабатываем разные типы контента
        if message.photo:
            memory_data["file_id"] = message.photo[-1].file_id
            memory_data["file_type"] = "photo"
            memory_data["text"] = message.caption or ""
            content_type = "📸 фото"
        elif message.video:
            memory_data["file_id"] = message.video.file_id
            memory_data["file_type"] = "video"
            memory_data["file_name"] = message.video.file_name or "video"
            memory_data["text"] = message.caption or ""
            content_type = "🎥 видео"
        elif message.audio:
            memory_data["file_id"] = message.audio.file_id
            memory_data["file_type"] = "audio"
            memory_data["file_name"] = message.audio.file_name or "audio"
            memory_data["text"] = message.caption or ""
            content_type = "🎵 аудио"
        elif message.document:
            memory_data["file_id"] = message.document.file_id
            memory_data["file_type"] = "document"
            memory_data["file_name"] = message.document.file_name or "document"
            memory_data["text"] = message.caption or ""
            content_type = "📄 документ"
        elif message.text:
            memory_data["text"] = message.text.strip()
            content_type = "✍️ текст"
        else:
            await message.answer("⚠️ Неподдерживаемый тип контента. Отправь текст, фото, видео, аудио или документ.")
            return
        
        # Сохраняем воспоминание
        memory_id = add_memory(memory_data)
        await state.clear()
        
        await message.answer(
            f"✅ Воспоминание сохранено! 💕\n\nТип: {content_type}\nВсего воспоминаний: {memory_id}",
            reply_markup=main_menu()
        )
        logging.info(f"✅ Memory added for user {message.from_user.id}: type={memory_data.get('file_type', 'text')}")
    except Exception as e:
        logging.error(f"❌ Error in save_memory: {e}")
        await message.answer("❌ Ошибка при сохранении воспоминания", reply_markup=main_menu())
        await state.clear()

@dp.callback_query(F.data == "show_all_memories")
async def show_all_memories(callback: types.CallbackQuery):
    """Показать все воспоминания"""
    try:
        memories = get_memories(limit=50)
        
        if not memories:
            await callback.answer("У вас еще нет воспоминаний 😢", show_alert=True)
            return
        
        # Формируем текст со всеми воспоминаниями
        text = f"📸 <b>ВСЕ ВОСПОМИНАНИЯ ({len(memories)} шт.)</b> 📸\n\n"
        
        for i, memory in enumerate(memories, 1):
            from datetime import datetime
            try:
                date = datetime.fromisoformat(memory["timestamp"]).strftime("%d.%m.%Y %H:%M")
            except:
                date = "Unknown"
            
            file_type = memory.get("file_type", "text")
            text_preview = memory.get("text", "")[:50]
            
            if file_type == "photo":
                emoji = "📸"
            elif file_type == "video":
                emoji = "🎥"
            elif file_type == "audio":
                emoji = "🎵"
            elif file_type == "document":
                emoji = "📄"
            else:
                emoji = "✍️"
            
            text += f"{i}. {emoji} <b>{date}</b>"
            if text_preview:
                text += f"\n   <i>{text_preview}...</i>"
            text += "\n\n"
        
        # Если много воспоминаний, отправляем как обычное сообщение
        if len(text) > 4000:
            await callback.message.edit_text("⏳ Загружаю воспоминания...")
            # Отправляем порциями
            for i in range(0, len(memories), 5):
                chunk_memories = memories[i:i+5]
                chunk_text = f"📸 <b>ВОСПОМИНАНИЯ (часть {i//5 + 1})</b> 📸\n\n"
                for j, memory in enumerate(chunk_memories, i+1):
                    try:
                        date = datetime.fromisoformat(memory["timestamp"]).strftime("%d.%m.%Y %H:%M")
                    except:
                        date = "Unknown"
                    
                    file_type = memory.get("file_type", "text")
                    emoji = {"photo": "📸", "video": "🎥", "audio": "🎵", "document": "📄"}.get(file_type, "✍️")
                    text_preview = memory.get("text", "")[:30]
                    
                    chunk_text += f"{j}. {emoji} <b>{date}</b>"
                    if text_preview:
                        chunk_text += f"\n   <i>{text_preview}</i>"
                    chunk_text += "\n\n"
                
                await bot.send_message(callback.from_user.id, chunk_text, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, parse_mode="HTML")
        
        logging.info(f"📂 All memories shown to user {callback.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in show_all_memories: {e}")
        await callback.answer("❌ Ошибка при загрузке воспоминаний", show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Вернуться в главное меню"""
    try:
        await state.clear()
        await callback.message.delete()
        builder = ReplyKeyboardBuilder()
        builder.button(text="✨ Факт про Майю")
        builder.button(text="🎁 В виш-лист")
        builder.adjust(2)
        await bot.send_message(
            callback.from_user.id,
            "Вернулась в главное меню! 🏠",
            reply_markup=main_menu()
        )
    except Exception as e:
        logging.error(f"❌ Error in back_to_menu: {e}")

# --- ОБРАБОТЧИК ДЛЯ НЕИЗВЕСТНЫХ КОМАНД И СООБЩЕНИЙ ---
@dp.message()
async def unknown_message(message: types.Message):
    """Обработчик для всех остальных сообщений"""
    if not await check_access(message):
        return
    await message.answer("❌ Неизвестная команда. Нажми /start для начала.", reply_markup=main_menu())

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