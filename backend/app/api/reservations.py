from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.schemas import OthersWishOut, PersonOut, ReservationOut
from app.api.wishes import WishOut
from app.auth.deps import MemberUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User, WishItem
from app.services.reservations import (
    AlreadyReserved,
    OwnWish,
    ReservationView,
    WishGone,
    cancel,
    my_reservations,
    reservations_for,
    reserve,
)
from app.services.wishes import get_wish_for_reader

router = APIRouter(prefix="/api", tags=["reservations"])


class MyReservationOut(BaseModel):
    wish: OthersWishOut
    owner: PersonOut


def others_wish_out(wish: WishItem, reservation: ReservationView | None) -> OthersWishOut:
    out = OthersWishOut(**WishOut.model_validate(wish).model_dump())
    if reservation:
        out.reservation = ReservationOut(mine=reservation.mine, by_name=reservation.by_name)
    return out


async def others_wishes_out(
    session: SessionDep, wishes: list[WishItem], viewer: User
) -> list[OthersWishOut]:
    views = await reservations_for(session, [w.id for w in wishes], viewer)
    return [others_wish_out(w, views.get(w.id)) for w in wishes]


@router.post("/wishes/{wish_id}/reservation", status_code=status.HTTP_201_CREATED)
async def reserve_wish(
    wish_id: int,
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OthersWishOut:
    wish = await get_wish_for_reader(session, settings, wish_id, user)
    if wish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wish not found")
    try:
        await reserve(session, wish, user)
    except OwnWish as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can't reserve your own wish") from exc
    except AlreadyReserved as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already reserved") from exc
    except WishGone as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wish not found") from exc
    [out] = await others_wishes_out(session, [wish], user)
    return out


@router.delete("/wishes/{wish_id}/reservation", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reservation(wish_id: int, user: MemberUser, session: SessionDep) -> None:
    """Only the gifter can cancel their own reservation."""
    if not await cancel(session, wish_id, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")


@router.get("/reservations")
async def list_my_reservations(
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MyReservationOut]:
    """«Я дарую»: what I've promised to gift."""
    result = []
    for r in await my_reservations(session, settings, user):
        out = others_wish_out(r.wish, ReservationView(mine=True, by_name=user.first_name))
        owner = PersonOut(
            id=r.owner.id,
            first_name=r.owner.first_name,
            last_name=r.owner.last_name,
            photo_url=r.owner.photo_url,
            wish_count=r.owner_wish_count,
        )
        result.append(MyReservationOut(wish=out, owner=owner))
    return result
