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
    7118929376,   # Artem личный тема
    1428288113,   # Artem основной (@A_rtemK)
    8481047835,   # Майя (@poqqg)
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


# ============================================================
#                        СОСТОЯНИЯ
# ============================================================
class MyStates(StatesGroup):
    waiting_for_wish = State()
    waiting_for_quote = State()
    waiting_for_ai = State()
    selecting_message_recipient = State()
    waiting_for_secret_message = State()
    setting_relationship_date = State()
    adding_memory = State()


# ============================================================
#                     РАБОТА С ДАННЫМИ
# ============================================================
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
    data = get_data("wishlist")
    return data.get(str(user_id), [])


def get_user_quotes(user_id):
    data = get_data("quotes")
    return data.get(str(user_id), [])


def add_wish(user_id, wish_text):
    data = get_data("wishlist")
    uid = str(user_id)
    if uid not in data:
        data[uid] = []
    data[uid].append(wish_text)
    save_data("wishlist", data)


def add_quote(user_id, quote_text):
    data = get_data("quotes")
    uid = str(user_id)
    if uid not in data:
        data[uid] = []
    data[uid].append(quote_text)
    save_data("quotes", data)


def delete_wish(user_id, idx):
    data = get_data("wishlist")
    uid = str(user_id)
    if uid in data and 0 <= idx < len(data[uid]):
        data[uid].pop(idx)
        save_data("wishlist", data)
        return True
    return False


def delete_quote(user_id, idx):
    data = get_data("quotes")
    uid = str(user_id)
    if uid in data and 0 <= idx < len(data[uid]):
        data[uid].pop(idx)
        save_data("quotes", data)
        return True
    return False


# --- Отношения ---
def get_relationship_date():
    data = get_data("relationship")
    return data.get("start_date", None)


def set_relationship_date_data(date_str):
    data = get_data("relationship")
    data["start_date"] = date_str
    save_data("relationship", data)


def calculate_relationship_stats():
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

        parts = []
        if days >= 365:
            parts.append(f"{years} год(а/ов)")
        if days >= 30:
            parts.append(f"{months} месяц(ев)")
        parts.append(f"{days} дней")

        return {
            "days": days,
            "months": months,
            "years": years,
            "start_date": start_date_str,
            "anniversaries": " • ".join(parts),
        }
    except Exception as e:
        logging.error(f"❌ Error calculating relationship stats: {e}")
        return None


# --- Воспоминания ---
def add_memory(memory_data):
    data = get_data("memories")
    if "memories" not in data:
        data["memories"] = []
    entry = {
        "timestamp": datetime.now().isoformat(),
        "text": memory_data.get("text", ""),
        "file_id": memory_data.get("file_id", None),
        "file_type": memory_data.get("file_type", None),
        "file_name": memory_data.get("file_name", ""),
    }
    data["memories"].append(entry)
    save_data("memories", data)
    return len(data["memories"])


def get_memories(limit=50):
    data = get_data("memories")
    memories = data.get("memories", [])
    return list(reversed(memories[-limit:]))


def delete_memory(idx):
    data = get_data("memories")
    memories = data.get("memories", [])
    if 0 <= idx < len(memories):
        memories.pop(idx)
        data["memories"] = memories
        save_data("memories", data)
        return True
    return False


# ============================================================
#                      КЛАВИАТУРЫ
# ============================================================
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


def ai_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Закончить общение")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def cancel_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


# ============================================================
#                  ВЫЗОВ ИИ (OpenRouter)
# ============================================================
async def call_ai(prompt):
    """Вызывает OpenRouter API в отдельном потоке (не блокирует бот)."""
    def sync_call():
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "MayaBot",
        }
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            logging.info("📤 Sending request to OpenRouter...")
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            logging.info(f"📥 Response status: {resp.status_code}")

            if resp.status_code != 200:
                logging.error(f"❌ OpenRouter error {resp.status_code}: {resp.text}")
                return None

            result = resp.json()
            if "choices" not in result or not result["choices"]:
                logging.error(f"❌ Unexpected response format: {result}")
                return None

            return result["choices"][0]["message"]["content"]
        except requests.Timeout:
            logging.error("❌ OpenRouter request timed out")
            return None
        except Exception as e:
            logging.error(f"❌ AI error: {type(e).__name__}: {e}")
            return None

    try:
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        logging.error(f"❌ AI thread error: {e}")
        return None


# ============================================================
#                  ПРОВЕРКА ДОСТУПА
# ============================================================
async def check_access(message: types.Message) -> bool:
    user_id = message.from_user.id
    if user_id not in ALLOWED_USERS:
        logging.warning(f"🚫 DENIED: {user_id} (@{message.from_user.username})")
        await message.answer("❌ У вас нет доступа к этому боту.")
        return False
    return True


# ============================================================
#               КОМАНДЫ: /start, /help, /menu
# ============================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    logging.info(f"🆔 /start from {message.from_user.id} (@{message.from_user.username})")
    await message.answer("Бот запущен! Что хочешь сделать?", reply_markup=main_menu())


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not await check_access(message):
        return
    help_text = """📚 <b>Доступные функции:</b>

✨ <b>Факт про Майю</b> — случайный милый факт
🎁 <b>В виш-лист</b> — добавить желание
🤣 <b>В цитаты</b> — сохранить цитату
🤖 <b>Спросить ИИ</b> — диалог с ИИ
💌 <b>Тайное сообщение</b> — секретное сообщение
📂 <b>Посмотреть списки</b> — все желания и цитаты
💕 <b>Отношения</b> — дата и статистика
📸 <b>Воспоминания</b> — фото/видео/текст
🗑️ <b>Удалить элемент</b> — удалить из списков

/start — главное меню
/help — эта справка"""
    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    await message.answer("Главное меню 🏠", reply_markup=main_menu())


# ============================================================
#               1. ФАКТ ПРО МАЙЮ (✨)
# ============================================================
@dp.message(F.text == "✨ Факт про Майю")
async def get_fact(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    try:
        await message.answer("⏳ Сочиняю...", reply_markup=main_menu())
        prompt = (
            "Придумай один интересный и милый факт или комплимент о девушке по имени Майя. "
            "Факт должен быть позитивным, коротким (1-2 предложения), оригинальным и смешным. "
            "Напиши один факт без предисловий:"
        )
        text = await call_ai(prompt)
        if text:
            if len(text) > 1000:
                text = text[:1000] + "..."
            await message.answer(text, reply_markup=main_menu())
        else:
            await message.answer("❌ ИИ не ответил. Попробуй ещё раз.", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error in get_fact: {e}")
        await message.answer("❌ Ошибка генерации факта", reply_markup=main_menu())


# ============================================================
#               2. ВИШ-ЛИСТ (🎁)
# ============================================================
@dp.message(F.text == "🎁 В виш-лист")
async def add_wish_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_wish)
    await message.answer("Пиши свою хотелку (или нажми «Отмена»):", reply_markup=cancel_menu())


@dp.message(MyStates.waiting_for_wish, F.text == "❌ Отмена")
async def cancel_wish(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено ✌️", reply_markup=main_menu())


@dp.message(MyStates.waiting_for_wish, F.text)
async def save_wish(message: types.Message, state: FSMContext):
    try:
        wish_text = message.text.strip()
        if not wish_text:
            await message.answer("⚠️ Желание не может быть пустым!")
            return
        if len(wish_text) > 500:
            await message.answer("⚠️ Слишком длинное (макс 500 символов)")
            return

        add_wish(message.from_user.id, wish_text)
        await state.clear()
        await message.answer(f"✅ Добавлено в виш-лист: {wish_text}", reply_markup=main_menu())
        logging.info(f"✅ Wish added for {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in save_wish: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при сохранении", reply_markup=main_menu())


# ============================================================
#               3. ЦИТАТЫ (🤣)
# ============================================================
@dp.message(F.text == "🤣 В цитаты")
async def add_quote_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_quote)
    await message.answer("Какую фразу сохраним? (или «Отмена»):", reply_markup=cancel_menu())


@dp.message(MyStates.waiting_for_quote, F.text == "❌ Отмена")
async def cancel_quote(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено ✌️", reply_markup=main_menu())


@dp.message(MyStates.waiting_for_quote, F.text)
async def save_quote(message: types.Message, state: FSMContext):
    try:
        quote_text = message.text.strip()
        if not quote_text:
            await message.answer("⚠️ Цитата не может быть пустой!")
            return
        if len(quote_text) > 500:
            await message.answer("⚠️ Слишком длинная (макс 500 символов)")
            return

        add_quote(message.from_user.id, quote_text)
        await state.clear()
        await message.answer("🤣 Ха-ха, сохранил в твою коллекцию!", reply_markup=main_menu())
        logging.info(f"✅ Quote added for {message.from_user.id}")
    except Exception as e:
        logging.error(f"❌ Error in save_quote: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при сохранении", reply_markup=main_menu())


# ============================================================
#               4. ИИ АССИСТЕНТ (🤖)
# ============================================================
@dp.message(F.text == "🤖 Спросить ИИ")
async def ai_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(MyStates.waiting_for_ai)
    await message.answer(
        "Я тебя слушаю! Пиши вопрос (или «Закончить общение»):",
        reply_markup=ai_menu(),
    )


@dp.message(MyStates.waiting_for_ai, F.text == "🔙 Закончить общение")
async def ai_end(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Общение завершено! ✌️", reply_markup=main_menu())


@dp.message(MyStates.waiting_for_ai, F.text)
async def ai_answer(message: types.Message, state: FSMContext):
    """Ответ ИИ — фильтр F.text гарантирует что фото/стикеры сюда не попадут."""
    try:
        question = message.text.strip()
        if not question:
            await message.answer("⚠️ Вопрос не может быть пустым!", reply_markup=ai_menu())
            return
        if len(question) > 2000:
            await message.answer("⚠️ Слишком длинный вопрос (макс 2000)", reply_markup=ai_menu())
            return

        await message.answer("⏳ Думаю...", reply_markup=ai_menu())
        text = await call_ai(question)

        if text:
            if len(text) > 3000:
                text = text[:3000] + "\n\n… (ответ обрезан)"
            await message.answer(text, reply_markup=ai_menu())
        else:
            await message.answer("❌ ИИ не ответил. Попробуй ещё раз.", reply_markup=ai_menu())
    except Exception as e:
        logging.error(f"❌ Error in ai_answer: {e}")
        await message.answer("❌ Ошибка", reply_markup=ai_menu())


# ============================================================
#            5. ТАЙНЫЕ СООБЩЕНИЯ (💌)
# ============================================================
@dp.message(F.text == "💌 Тайное сообщение")
async def secret_message_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return

    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Тёма")
    builder.button(text="👩 Майя")
    builder.button(text="❌ Отмена")
    builder.adjust(2)

    await state.set_state(MyStates.selecting_message_recipient)
    await message.answer("💌 Кому отправить?", reply_markup=builder.as_markup(resize_keyboard=True))


@dp.message(MyStates.selecting_message_recipient, F.text == "❌ Отмена")
async def cancel_secret(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено ✌️", reply_markup=main_menu())


@dp.message(MyStates.selecting_message_recipient, F.text)
async def select_recipient(message: types.Message, state: FSMContext):
    recipient_map = {
        "👤 Тёма": (7118929376, "Тёма"),
        "👩 Майя": (8481047835, "Майя"),
    }
    choice = recipient_map.get(message.text)
    if not choice:
        await message.answer("⚠️ Выбери кнопку: «Тёма» или «Майя»")
        return

    recipient_id, recipient_name = choice
    await state.update_data(recipient_id=recipient_id, recipient=recipient_name)
    await state.set_state(MyStates.waiting_for_secret_message)
    await message.answer(
        f"✍️ Напиши тайное сообщение для {recipient_name}:",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@dp.message(MyStates.waiting_for_secret_message, F.text)
async def send_secret_message(message: types.Message, state: FSMContext):
    try:
        msg = message.text.strip()
        if not msg:
            await message.answer("⚠️ Сообщение не может быть пустым!")
            return
        if len(msg) > 2000:
            await message.answer("⚠️ Слишком длинное (макс 2000)")
            return

        data = await state.get_data()
        sender_name = USER_NAMES.get(message.from_user.id, "Аноним")
        recipient_id = data.get("recipient_id")
        recipient_name = data.get("recipient", "???")

        if not recipient_id:
            await state.clear()
            await message.answer("❌ Получатель не выбран", reply_markup=main_menu())
            return

        try:
            await bot.send_message(
                recipient_id,
                f"💌 <b>Тайное сообщение от {sender_name}:</b>\n\n<i>{msg}</i>",
                parse_mode="HTML",
            )
            await message.answer(f"✅ Отправлено {recipient_name}!", reply_markup=main_menu())
            logging.info(f"💌 Secret msg {message.from_user.id} → {recipient_id}")
        except Exception as send_err:
            logging.error(f"❌ Failed to send secret: {send_err}")
            await message.answer("❌ Не удалось отправить. Попробуй позже.", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error in send_secret_message: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())
    finally:
        await state.clear()


# ============================================================
#           6. ПОСМОТРЕТЬ СПИСКИ (📂)
# ============================================================
@dp.message(F.text == "📂 Посмотреть списки")
async def show_all(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    try:
        all_wishes = get_data("wishlist")
        all_quotes = get_data("quotes")

        text = "<b>🎁 ВИШИРЦЫ:</b>\n\n"
        wishes_empty = True
        for uid in ALLOWED_USERS:
            uid_str = str(uid)
            name = USER_NAMES.get(uid, "Неизвестный")
            items = all_wishes.get(uid_str, [])
            if items:
                wishes_empty = False
                text += f"<b>{name}:</b>\n"
                for i, w in enumerate(items, 1):
                    text += f"  {i}. {w}\n"
                text += "\n"
        if wishes_empty:
            text += "<i>Все виш-листы пусты</i>\n"

        text += "\n<b>🤣 ЦИТАТЫ:</b>\n\n"
        quotes_empty = True
        for uid in ALLOWED_USERS:
            uid_str = str(uid)
            name = USER_NAMES.get(uid, "Неизвестный")
            items = all_quotes.get(uid_str, [])
            if items:
                quotes_empty = False
                text += f"<b>{name}:</b>\n"
                for i, q in enumerate(items, 1):
                    text += f"  {i}. {q}\n"
                text += "\n"
        if quotes_empty:
            text += "<i>Все цитаты пусты</i>"

        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error in show_all: {e}")
        await message.answer("❌ Ошибка при получении списков", reply_markup=main_menu())


# ============================================================
#              7. УДАЛЕНИЕ ЭЛЕМЕНТОВ (🗑️)
# ============================================================
@dp.message(F.text == "🗑️ Удалить элемент")
async def delete_menu(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🎁 Удалить из виш-листа", callback_data="delete_wish_menu")
        builder.button(text="🤣 Удалить из цитат", callback_data="delete_quote_menu")
        builder.button(text="❌ Отмена", callback_data="cancel_delete")
        builder.adjust(1)
        await message.answer("Что удаляем?", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"❌ Error in delete_menu: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())


@dp.callback_query(F.data == "delete_wish_menu")
async def show_wishes_to_delete(callback: types.CallbackQuery):
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
            label = wish[:40] + "..." if len(wish) > 40 else wish
            builder.button(text=f"❌ {label}", callback_data=f"del_wish_{i}")
        builder.button(text="🔙 Назад", callback_data="cancel_delete")
        builder.adjust(1)

        await callback.message.edit_text("Какую хотелку удалить?", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"❌ Error in show_wishes_to_delete: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data == "delete_quote_menu")
async def show_quotes_to_delete(callback: types.CallbackQuery):
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
            label = quote[:40] + "..." if len(quote) > 40 else quote
            builder.button(text=f"❌ {label}", callback_data=f"del_quote_{i}")
        builder.button(text="🔙 Назад", callback_data="cancel_delete")
        builder.adjust(1)

        await callback.message.edit_text("Какую цитату удалить?", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"❌ Error in show_quotes_to_delete: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("del_wish_"))
async def delete_wish_cb(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return

        idx = int(callback.data.split("del_wish_")[1])
        wishes = get_user_wishes(user_id)

        if not (0 <= idx < len(wishes)):
            await callback.answer("❌ Не найдено!", show_alert=True)
            return

        removed = wishes[idx]
        if delete_wish(user_id, idx):
            await callback.message.edit_text(
                f"✅ Удалено: {removed}\n\nОсталось {len(wishes) - 1} хотелок"
            )
        else:
            await callback.answer("❌ Не удалось удалить!", show_alert=True)
    except ValueError:
        await callback.answer("❌ Неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error in delete_wish_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("del_quote_"))
async def delete_quote_cb(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("❌ Доступ запрещен!", show_alert=True)
            return

        idx = int(callback.data.split("del_quote_")[1])
        quotes = get_user_quotes(user_id)

        if not (0 <= idx < len(quotes)):
            await callback.answer("❌ Не найдено!", show_alert=True)
            return

        removed = quotes[idx]
        if delete_quote(user_id, idx):
            await callback.message.edit_text(
                f"✅ Удалено: {removed}\n\nОсталось {len(quotes) - 1} цитат"
            )
        else:
            await callback.answer("❌ Не удалось удалить!", show_alert=True)
    except ValueError:
        await callback.answer("❌ Неверный формат", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Error in delete_quote_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text("Отменено ✌️")
    except Exception as e:
        logging.error(f"❌ Error in cancel_delete: {e}")


# ============================================================
#            8. ОТНОШЕНИЯ И ГОДОВЩИНЫ (💕)
# ============================================================
@dp.message(F.text == "💕 Отношения")
async def show_relationship_menu(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    try:
        stats = calculate_relationship_stats()
        if stats:
            text = (
                f"💕 <b>НАШИ ОТНОШЕНИЯ</b> 💕\n\n"
                f"📅 Дата начала: <b>{stats['start_date']}</b>\n\n"
                f"🎉 <b>Статистика:</b>\n"
                f"   {stats['anniversaries']}\n\n"
                f"Это чудесное путешествие! ❤️"
            )
            builder = InlineKeyboardBuilder()
            builder.button(text="📝 Изменить дату", callback_data="edit_relationship_date")
            builder.button(text="🔙 Назад", callback_data="back_to_menu")
            builder.adjust(1)
            await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            text = "💕 <b>Отношения не настроены!</b>\n\nДавай установим дату начала?"
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Установить дату", callback_data="set_relationship_date")
            builder.button(text="🔙 Назад", callback_data="back_to_menu")
            builder.adjust(1)
            await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"❌ Error in show_relationship_menu: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())


@dp.callback_query(F.data == "set_relationship_date")
async def set_relationship_date_cb(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.set_state(MyStates.setting_relationship_date)
        await callback.message.edit_text(
            "📅 Напиши дату начала отношений: <b>YYYY-MM-DD</b>\n\n"
            "Например: <b>2023-06-15</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error(f"❌ Error in set_relationship_date_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data == "edit_relationship_date")
async def edit_relationship_date_cb(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.set_state(MyStates.setting_relationship_date)
        await callback.message.edit_text(
            "📅 Напиши новую дату: <b>YYYY-MM-DD</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error(f"❌ Error in edit_relationship_date_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.message(MyStates.setting_relationship_date, F.text)
async def save_relationship_date(message: types.Message, state: FSMContext):
    try:
        date_text = message.text.strip()
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ Неверный формат! Используй: YYYY-MM-DD (например, 2023-06-15)")
            return

        set_relationship_date_data(date_text)
        await state.clear()

        stats = calculate_relationship_stats()
        text = (
            f"✅ <b>Дата установлена!</b>\n\n"
            f"💕 Наши отношения:\n"
            f"📅 {stats['start_date']}\n\n"
            f"🎉 Статистика:\n"
            f"   {stats['anniversaries']}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"❌ Error in save_relationship_date: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при сохранении даты", reply_markup=main_menu())


# ============================================================
#              9. ВОСПОМИНАНИЯ (📸)
# ============================================================
@dp.message(F.text == "📸 Воспоминания")
async def show_memories_menu(message: types.Message, state: FSMContext):
    """Главный хендлер кнопки 📸 Воспоминания — показывает меню."""
    if not await check_access(message):
        return
    await state.clear()
    try:
        memories = get_memories(limit=50)
        count = len(memories)

        builder = InlineKeyboardBuilder()
        builder.button(text="📸 Добавить воспоминание", callback_data="add_memory_button")
        if count > 0:
            builder.button(text=f"📂 Все воспоминания ({count})", callback_data="show_all_memories")
        builder.button(text="🔙 Назад", callback_data="back_to_menu")
        builder.adjust(1)

        if count > 0:
            text = f"📸 <b>ВОСПОМИНАНИЯ</b>\n\nУ вас {count} воспоминаний. Что хочешь сделать?"
        else:
            text = "📸 <b>ВОСПОМИНАНИЯ</b>\n\nПока нет воспоминаний. Добавь первое! 💕"

        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"❌ Error in show_memories_menu: {e}")
        await message.answer("❌ Ошибка", reply_markup=main_menu())


@dp.callback_query(F.data == "add_memory_button")
async def add_memory_button_cb(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.set_state(MyStates.adding_memory)
        await callback.message.edit_text(
            "📸 <b>Поделись воспоминанием!</b>\n\n"
            "Можешь:\n"
            "• Написать текст\n"
            "• Отправить фото\n"
            "• Отправить видео\n"
            "• Отправить аудио\n"
            "• Отправить документ\n\n"
            "Отправь своё воспоминание:",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error(f"❌ Error in add_memory_button_cb: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.message(MyStates.adding_memory)
async def save_memory(message: types.Message, state: FSMContext):
    """Сохраняет воспоминание — текст, фото, видео, аудио, документ."""
    try:
        memory_data = {}

        if message.photo:
            memory_data["file_id"] = message.photo[-1].file_id
            memory_data["file_type"] = "photo"
            memory_data["text"] = message.caption or ""
            ctype = "📸 фото"
        elif message.video:
            memory_data["file_id"] = message.video.file_id
            memory_data["file_type"] = "video"
            memory_data["file_name"] = message.video.file_name or "video"
            memory_data["text"] = message.caption or ""
            ctype = "🎥 видео"
        elif message.audio:
            memory_data["file_id"] = message.audio.file_id
            memory_data["file_type"] = "audio"
            memory_data["file_name"] = message.audio.file_name or "audio"
            memory_data["text"] = message.caption or ""
            ctype = "🎵 аудио"
        elif message.document:
            memory_data["file_id"] = message.document.file_id
            memory_data["file_type"] = "document"
            memory_data["file_name"] = message.document.file_name or "document"
            memory_data["text"] = message.caption or ""
            ctype = "📄 документ"
        elif message.text:
            txt = message.text.strip()
            if not txt:
                await message.answer("⚠️ Пустое воспоминание!")
                return
            memory_data["text"] = txt
            ctype = "✍️ текст"
        else:
            await message.answer("⚠️ Неподдерживаемый тип. Отправь текст, фото, видео, аудио или документ.")
            return

        total = add_memory(memory_data)
        await state.clear()
        await message.answer(
            f"✅ Воспоминание сохранено! 💕\n\nТип: {ctype}\nВсего: {total}",
            reply_markup=main_menu(),
        )
    except Exception as e:
        logging.error(f"❌ Error in save_memory: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при сохранении", reply_markup=main_menu())


@dp.callback_query(F.data == "show_all_memories")
async def show_all_memories(callback: types.CallbackQuery):
    try:
        memories = get_memories(limit=50)
        if not memories:
            await callback.answer("Нет воспоминаний 😢", show_alert=True)
            return

        type_emoji = {"photo": "📸", "video": "🎥", "audio": "🎵", "document": "📄"}
        text = f"📸 <b>ВОСПОМИНАНИЯ ({len(memories)} шт.)</b>\n\n"

        for i, m in enumerate(memories, 1):
            try:
                date = datetime.fromisoformat(m["timestamp"]).strftime("%d.%m.%Y %H:%M")
            except Exception:
                date = "—"
            emoji = type_emoji.get(m.get("file_type"), "✍️")
            preview = m.get("text", "")[:50]
            text += f"{i}. {emoji} <b>{date}</b>"
            if preview:
                text += f"\n   <i>{preview}</i>"
            text += "\n\n"

        if len(text) > 4000:
            text = text[:3990] + "\n\n<i>… ещё</i>"

        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Error in show_all_memories: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
#            ОБЩИЕ INLINE-КНОПКИ
# ============================================================
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.delete()
        await bot.send_message(
            callback.from_user.id,
            "Главное меню 🏠",
            reply_markup=main_menu(),
        )
    except Exception as e:
        logging.error(f"❌ Error in back_to_menu: {e}")


# ============================================================
#         FALLBACK — НЕИЗВЕСТНЫЕ СООБЩЕНИЯ (ПОСЛЕДНИЙ!)
# ============================================================
@dp.message()
async def unknown_message(message: types.Message):
    if not await check_access(message):
        return
    await message.answer(
        "🤔 Не понимаю. Нажми /start чтобы открыть меню.",
        reply_markup=main_menu(),
    )


# ============================================================
#                        ЗАПУСК
# ============================================================
async def main():
    logging.info("�� Bot starting... (v3.0 — полный рефакторинг)")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Bot crashed: {e}")
        raise
    finally:
        await bot.session.close()
        logging.info("🛑 Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
