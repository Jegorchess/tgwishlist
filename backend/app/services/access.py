"""Invite-only access: who may use the app, and the invite link."""

import secrets

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AccessGrant, Invite

CODE_BYTES = 12  # -> 16 URL-safe characters


def is_admin(settings: Settings, telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids


async def has_access(session: AsyncSession, settings: Settings, telegram_id: int) -> bool:
    if is_admin(settings, telegram_id):
        return True
    return await session.get(AccessGrant, telegram_id) is not None


async def _newest_active_code(session: AsyncSession) -> str | None:
    return await session.scalar(
        select(Invite.code).where(Invite.active).order_by(Invite.id.desc()).limit(1)
    )


async def current_invite_code(session: AsyncSession) -> str:
    """The active invite code, created on first use."""
    code = await _newest_active_code(session)
    return code if code is not None else await regenerate_invite_code(session)


async def regenerate_invite_code(session: AsyncSession) -> str:
    """Deactivate old codes and create a new one. Existing grants are kept."""
    await session.execute(update(Invite).where(Invite.active).values(active=False))
    code = secrets.token_urlsafe(CODE_BYTES)
    session.add(Invite(code=code))
    await session.commit()
    return code


async def redeem_invite(session: AsyncSession, telegram_id: int, code: str) -> bool:
    """Grant access if ``code`` is the current invite. Returns whether access was granted."""
    newest = await _newest_active_code(session)
    if newest is None or not secrets.compare_digest(newest, code):
        return False
    session.add(AccessGrant(telegram_id=telegram_id))
    try:
        await session.commit()
    except IntegrityError:  # granted concurrently
        await session.rollback()
    return True


def invite_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={code}"
