from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.deps import AdminUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.services.access import is_admin, list_members, restore_access, revoke_access

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MemberOut(BaseModel):
    telegram_id: int  # admin-only endpoint: the id identifies the person for actions
    first_name: str
    last_name: str | None
    photo_url: str | None
    granted_at: datetime
    revoked: bool
    is_admin: bool  # admins from settings can't be blocked: the app shows no button


@router.get("/members")
async def members(
    _: AdminUser, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> list[MemberOut]:
    """Everyone who joined via the invite link, including blocked people."""
    return [
        MemberOut(
            telegram_id=m.telegram_id,
            first_name=m.first_name,
            last_name=m.last_name,
            photo_url=m.photo_url,
            granted_at=m.granted_at,
            revoked=m.revoked_at is not None,
            is_admin=is_admin(settings, m.telegram_id),
        )
        for m in await list_members(session)
    ]


@router.post("/members/{telegram_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    telegram_id: int,
    _: AdminUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Block the person: no app, no wishes visible, reservations released, link won't work."""
    if is_admin(settings, telegram_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins can't be blocked")
    if not await revoke_access(session, telegram_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")


@router.post("/members/{telegram_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore(telegram_id: int, _: AdminUser, session: SessionDep) -> None:
    if not await restore_access(session, telegram_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
