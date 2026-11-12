"""Invite-only access: who may use the app, and the invite link."""

import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AccessGrant, Invite, Reservation, User

CODE_BYTES = 12  # -> 16 URL-safe characters


def is_admin(settings: Settings, telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids


def has_access_condition(settings: Settings) -> ColumnElement[bool]:
    """SQL condition on ``User``: joined via an invite (and not revoked) or is an admin."""
    granted = exists().where(
        AccessGrant.telegram_id == User.telegram_id, AccessGrant.revoked_at.is_(None)
    )
    return or_(granted, User.telegram_id.in_(settings.admin_ids))


async def has_access(session: AsyncSession, settings: Settings, telegram_id: int) -> bool:
    if is_admin(settings, telegram_id):
        return True
    grant = await session.get(AccessGrant, telegram_id)
    return grant is not None and grant.revoked_at is None


async def is_blocked(session: AsyncSession, telegram_id: int) -> bool:
    grant = await session.get(AccessGrant, telegram_id)
    return grant is not None and grant.revoked_at is not None


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


async def redeem_invite(
    session: AsyncSession, telegram_id: int, code: str, first_name: str | None = None
) -> bool:
    """Grant access if ``code`` is the current invite. Returns whether access was granted.

    A blocked person (access revoked by the admin) is never let back in by a link.
    """
    if await is_blocked(session, telegram_id):
        return False
    newest = await _newest_active_code(session)
    if newest is None or not secrets.compare_digest(newest, code):
        return False
    session.add(AccessGrant(telegram_id=telegram_id, first_name=first_name))
    try:
        await session.commit()
    except IntegrityError:  # a grant appeared concurrently (or was just revoked)
        await session.rollback()
        return not await is_blocked(session, telegram_id)
    return True


def invite_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={code}"


@dataclass(frozen=True)
class Member:
    telegram_id: int
    first_name: str
    last_name: str | None
    photo_url: str | None
    granted_at: datetime
    revoked_at: datetime | None


async def list_members(session: AsyncSession) -> list[Member]:
    """Everyone who joined via an invite (blocked ones too), newest first."""
    rows = await session.execute(
        select(AccessGrant, User)
        .outerjoin(User, User.telegram_id == AccessGrant.telegram_id)
        .order_by(AccessGrant.granted_at.desc(), AccessGrant.telegram_id)
    )
    return [
        Member(
            telegram_id=grant.telegram_id,
            first_name=(user.first_name if user else grant.first_name) or "Без імені",
            last_name=user.last_name if user else None,
            photo_url=user.photo_url if user else None,
            granted_at=grant.granted_at,
            revoked_at=grant.revoked_at,
        )
        for grant, user in rows.all()
    ]


async def revoke_access(session: AsyncSession, telegram_id: int) -> bool:
    """Block the person and release their reservations. False if they never joined."""
    grant = await session.get(AccessGrant, telegram_id)
    if grant is None:
        return False
    if grant.revoked_at is None:
        grant.revoked_at = func.now()
        user_id = select(User.id).where(User.telegram_id == telegram_id).scalar_subquery()
        await session.execute(delete(Reservation).where(Reservation.reserver_id == user_id))
        await session.commit()
    return True


async def restore_access(session: AsyncSession, telegram_id: int) -> bool:
    grant = await session.get(AccessGrant, telegram_id)
    if grant is None:
        return False
    grant.revoked_at = None
    await session.commit()
    return True
