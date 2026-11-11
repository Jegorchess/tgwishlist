"""Validation of Telegram Mini App ``initData``.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """Raised when initData is missing, malformed, forged or expired."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    photo_url: str | None = None


@dataclass(frozen=True)
class InitData:
    user: TelegramUser
    auth_date: int
    start_param: str | None = None


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign(fields: dict[str, str], bot_token: str) -> str:
    """Compute the ``hash`` for the given fields. Used by tests and dev tooling."""
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    return hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()


def validate_init_data(
    raw: str, bot_token: str, max_age: int, now: float | None = None
) -> InitData:
    if not raw:
        raise InitDataError("initData is empty")
    if not bot_token:
        raise InitDataError("bot token is not configured")

    fields = dict(parse_qsl(raw, keep_blank_values=True, strict_parsing=False))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash is missing")

    expected_hash = sign(fields, bot_token)
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("signature mismatch")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as exc:
        raise InitDataError("auth_date is missing or invalid") from exc

    current = time.time() if now is None else now
    if max_age > 0 and current - auth_date > max_age:
        raise InitDataError("initData expired")

    try:
        user_raw = json.loads(fields["user"])
        user = TelegramUser(
            id=int(user_raw["id"]),
            first_name=user_raw.get("first_name", ""),
            last_name=user_raw.get("last_name"),
            username=user_raw.get("username"),
            language_code=user_raw.get("language_code"),
            photo_url=user_raw.get("photo_url"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InitDataError("user is missing or invalid") from exc

    return InitData(user=user, auth_date=auth_date, start_param=fields.get("start_param"))
