"""Shared test helpers: signed initData and auth headers."""

import json
import time
from urllib.parse import urlencode

from app.auth.telegram import sign

TOKEN = "123456:TEST-TOKEN"
MAX_AGE = 3600


def make_init_data(
    token: str = TOKEN, auth_date: int | None = None, user: dict | None = None, **extra: str
) -> str:
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user or {"id": 42, "first_name": "Єгор", "username": "jegor"}),
        **extra,
    }
    fields["hash"] = sign(fields, token)
    return urlencode(fields)


def auth(init_data: str | None = None) -> dict[str, str]:
    return {"Authorization": f"tma {init_data or make_init_data()}"}
