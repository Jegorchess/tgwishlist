from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.wishes import WishOut
from app.auth.deps import MemberUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.services.people import get_person, list_people
from app.services.wishes import list_own_wishes

router = APIRouter(prefix="/api/people", tags=["people"])


class PersonOut(BaseModel):
    """Only what the list needs: no Telegram ID, username or language of other people."""

    id: int
    first_name: str
    last_name: str | None
    photo_url: str | None
    wish_count: int


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
    _: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[WishOut]:
    """Read-only list of another person's wishes, sorted like "my wishes"."""
    person = await get_person(session, settings, user_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    return [WishOut.model_validate(w) for w in await list_own_wishes(session, person)]
