from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.config import get_settings

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Відкрити вішліст",
                    web_app=WebAppInfo(url=get_settings().webapp_url),
                )
            ]
        ]
    )
    await message.answer(
        "Привіт! Це сімейний вішліст. Натисни кнопку, щоб відкрити застосунок.",
        reply_markup=keyboard,
    )
