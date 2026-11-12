"""Who can be browsed in "Люди": users with access who have at least one wish."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import User, WishItem
from app.services.access import has_access_condition

_UK_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
_UK_ORDER = {ch: i for i, ch in enumerate(_UK_ALPHABET)}
# Apostrophes and hyphens don't affect order: «Мар'яна», «Анна-Марія».
_IGNORED = str.maketrans("", "", "'’ʼ-")


def name_sort_key(first_name: str, last_name: str | None) -> tuple[int, ...]:
    """Ukrainian alphabetical order (є, і, ї, ґ in place), then other letters."""

    def key(text: str) -> tuple[int, ...]:
        text = text.casefold().translate(_IGNORED)
        return tuple(_UK_ORDER.get(ch, 100 + ord(ch)) for ch in text)

    return (*key(first_name), -1, *key(last_name or ""))


@dataclass(frozen=True)
class Person:
    user: User
    wish_count: int


async def list_people(session: AsyncSession, settings: Settings, viewer: User) -> list[Person]:
    """Everyone with access and >= 1 wish except the viewer, sorted by name.

    Strangers who only opened the Mini App also have a ``users`` row; the access
    condition keeps them out of the list.
    """
    wish_count = func.count(WishItem.id)
    rows = await session.execute(
        select(User, wish_count)
        .join(WishItem, (WishItem.owner_id == User.id) & WishItem.received_at.is_(None))
        .where(User.id != viewer.id, has_access_condition(settings))
        .group_by(User.id)
    )
    found = [Person(user=user, wish_count=count) for user, count in rows.all()]
    return sorted(found, key=lambda p: name_sort_key(p.user.first_name, p.user.last_name))


async def get_person(session: AsyncSession, settings: Settings, user_id: int) -> User | None:
    """A user whose list may be browsed (has access); ``None`` otherwise."""
    return await session.scalar(
        select(User).where(User.id == user_id, has_access_condition(settings))
    )
