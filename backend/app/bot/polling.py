"""Run the bot in long-polling mode for local development.

Usage: ``uv run python -m app.bot.polling``. Docker Compose runs it as the ``bot`` service.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.bot.handlers import router
from app.config import get_settings


async def set_menu_button(bot: Bot, webapp_url: str) -> None:
    """«Відкрити» next to the message field, always pointing at the current app URL
    (the dev tunnel URL changes on every restart)."""
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Відкрити", web_app=WebAppInfo(url=webapp_url))
        )
    except Exception:  # never block the bot because of the button
        logging.getLogger(__name__).exception("Failed to set the menu button")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")
    bot = Bot(settings.bot_token)
    await set_menu_button(bot, settings.webapp_url)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
