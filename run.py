"""
Главный файл запуска — запускает бота (aiogram) и веб-сервер (aiohttp) параллельно.
Для Railway: одна команда стартует всё.
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from aiohttp import web
    from server import create_app

    # Импортируем бота
    from main import bot, dp, init_data_files, BOT_VERSION

    # Инициализация данных
    init_data_files()

    logging.info(f"🚀 Starting Piska Bot v{BOT_VERSION} + Mini App...")

    # Создаём веб-приложение
    app = create_app()

    # Запускаем веб-сервер
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 Web server running on port {port}")

    # Запускаем бота
    logging.info("🤖 Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Bot crashed: {e}")
    finally:
        await runner.cleanup()
        await bot.session.close()
        logging.info("🛑 All stopped")


if __name__ == "__main__":
    asyncio.run(main())
