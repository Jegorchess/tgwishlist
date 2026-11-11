from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Priority, User, WishItem


async def create_wish(
    session: AsyncSession,
    owner: User,
    *,
    title: str,
    price: Decimal | None,
    priority: Priority,
    url: str | None,
    description: str | None,
    photo_name: str | None,
) -> WishItem:
    wish = WishItem(
        owner_id=owner.id,
        title=title,
        price=price,
        priority=priority,
        url=url,
        description=description,
        photo_name=photo_name,
    )
    session.add(wish)
    await session.commit()
    await session.refresh(wish)
    return wish


async def list_own_wishes(session: AsyncSession, owner: User) -> list[WishItem]:
    """Owner's wishes: most wanted first, newest first within the same priority."""
    result = await session.scalars(
        select(WishItem)
        .where(WishItem.owner_id == owner.id)
        .order_by(WishItem.priority, WishItem.created_at.desc(), WishItem.id.desc())
    )
    return list(result)


async def get_wish_for_reader(session: AsyncSession, wish_id: int, reader: User) -> WishItem | None:
    """Return the wish if ``reader`` may see it.

    Families come in iteration 2; until then only the owner can see their wishes.
    """
    return await session.scalar(
        select(WishItem).where(WishItem.id == wish_id, WishItem.owner_id == reader.id)
    )
