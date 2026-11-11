from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth.telegram import InitData, InitDataError, TelegramUser, validate_init_data
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User
from app.services.access import has_access, is_admin
from app.services.users import get_or_create_user

DEV_USER = TelegramUser(id=1, first_name="Dev", username="dev")


def current_init_data(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> InitData:
    """Authenticate a request by the ``Authorization: tma <initData>`` header."""
    scheme, _, value = (authorization or "").partition(" ")

    if settings.dev_auth and scheme.lower() == "dev":
        return InitData(user=DEV_USER, auth_date=0)

    if scheme.lower() != "tma" or not value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Telegram initData")
    try:
        return validate_init_data(value, settings.bot_token, settings.init_data_max_age)
    except InitDataError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


CurrentInitData = Annotated[InitData, Depends(current_init_data)]


async def current_user(init_data: CurrentInitData, session: SessionDep) -> User:
    """The authenticated user's profile; created automatically on first login."""
    return await get_or_create_user(session, init_data.user)


CurrentUser = Annotated[User, Depends(current_user)]


async def member_user(
    user: CurrentUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """A user who joined via the invite link (or an admin). Everyone else gets 403."""
    if not await has_access(session, settings, user.telegram_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access is by invitation only")
    return user


MemberUser = Annotated[User, Depends(member_user)]


def admin_user(user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]) -> User:
    if not is_admin(settings, user.telegram_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


AdminUser = Annotated[User, Depends(admin_user)]
