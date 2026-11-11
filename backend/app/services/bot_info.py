from aiogram import Bot

from app.config import Settings

_username: str | None = None


async def bot_username(settings: Settings) -> str:
    """The bot's @username (without @): from settings, else asked from Telegram once."""
    global _username
    if settings.bot_username:
        return settings.bot_username.lstrip("@")
    if _username is None:
        async with Bot(settings.bot_token) as bot:
            _username = (await bot.get_me()).username or ""
    return _username
