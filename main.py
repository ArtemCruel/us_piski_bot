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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8682882436:AAGjx583es0SwLIrVyOQ1-Z_-_tINYdtkI0"
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY") or "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"

# --- БЕЛЫЙ СПИСОК ПОЛЬЗОВАТЕЛЕЙ (разрешены только эти user_id) ---
ALLOWED_USERS = [
    7118929376,     # Artem личный
    1428288113,     # Artem основной (@A_rtemK)
    8481047835,     # Майя (@poqqg)
]

logging.info(f"🔧 TELEGRAM_TOKEN set: {bool(TELEGRAM_TOKEN)}")
logging.info(f"🔧 OPENROUTER_KEY set: {bool(OPENROUTER_KEY)}")

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

# --- РАБОТА С ДАННЫМИ ---
def get_data(name):
    try:
        with open(f"{name}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_data(name, data):
    with open(f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✨ Факт про Майю")
    builder.button(text="🎁 В виш-лист")
    builder.button(text="🤣 В цитаты")
    builder.button(text="🤖 Спросить ИИ")
    builder.button(text="📂 Посмотреть списки")
    builder.button(text="🗑️ Удалить элемент")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

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
            response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logging.error(f"AI error: {e}")
            return None
    
    try:
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        logging.error(f"AI error: {e}")
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
        await message.answer(text)
    else:
        await message.answer("❌ Ошибка ИИ. Проверь баланс/ключ на OpenRouter.")

# 2. ВИШ-ЛИСТ
@dp.message(F.text == "🎁 В виш-лист")
async def add_wish_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_wish)
    await message.answer("Пиши свою хотелку, я её сразу запишу!")

@dp.message(MyStates.waiting_for_wish, F.text)
async def save_wish(message: types.Message, state: FSMContext):
    data = get_data("wishlist")
    data.append(message.text)
    save_data("wishlist", data)
    await state.clear()
    await message.answer(f"✅ Добавлено в виш-лист: {message.text}", reply_markup=main_menu())

# 3. ЦИТАТЫ
@dp.message(F.text == "🤣 В цитаты")
async def add_quote_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_quote)
    await message.answer("Какую фразу сохраним для истории?")

@dp.message(MyStates.waiting_for_quote, F.text)
async def save_quote(message: types.Message, state: FSMContext):
    data = get_data("quotes")
    data.append(message.text)
    save_data("quotes", data)
    await state.clear()
    await message.answer("🤣 Ха-ха, сохранил!", reply_markup=main_menu())

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

@dp.message(MyStates.waiting_for_ai, F.text)
async def ai_answer(message: types.Message, state: FSMContext):
    await message.answer("⏳ Думаю...")
    text = await call_ai(message.text)
    if text:
        await message.answer(text, reply_markup=ai_menu())
    else:
        await message.answer("❌ Ошибка ИИ при обработке запроса.", reply_markup=ai_menu())

# 5. ПРОСМОТР СПИСКОВ
@dp.message(F.text == "📂 Посмотреть списки")
async def show_all(message: types.Message):
    if not await check_access(message):
        return
    wishes = get_data("wishlist")
    quotes = get_data("quotes")
    
    text = "🎁 **Виш-лист:**\n" + ("\n".join([f"{i+1}. {item}" for i, item in enumerate(wishes)]) if wishes else "Пусто")
    text += "\n\n🤣 **Цитаты:**\n" + ("\n".join([f"{i+1}. {item}" for i, item in enumerate(quotes)]) if quotes else "Пусто")
    
    await message.answer(text, parse_mode="Markdown")

# 6. УДАЛЕНИЕ
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
    wishes = get_data("wishlist")
    if not wishes:
        await callback.answer("Виш-лист пуст!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for i, wish in enumerate(wishes):
        builder.button(text=f"❌ {wish}", callback_data=f"del_wish_{i}")
    builder.button(text="🔙 Назад", callback_data="cancel_delete")
    builder.adjust(1)
    
    await callback.message.edit_text("Выбери, что удалить:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "delete_quote_menu")
async def show_quotes_to_delete(callback: types.CallbackQuery):
    quotes = get_data("quotes")
    if not quotes:
        await callback.answer("Цитаты пусты!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for i, quote in enumerate(quotes):
        builder.button(text=f"❌ {quote}", callback_data=f"del_quote_{i}")
    builder.button(text="🔙 Назад", callback_data="cancel_delete")
    builder.adjust(1)
    
    await callback.message.edit_text("Выбери цитату для удаления:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_wish_"))
async def delete_wish(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[2])
    data = get_data("wishlist")
    if 0 <= idx < len(data):
        removed = data.pop(idx)
        save_data("wishlist", data)
        await callback.message.edit_text(f"✅ Удалено: {removed}\n\nОставалось: {len(data)} желаний")
    else:
        await callback.answer("Ошибка индекса!", show_alert=True)

@dp.callback_query(F.data.startswith("del_quote_"))
async def delete_quote(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[2])
    data = get_data("quotes")
    if 0 <= idx < len(data):
        removed = data.pop(idx)
        save_data("quotes", data)
        await callback.message.edit_text(f"✅ Удалено: {removed}\n\nОставалось: {len(data)} цитат")
    else:
        await callback.answer("Ошибка индекса!", show_alert=True)

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    await callback.message.edit_text("Отменено ✌️", reply_markup=None)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())