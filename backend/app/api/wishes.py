from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.deps import CurrentUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import Priority
from app.services.photos import InvalidPhoto, PhotoTooLarge, read_limited, save_photo
from app.services.wishes import create_wish, get_wish_for_reader, list_own_wishes

router = APIRouter(prefix="/api/wishes", tags=["wishes"])


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class WishCreate(BaseModel):
    """Fields of the "add wish" form. The owner always comes from initData, never from here."""

    title: str = Field(min_length=1, max_length=200)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    priority: Priority = Priority.MEDIUM
    url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("url", "description", mode="before")
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("price", mode="before")
    @classmethod
    def decimal_comma(cls, value: object) -> object:
        value = _blank_to_none(value)
        # Accept the Polish/Ukrainian decimal comma: "12,50".
        if isinstance(value, str) and "," in value and "." not in value:
            value = value.replace(",", ".")
        return value

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in value:
            raise ValueError("must be an http:// or https:// link")
        return value


class WishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: Decimal | None
    priority: Priority
    url: str | None
    description: str | None
    has_photo: bool
    created_at: datetime


@router.get("")
async def my_wishes(user: CurrentUser, session: SessionDep) -> list[WishOut]:
    return [WishOut.model_validate(w) for w in await list_own_wishes(session, user)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_wish(
    user: CurrentUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    form: Annotated[WishCreate, Form()],
    photo: Annotated[UploadFile | None, File()] = None,
) -> WishOut:
    photo_name = None
    media_dir = Path(settings.media_dir)
    if photo is not None and photo.filename:
        try:
            data = await read_limited(photo)
            photo_name = await run_in_threadpool(save_photo, data, media_dir)
        except PhotoTooLarge as exc:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
        except InvalidPhoto as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    try:
        wish = await create_wish(
            session,
            user,
            title=form.title,
            price=form.price,
            priority=form.priority,
            url=form.url,
            description=form.description,
            photo_name=photo_name,
        )
    except BaseException:  # incl. cancellation: don't leave an orphan file
        if photo_name:
            (media_dir / photo_name).unlink(missing_ok=True)
        raise
    return WishOut.model_validate(wish)


@router.get("/{wish_id}/photo", response_class=FileResponse)
async def wish_photo(
    wish_id: int,
    user: CurrentUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    wish = await get_wish_for_reader(session, wish_id, user)
    path = Path(settings.media_dir) / wish.photo_name if wish and wish.photo_name else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )
