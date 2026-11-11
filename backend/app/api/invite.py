from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import AdminUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.services.access import current_invite_code, invite_link, regenerate_invite_code
from app.services.bot_info import bot_username

router = APIRouter(prefix="/api/invite", tags=["invite"])


class InviteOut(BaseModel):
    link: str


@router.get("")
async def get_invite(
    _: AdminUser, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> InviteOut:
    code = await current_invite_code(session)
    return InviteOut(link=invite_link(await bot_username(settings), code))


@router.post("/regenerate")
async def regenerate_invite(
    _: AdminUser, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> InviteOut:
    """The old link stops working at once; people who already joined keep access."""
    code = await regenerate_invite_code(session)
    return InviteOut(link=invite_link(await bot_username(settings), code))
