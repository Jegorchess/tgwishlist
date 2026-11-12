from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import MemberUser
from app.config import Settings, get_settings
from app.services.bot_info import bot_username
from app.services.share import share_link

router = APIRouter(prefix="/api", tags=["share"])


class ShareLinkOut(BaseModel):
    link: str


@router.get("/share-link")
async def my_share_link(
    user: MemberUser, settings: Annotated[Settings, Depends(get_settings)]
) -> ShareLinkOut:
    """A link to my list: opens the bot, which opens the app on my wishes.

    Uses the internal user id (never the Telegram id) and grants no access by itself.
    """
    return ShareLinkOut(link=share_link(await bot_username(settings), user.id))
