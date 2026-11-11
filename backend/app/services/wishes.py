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


async def get_own_wish(session: AsyncSession, wish_id: int, owner: User) -> WishItem | None:
    """The wish only if ``owner`` created it: changing and deleting is owner-only.

    The row is locked until commit, so two overlapping edits can't both replace the photo
    and leave one file orphaned.
    """
    return await session.scalar(
        select(WishItem)
        .where(WishItem.id == wish_id, WishItem.owner_id == owner.id)
        .with_for_update()
    )


async def update_wish(
    session: AsyncSession,
    wish: WishItem,
    *,
    title: str,
    price: Decimal | None,
    priority: Priority,
    url: str | None,
    description: str | None,
    new_photo_name: str | None,
    remove_photo: bool,
) -> str | None:
    """Replace the wish's fields and commit.

    Returns the name of a photo file that is no longer used. The caller refreshes ``wish``.
    """
    wish.title = title
    wish.price = price
    wish.priority = priority
    wish.url = url
    wish.description = description
    old_photo = wish.photo_name
    if new_photo_name:
        wish.photo_name = new_photo_name
    elif remove_photo:
        wish.photo_name = None
    unused = old_photo if old_photo != wish.photo_name else None
    await session.commit()
    return unused


async def delete_wish(session: AsyncSession, wish: WishItem) -> str | None:
    """Delete the wish. Returns its photo file name so the caller can remove the file."""
    photo = wish.photo_name
    await session.delete(wish)
    await session.commit()
    return photo
