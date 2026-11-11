from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.auth.deps import CurrentInitData, CurrentUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.services.access import has_access, is_admin

router = APIRouter(prefix="/api", tags=["me"])


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    photo_url: str | None
    start_param: str | None = None
    has_access: bool = False
    is_admin: bool = False


@router.get("/me")
async def me(
    user: CurrentUser,
    init_data: CurrentInitData,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeOut:
    """Available without access: the app uses it to show the "invitation only" screen."""
    out = MeOut.model_validate(user)
    out.start_param = init_data.start_param
    out.has_access = await has_access(session, settings, user.telegram_id)
    out.is_admin = is_admin(settings, user.telegram_id)
    return out
