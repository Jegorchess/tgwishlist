from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.reservations import others_wishes_out
from app.api.schemas import OthersWishOut, PersonOut
from app.auth.deps import MemberUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.services.people import get_person, list_people
from app.services.wishes import list_own_wishes

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
async def people(
    user: MemberUser, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> list[PersonOut]:
    return [
        PersonOut(
            id=p.user.id,
            first_name=p.user.first_name,
            last_name=p.user.last_name,
            photo_url=p.user.photo_url,
            wish_count=p.wish_count,
        )
        for p in await list_people(session, settings, user)
    ]


@router.get("/{user_id}/wishes")
async def person_wishes(
    user_id: int,
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[OthersWishOut]:
    """Read-only list of another person's wishes, sorted like "my wishes".

    Includes reservations, except when I'm looking at my own list (surprise!).
    """
    person = await get_person(session, settings, user_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    wishes = await list_own_wishes(session, person)
    if person.id == user.id:  # my own list via /people: never reveal reservations
        return [OthersWishOut.model_validate(w, from_attributes=True) for w in wishes]
    return await others_wishes_out(session, wishes, user)
