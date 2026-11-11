from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth.telegram import InitData, InitDataError, TelegramUser, validate_init_data
from app.config import Settings, get_settings

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
