"""
Главный файл запуска — запускает бота (aiogram) и веб-сервер (aiohttp) параллельно.
Для Railway: одна команда стартует всё.
"""

import asyncio
import logging
import os
import shutil
import sys

logging.basicConfig(level=logging.INFO)

# Добавляем текущую директорию в путь
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def seed_data_volume():
    """
    Если DATA_DIR (Railway Volume /data) задан — копируем туда начальные
    JSON-файлы из репозитория, только если их там ещё нет.
    Это защищает данные: Volume переживает редеплои, а начальные значения
    не перезатирают уже накопленные воспоминания/цитаты.
    """
    data_dir = os.getenv("DATA_DIR", "")
    if not data_dir:
        return  # локальный запуск — ничего не делаем

    os.makedirs(data_dir, exist_ok=True)
    json_files = ["memories.json", "quotes.json", "relationship.json", "wishlist.json"]

    for fname in json_files:
        dest = os.path.join(data_dir, fname)
        src = os.path.join(BASE_DIR, fname)
        if not os.path.exists(dest):
            if os.path.exists(src):
                shutil.copy2(src, dest)
                logging.info(f"📦 Seeded {fname} → {data_dir}")
            else:
                logging.warning(f"⚠️  No seed file found for {fname}")

# Загружаем .env ДО импорта server.py (чтобы os.getenv работал)
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Сидируем Volume данными из репо при первом запуске
seed_data_volume()


async def main():
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from server import create_app

    # Импортируем бота
    from main import bot, dp, init_data_files, BOT_VERSION

    # Инициализация данных
    init_data_files()

    logging.info(f"🚀 Starting Piska Bot v{BOT_VERSION} + Mini App (webhook mode)...")

    # Webhook URL — используем публичный домен Railway (или переменную)
    public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    webhook_path = "/bot/webhook"

    if public_domain:
        webhook_url = f"https://{public_domain}{webhook_path}"
    else:
        # Локальный запуск — падаем обратно на polling
        logging.info("⚠️  No RAILWAY_PUBLIC_DOMAIN — using polling mode (local)")
        app = create_app()
        port = int(os.getenv("PORT", "8080"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logging.info(f"🌐 Web server running on port {port}")
        try:
            await dp.start_polling(bot)
        finally:
            await runner.cleanup()
            await bot.session.close()
        return

    # Создаём веб-приложение и подключаем webhook handler
    app = create_app()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    # Устанавливаем webhook при старте
    async def on_startup(_app):
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logging.info(f"✅ Webhook set: {webhook_url}")

    # Удаляем webhook при остановке
    async def on_shutdown(_app):
        await bot.delete_webhook()
        logging.info("🛑 Webhook deleted")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Запускаем веб-сервер
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 Web server + Webhook running on port {port}")

    # Ждём вечно (webhook сам обрабатывает обновления)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()
        logging.info("🛑 All stopped")


if __name__ == "__main__":
    asyncio.run(main())
