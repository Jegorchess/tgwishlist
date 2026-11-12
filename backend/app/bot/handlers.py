import logging
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.services.access import has_access, is_blocked, redeem_invite

router = Router()
log = logging.getLogger(__name__)

WELCOME = (
    "Привіт! Це Хотєлочки — вішліст для рідних і друзів. Натисни кнопку, щоб відкрити застосунок."
)
JOINED = "Вітаю! Тепер у тебе є доступ до Хотєлочок 🎁"
INVALID_INVITE = "Посилання недійсне. Попроси нове в того, хто тебе запросив."
PRIVATE = "Це приватні Хотєлочки. Доступ — лише за запрошенням."
BLOCKED = "Доступ закрито. Звернись до того, хто тебе запросив."
FAILED = "Щось пішло не так. Спробуй ще раз трохи пізніше."


@dataclass(frozen=True)
class StartReply:
    text: str
    show_app_button: bool


async def start_reply(
    session: AsyncSession,
    settings: Settings,
    telegram_id: int,
    code: str | None,
    first_name: str | None = None,
) -> StartReply:
    """What the bot answers to ``/start`` or ``/start <invite code>``."""
    if await has_access(session, settings, telegram_id):
        return StartReply(WELCOME, True)
    if await is_blocked(session, telegram_id):
        return StartReply(BLOCKED, False)
    if not code:
        return StartReply(PRIVATE, False)
    if await redeem_invite(session, telegram_id, code, first_name):
        return StartReply(JOINED, True)
    return StartReply(INVALID_INVITE, False)


# Private chats only: Telegram rejects Mini App buttons in groups.
@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message, command: CommandObject) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    try:
        async with get_sessionmaker()() as session:
            reply = await start_reply(
                session,
                settings,
                message.from_user.id,
                command.args,
                message.from_user.first_name,
            )
    except Exception:
        log.exception("Failed to handle /start")
        await message.answer(FAILED)
        return

    keyboard = None
    if reply.show_app_button:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎁 Відкрити Хотєлочки", web_app=WebAppInfo(url=settings.webapp_url)
                    )
                ]
            ]
        )
    await message.answer(reply.text, reply_markup=keyboard)
