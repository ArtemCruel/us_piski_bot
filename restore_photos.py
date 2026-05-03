"""
Восстанавливает 42 фото в бота.
1. Отправляет каждое фото боту через Telegram Bot API → получает file_id
2. Собирает список воспоминаний
3. Отправляет на admin-endpoint бота → сохраняет в Volume /data/memories.json

Запуск: python3 restore_photos.py
"""
import os
import re
import time
import requests
from datetime import datetime
from pathlib import Path

TOKEN = "8682882436:AAEveTZwakXKQLGPjCGKx4H7KCs3ZbPnetU"
CHAT_ID = 7118929376  # Тёма — фото отправляются в его личный чат с ботом
BOT_API = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_URL = "https://uspiskibot-production.up.railway.app/api/admin/import-memories"
ADMIN_SECRET = "piski-restore-2026"

PHOTOS_DIR = Path("/Users/byteup/Downloads/тг восп")

photos = sorted(PHOTOS_DIR.glob("*.jpg"))
print(f"📂 Найдено фото: {len(photos)}")

memories = []

for i, photo_path in enumerate(photos):
    fname = photo_path.stem  # "2026-05-02 18.05.28"
    # Парсим дату из имени файла
    try:
        dt = datetime.strptime(fname, "%Y-%m-%d %H.%M.%S")
        timestamp = dt.isoformat()
    except ValueError:
        timestamp = datetime.now().isoformat()

    print(f"  [{i+1}/{len(photos)}] Загружаю {photo_path.name}...", end=" ")

    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(
                f"{BOT_API}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": "📸 восстановление воспоминания"},
                files={"photo": f},
                timeout=30,
            )

        if resp.status_code != 200:
            print(f"❌ HTTP {resp.status_code}: {resp.text[:100]}")
            continue

        result = resp.json()
        if not result.get("ok"):
            print(f"❌ Telegram error: {result.get('description')}")
            continue

        # Берём самый большой размер фото
        photos_list = result["result"]["photo"]
        biggest = max(photos_list, key=lambda p: p["file_size"])
        file_id = biggest["file_id"]

        memories.append({
            "timestamp": timestamp,
            "text": "",
            "file_id": file_id,
            "file_type": "photo",
            "file_name": photo_path.name,
        })
        print(f"✅ file_id получен")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

    time.sleep(0.3)  # небольшая пауза чтобы не флудить API

print(f"\n📦 Собрано воспоминаний: {len(memories)}")
print("🚀 Отправляю на бот-сервер...")

resp = requests.post(
    ADMIN_URL,
    json={"memories": memories},
    headers={"X-Admin-Secret": ADMIN_SECRET},
    timeout=30,
)

print(f"Статус: {resp.status_code}")
try:
    print(resp.json())
except Exception:
    print(resp.text[:300])
