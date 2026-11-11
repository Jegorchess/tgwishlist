"""Run the bot in long-polling mode for local development.

Usage: ``uv run python -m app.bot.polling``. In production the bot will run via webhook.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.config import get_settings


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
