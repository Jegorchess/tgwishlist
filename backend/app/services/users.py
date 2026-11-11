from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.telegram import TelegramUser
from app.models import User


async def get_or_create_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    """Return the user for this Telegram account, creating it on first login.

    Profile data is captured once, at registration; later logins do not change it.
    """
    query = select(User).where(User.telegram_id == tg_user.id)
    user = await session.scalar(query)
    if user is not None:
        return user

    user = User(
        telegram_id=tg_user.id,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        username=tg_user.username,
        language_code=tg_user.language_code,
        photo_url=tg_user.photo_url,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Two first requests raced each other: the other one created the user.
        await session.rollback()
        user = await session.scalar(query)
        if user is None:
            raise
    return user
