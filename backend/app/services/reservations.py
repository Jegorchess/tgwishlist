"""«Я дарую»: reserving someone else's wish so nobody buys the same gift."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Reservation, User, WishItem
from app.services.access import has_access_condition


class ReservationError(Exception):
    pass


class OwnWish(ReservationError):
    """Reserving your own wish would spoil nothing but makes no sense."""


class AlreadyReserved(ReservationError):
    pass


class WishGone(ReservationError):
    """The wish was deleted while we were reserving it."""


@dataclass(frozen=True)
class ReservationView:
    """What a non-owner sees about a wish's reservation."""

    mine: bool
    by_name: str


@dataclass(frozen=True)
class MyReservation:
    wish: WishItem
    owner: User
    owner_wish_count: int


async def reservations_for(
    session: AsyncSession, wish_ids: list[int], viewer: User
) -> dict[int, ReservationView]:
    """Reservations of the given wishes, as seen by ``viewer`` (who must not be their owner)."""
    if not wish_ids:
        return {}
    rows = await session.execute(
        select(Reservation.wish_id, User.id, User.first_name)
        .join(User, User.id == Reservation.reserver_id)
        .where(Reservation.wish_id.in_(wish_ids))
    )
    return {
        wish_id: ReservationView(mine=user_id == viewer.id, by_name=first_name)
        for wish_id, user_id, first_name in rows.all()
    }


async def reserve(session: AsyncSession, wish: WishItem, reserver: User) -> None:
    if wish.owner_id == reserver.id:
        raise OwnWish
    wish_id = wish.id  # attributes expire on rollback; keep the id
    session.add(Reservation(wish_id=wish_id, reserver_id=reserver.id))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # Either the primary key (someone was faster) or the FK (the wish was just deleted).
        if await session.scalar(select(WishItem.id).where(WishItem.id == wish_id)) is None:
            raise WishGone from exc
        raise AlreadyReserved from exc


async def cancel(session: AsyncSession, wish_id: int, reserver: User) -> bool:
    """Cancel *my* reservation. Returns False if I had none on this wish."""
    result = await session.execute(
        delete(Reservation).where(
            Reservation.wish_id == wish_id, Reservation.reserver_id == reserver.id
        )
    )
    await session.commit()
    return result.rowcount > 0


async def my_reservations(
    session: AsyncSession, settings: Settings, reserver: User
) -> list[MyReservation]:
    """Wishes I'm gifting whose owners still have access, newest reservation first."""
    rows = (
        await session.execute(
            select(WishItem, User)
            .join(Reservation, Reservation.wish_id == WishItem.id)
            .join(User, User.id == WishItem.owner_id)
            .where(Reservation.reserver_id == reserver.id, has_access_condition(settings))
            .order_by(Reservation.created_at.desc(), WishItem.id.desc())
        )
    ).all()
    owner_ids = {owner.id for _, owner in rows}
    counts = (
        dict(
            (
                await session.execute(
                    select(WishItem.owner_id, func.count())
                    .where(WishItem.owner_id.in_(owner_ids))
                    .group_by(WishItem.owner_id)
                )
            ).all()
        )
        if owner_ids
        else {}
    )
    return [MyReservation(wish, owner, counts.get(owner.id, 0)) for wish, owner in rows]


async def reserver_of(session: AsyncSession, wish_id: int) -> User | None:
    return await session.scalar(
        select(User)
        .join(Reservation, Reservation.reserver_id == User.id)
        .where(Reservation.wish_id == wish_id)
    )
