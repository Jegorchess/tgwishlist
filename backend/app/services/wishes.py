from decimal import Decimal

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Priority, Reservation, User, WishItem
from app.services.access import has_access_condition


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
    """Owner's active wishes: most wanted first, newest first within the same priority.

    Used both for "my wishes" and for browsing another person's list. Received
    (archived) wishes are not included.
    """
    result = await session.scalars(
        select(WishItem)
        .where(WishItem.owner_id == owner.id, WishItem.received_at.is_(None))
        .order_by(WishItem.priority, WishItem.created_at.desc(), WishItem.id.desc())
    )
    return list(result)


async def list_archived_wishes(session: AsyncSession, owner: User) -> list[WishItem]:
    """The owner's received wishes, most recently received first."""
    result = await session.scalars(
        select(WishItem)
        .where(WishItem.owner_id == owner.id, WishItem.received_at.is_not(None))
        .order_by(WishItem.received_at.desc(), WishItem.id.desc())
    )
    return list(result)


async def mark_received(session: AsyncSession, wish: WishItem) -> None:
    """Archive the wish; its reservation (if any) is closed. The caller notifies the gifter."""
    wish.received_at = func.now()
    await session.execute(delete(Reservation).where(Reservation.wish_id == wish.id))
    await session.commit()


async def restore_wish(session: AsyncSession, wish: WishItem) -> None:
    wish.received_at = None
    await session.commit()


async def get_wish_for_reader(
    session: AsyncSession, settings: Settings, wish_id: int, reader: User
) -> WishItem | None:
    """A wish ``reader`` may see: any of their own, or someone's active wish while that
    owner has access (same rule as «Люди»). Received wishes are private to the owner.

    The reader's own access is checked by the caller (MemberUser).
    """
    return await session.scalar(
        select(WishItem)
        .join(User, User.id == WishItem.owner_id)
        .where(
            WishItem.id == wish_id,
            or_(
                WishItem.owner_id == reader.id,
                and_(WishItem.received_at.is_(None), has_access_condition(settings)),
            ),
        )
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
    # Explicit (not only ON DELETE CASCADE): SQLite doesn't enforce foreign keys by default.
    await session.execute(delete(Reservation).where(Reservation.wish_id == wish.id))
    await session.delete(wish)
    await session.commit()
    return photo
