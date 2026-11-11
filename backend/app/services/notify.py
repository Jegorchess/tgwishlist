"""Messages from the bot to users (e.g. a reserved wish was deleted)."""

import logging
from typing import Annotated, Protocol

from aiogram import Bot
from fastapi import Depends

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


class Notifier(Protocol):
    async def send(self, telegram_id: int, text: str) -> None: ...


class BotNotifier:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.bot_token

    async def send(self, telegram_id: int, text: str) -> None:
        """Best effort: a failed notification must never break the request."""
        try:
            async with Bot(self._token) as bot:
                await bot.send_message(telegram_id, text)
        except Exception:
            log.exception("Failed to notify telegram_id=%s", telegram_id)


def get_notifier(settings: Annotated[Settings, Depends(get_settings)]) -> Notifier:
    return BotNotifier(settings)
