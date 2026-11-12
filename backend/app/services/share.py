"""Sharing my list: t.me/<bot>?startapp=list_<user id> opens the app on that list."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Invite codes are always 16 characters, so a short "list_<1-10 digits>" can never be
# mistaken for one (and fits Telegram's start-parameter rules: [A-Za-z0-9_-], <= 64).
_SHARE_CODE = re.compile(r"^list_(\d{1,10})$")


def share_code(user_id: int) -> str:
    return f"list_{user_id}"


def shared_user_id(code: str | None) -> int | None:
    match = _SHARE_CODE.match(code or "")
    return int(match.group(1)) if match else None


def share_link(bot_username: str, user_id: int) -> str:
    """Opens the bot's main Mini App directly (``startapp``) on this person's list.

    Needs the main Mini App enabled in @BotFather; otherwise Telegram opens the bot chat.
    Old ``?start=list_<id>`` links keep working through the bot.
    """
    return f"https://t.me/{bot_username}?startapp={share_code(user_id)}"


def app_url_for_person(webapp_url: str, person_id: int | None) -> str:
    """The Mini App URL, opening a person's list when ``person_id`` is given."""
    if person_id is None:
        return webapp_url
    parts = urlsplit(webapp_url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "person"]
    query.append(("person", str(person_id)))
    return urlunsplit(parts._replace(query=urlencode(query)))
