"""
Telegram Mini App API Server
Обслуживает веб-приложение и API для данных бота.
Работает параллельно с aiogram ботом.
"""

import asyncio
import json
import os
import logging
import hashlib
import hmac
import time
from urllib.parse import parse_qs
from datetime import datetime

import requests as http_requests
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# ============================================================
#                      КОНФИГ
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
DATA_DIR = os.getenv("DATA_DIR", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ALLOWED_USERS = {7118929376, 1428288113, 8481047835}

USER_NAMES = {
    7118929376: "Тёма",
    1428288113: "Артём",
    8481047835: "Майя",
}

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


# ============================================================
#                   РАБОТА С ДАННЫМИ
# ============================================================
def _data_path(name):
    if DATA_DIR:
        return os.path.join(DATA_DIR, f"{name}.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}.json")


def get_data(name):
    path = _data_path(name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_data(name, data):
    path = _data_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ============================================================
#               TELEGRAM INIT DATA VALIDATION
# ============================================================
def validate_init_data(init_data_raw: str) -> dict | None:
    """Проверяет подпись Telegram WebApp initData. Возвращает данные пользователя или None."""
    if not init_data_raw or not TELEGRAM_TOKEN:
        logging.warning("⚠️ initData validation: empty initData or token")
        return None

    try:
        from urllib.parse import unquote, parse_qsl

        # parse_qsl даёт список пар (key, value), а не массивы как parse_qs
        pairs = parse_qsl(init_data_raw, keep_blank_values=True)
        hash_value = None
        data_pairs = []

        for key, value in sorted(pairs, key=lambda x: x[0]):
            if key == "hash":
                hash_value = value
            else:
                data_pairs.append(f"{key}={value}")

        if not hash_value:
            logging.warning("⚠️ initData: no hash found")
            return None

        data_check_string = "\n".join(data_pairs)

        # Проверяем HMAC
        secret_key = hmac.new(b"WebAppData", TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if computed_hash != hash_value:
            logging.warning(f"⚠️ initData: hash mismatch")
            return None

        # Парсим user
        user_data = dict(pairs)
        user_raw = user_data.get("user")
        if user_raw:
            user = json.loads(user_raw)
            logging.info(f"✅ initData validated: user_id={user.get('id')}")
            return user

        logging.warning("⚠️ initData: no user field")
        return None
    except Exception as e:
        logging.error(f"❌ initData validation error: {e}")
        return None


def get_user_id(request) -> int | None:
    """Извлекает user_id из заголовка Telegram initData или query param uid."""
    # 1) Telegram WebApp initData (реальный Telegram)
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        user = validate_init_data(init_data)
        if user and user.get("id") in ALLOWED_USERS:
            return user["id"]
        logging.warning(f"⚠️ initData present but invalid or user not allowed")

    # 2) Fallback: uid из Telegram WebApp user (передаётся через JS)
    #    или debug ?uid= параметр
    debug_uid = request.query.get("uid")
    if debug_uid:
        try:
            uid_int = int(debug_uid)
            if uid_int in ALLOWED_USERS:
                return uid_int
        except ValueError:
            pass

    logging.warning(f"⚠️ No valid auth found. Headers: {dict(request.headers)}, Query: {dict(request.query)}")
    return None


# ============================================================
#                    API HANDLERS
# ============================================================

# --- WISHES (общие для всех!) ---
async def api_get_wishes(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    data = get_data("wishlist")
    # Собираем хотелки ВСЕХ пользователей с именами авторов
    all_wishes = []
    for user_id_str, wishes in data.items():
        author = USER_NAMES.get(int(user_id_str), "?")
        for w in wishes:
            if isinstance(w, str):
                all_wishes.append({"text": w, "author": author, "uid": user_id_str})
            elif isinstance(w, dict):
                w["author"] = w.get("author", author)
                w["uid"] = user_id_str
                all_wishes.append(w)
    return web.json_response({"data": all_wishes, "my_uid": str(uid)})


async def api_add_wish(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return web.json_response({"error": "empty text"}, status=400)
    data = get_data("wishlist")
    key = str(uid)
    if key not in data:
        data[key] = []
    data[key].append(text)
    save_data("wishlist", data)
    return web.json_response({"ok": True, "total": len(data[key])})


async def api_delete_wish(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    idx = int(request.match_info["idx"])
    owner = request.query.get("owner", str(uid))
    data = get_data("wishlist")
    if owner in data and 0 <= idx < len(data[owner]):
        data[owner].pop(idx)
        save_data("wishlist", data)
        return web.json_response({"ok": True})
    return web.json_response({"error": "not found"}, status=404)


# --- QUOTES (общие для всех!) ---
async def api_get_quotes(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    data = get_data("quotes")
    all_quotes = []
    for user_id_str, quotes in data.items():
        author = USER_NAMES.get(int(user_id_str), "?")
        for q in quotes:
            if isinstance(q, str):
                all_quotes.append({"text": q, "author": author, "uid": user_id_str})
            elif isinstance(q, dict):
                q["author"] = q.get("author", author)
                q["uid"] = user_id_str
                all_quotes.append(q)
    return web.json_response({"data": all_quotes, "my_uid": str(uid)})


async def api_add_quote(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return web.json_response({"error": "empty text"}, status=400)
    data = get_data("quotes")
    key = str(uid)
    if key not in data:
        data[key] = []
    data[key].append(text)
    save_data("quotes", data)
    return web.json_response({"ok": True, "total": len(data[key])})


async def api_delete_quote(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    idx = int(request.match_info["idx"])
    owner = request.query.get("owner", str(uid))
    data = get_data("quotes")
    if owner in data and 0 <= idx < len(data[owner]):
        data[owner].pop(idx)
        save_data("quotes", data)
        return web.json_response({"ok": True})
    return web.json_response({"error": "not found"}, status=404)


# --- MEMORIES ---
async def api_get_memories(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    data = get_data("memories")
    memories = data.get("memories", [])
    # Добавляем URL для фото (через Telegram Bot API getFile)
    for m in memories:
        if m.get("file_id"):
            m["file_url"] = f"/api/file/{m['file_id']}"
    return web.json_response({"data": list(reversed(memories[-50:]))})


async def api_add_memory(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)

    # Поддержка multipart (файл + текст)
    if request.content_type.startswith("multipart"):
        reader = await request.multipart()
        text = ""
        event_date = ""
        file_data = None
        file_name = ""

        async for part in reader:
            if part.name == "text":
                text = (await part.text()).strip()
            elif part.name == "event_date":
                event_date = (await part.text()).strip()
            elif part.name == "file":
                file_data = await part.read()
                file_name = part.filename or "file"
        # TODO: Для загрузки файлов через Mini App нужен Telegram Bot API
        # Пока сохраняем только текст
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_date": event_date or None,
            "text": text,
            "file_id": None,
            "file_type": None,
            "file_name": file_name,
        }
    else:
        body = await request.json()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_date": body.get("event_date") or None,
            "text": body.get("text", ""),
            "file_id": None,
            "file_type": None,
            "file_name": "",
        }

    data = get_data("memories")
    if "memories" not in data:
        data["memories"] = []
    data["memories"].append(entry)
    save_data("memories", data)
    return web.json_response({"ok": True, "total": len(data["memories"])})


async def api_delete_memory(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    idx = int(request.match_info["idx"])
    data = get_data("memories")
    memories = data.get("memories", [])
    # Индекс в API — от reversed list, переводим в реальный
    real_idx = len(memories) - 1 - idx
    if 0 <= real_idx < len(memories):
        memories.pop(real_idx)
        data["memories"] = memories
        save_data("memories", data)
        return web.json_response({"ok": True})
    return web.json_response({"error": "not found"}, status=404)


# --- RELATIONSHIP (общая для всех!) ---
async def api_get_relationship(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    data = get_data("relationship")
    start_date_str = data.get("start_date")
    if not start_date_str:
        return web.json_response({"data": None})
    try:
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        days = (datetime.now() - start).days
        return web.json_response({"data": {
            "start_date": start_date_str,
            "days": days,
            "months": days // 30,
            "years": days // 365,
        }})
    except Exception:
        return web.json_response({"data": None})


async def api_set_relationship(request):
    """Установить дату начала отношений — одна на всех."""
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    date_str = body.get("date", "").strip()
    if not date_str:
        return web.json_response({"error": "empty date"}, status=400)
    try:
        # Валидация формата
        datetime.strptime(date_str, "%Y-%m-%d")
        data = get_data("relationship")
        data["start_date"] = date_str
        data["set_by"] = uid
        save_data("relationship", data)
        logging.info(f"💕 Relationship date set to {date_str} by user {uid}")
        return web.json_response({"ok": True})
    except ValueError:
        return web.json_response({"error": "invalid date format, use YYYY-MM-DD"}, status=400)


# --- AI ---
async def api_ai(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return web.json_response({"error": "empty"}, status=400)

    def sync_ai():
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "MayaBot",
        }
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": message}],
        }
        try:
            resp = http_requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            logging.info(f"🤖 AI response status: {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                return result["choices"][0]["message"]["content"]
            else:
                logging.error(f"🤖 AI error response: {resp.text[:500]}")
        except Exception as e:
            logging.error(f"AI error: {e}")
        return None

    reply = await asyncio.to_thread(sync_ai)
    if reply:
        return web.json_response({"reply": reply})
    return web.json_response({"error": "ai_error", "detail": "OpenRouter API failed"}, status=500)


# --- FACT ---
async def api_fact(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_name = USER_NAMES.get(uid, "друг")

    def sync_fact():
        prompt = f"Расскажи один милый, забавный или интересный факт про девушку по имени Майя. Обращайся к {user_name}. Ответ до 3 предложений."
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
            resp = http_requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            logging.info(f"✨ Fact response status: {resp.status_code}")
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                logging.error(f"✨ Fact error response: {resp.text[:500]}")
        except Exception as e:
            logging.error(f"Fact error: {e}")
        return None

    fact = await asyncio.to_thread(sync_fact)
    if fact:
        return web.json_response({"fact": fact})
    return web.json_response({"error": "ai_error", "detail": "OpenRouter API failed"}, status=500)


# --- SECRET MESSAGE ---
async def api_secret(request):
    uid = get_user_id(request)
    if not uid:
        return web.json_response({"error": "unauthorized"}, status=401)
    body = await request.json()
    to_user_id = body.get("to_user_id")
    text = body.get("text", "").strip()
    if not text or not to_user_id:
        return web.json_response({"error": "missing data"}, status=400)

    try:
        # Отправляем через Telegram Bot API напрямую (без создания нового бота)
        sender_name = USER_NAMES.get(uid, "Кто-то")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": to_user_id,
            "text": f"💌 <b>Тебе тайное сообщение!</b>\n\n{text}",
            "parse_mode": "HTML",
        }
        resp = await asyncio.to_thread(
            lambda: http_requests.post(url, json=payload, timeout=10)
        )
        if resp.status_code == 200:
            logging.info(f"💌 Secret message from {uid} to {to_user_id}")
            return web.json_response({"ok": True})
        else:
            logging.error(f"Secret message API error: {resp.status_code} {resp.text}")
            return web.json_response({"error": "telegram_error"}, status=500)
    except Exception as e:
        logging.error(f"Secret message error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# --- FILE PROXY (для отображения фото из Telegram) ---
async def api_get_file(request):
    """Проксирует файлы из Telegram. Не требует auth (URL не угадать)."""
    file_id = request.match_info["file_id"]
    if not TELEGRAM_TOKEN:
        return web.Response(status=503, text="Bot token not configured")
    try:
        # Получаем путь к файлу через Telegram Bot API
        resp = http_requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10,
        )
        if resp.status_code != 200:
            return web.Response(status=404)
        file_path = resp.json()["result"]["file_path"]

        # Скачиваем файл
        file_resp = http_requests.get(
            f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}",
            timeout=30,
        )
        if file_resp.status_code != 200:
            return web.Response(status=404)

        content_type = "image/jpeg"
        if file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".mp4"):
            content_type = "video/mp4"

        return web.Response(body=file_resp.content, content_type=content_type)
    except Exception as e:
        logging.error(f"File proxy error: {e}")
        return web.Response(status=500)


# ============================================================
#                   WEB SERVER
# ============================================================

@web.middleware
async def cors_middleware(request, handler):
    """Добавляем CORS заголовки для Telegram WebApp."""
    if request.method == 'OPTIONS':
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-Init-Data'
    return response


def create_app():
    app = web.Application(middlewares=[cors_middleware])

    # API routes
    app.router.add_get('/api/wishes', api_get_wishes)
    app.router.add_post('/api/wishes', api_add_wish)
    app.router.add_delete('/api/wishes/{idx}', api_delete_wish)

    app.router.add_get('/api/quotes', api_get_quotes)
    app.router.add_post('/api/quotes', api_add_quote)
    app.router.add_delete('/api/quotes/{idx}', api_delete_quote)

    app.router.add_get('/api/memories', api_get_memories)
    app.router.add_post('/api/memories', api_add_memory)
    app.router.add_delete('/api/memories/{idx}', api_delete_memory)

    app.router.add_get('/api/relationship', api_get_relationship)
    app.router.add_post('/api/relationship', api_set_relationship)

    app.router.add_post('/api/ai', api_ai)
    app.router.add_get('/api/fact', api_fact)
    app.router.add_post('/api/secret', api_secret)

    app.router.add_get('/api/file/{file_id}', api_get_file)

    # Static files (webapp)
    app.router.add_static('/static/', WEBAPP_DIR, show_index=False)

    # Index — serve webapp
    async def index(request):
        return web.FileResponse(os.path.join(WEBAPP_DIR, 'index.html'))

    app.router.add_get('/', index)

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logging.info(f"🌐 Starting web server on port {port}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
