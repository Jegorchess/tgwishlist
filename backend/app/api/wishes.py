from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.deps import MemberUser
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import Priority, WishItem
from app.services.photos import InvalidPhoto, PhotoTooLarge, read_limited, save_photo
from app.services.wishes import (
    create_wish,
    delete_wish,
    get_own_wish,
    get_wish_for_reader,
    list_own_wishes,
    update_wish,
)

router = APIRouter(prefix="/api/wishes", tags=["wishes"])


async def _store_upload(photo: UploadFile | None, media_dir: Path) -> str | None:
    """Validate and save an uploaded photo; ``None`` when no file was sent."""
    if photo is None or not photo.filename:
        return None
    try:
        data = await read_limited(photo)
        return await run_in_threadpool(save_photo, data, media_dir)
    except PhotoTooLarge as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
    except InvalidPhoto as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _remove_file(media_dir: Path, name: str | None) -> None:
    if name:
        (media_dir / name).unlink(missing_ok=True)


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


class WishUpdate(WishCreate):
    """All fields are replaced. ``remove_photo`` drops the photo unless a new one is uploaded."""

    remove_photo: bool = False


class WishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: Decimal | None
    priority: Priority
    url: str | None
    description: str | None
    has_photo: bool
    photo_version: str | None
    created_at: datetime


@router.get("")
async def my_wishes(user: MemberUser, session: SessionDep) -> list[WishOut]:
    return [WishOut.model_validate(w) for w in await list_own_wishes(session, user)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_wish(
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    form: Annotated[WishCreate, Form()],
    photo: Annotated[UploadFile | None, File()] = None,
) -> WishOut:
    media_dir = Path(settings.media_dir)
    photo_name = await _store_upload(photo, media_dir)
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
        _remove_file(media_dir, photo_name)
        raise
    # Outside the guard: after a successful commit the row references the file.
    await session.refresh(wish)
    return WishOut.model_validate(wish)


async def _own_wish_or_404(session: SessionDep, wish_id: int, user: MemberUser) -> WishItem:
    wish = await get_own_wish(session, wish_id, user)
    if wish is None:
        # Same answer for "someone else's" and "does not exist": don't reveal other wishes.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wish not found")
    return wish


@router.patch("/{wish_id}")
async def edit_wish(
    wish_id: int,
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    form: Annotated[WishUpdate, Form()],
    photo: Annotated[UploadFile | None, File()] = None,
) -> WishOut:
    wish = await _own_wish_or_404(session, wish_id, user)
    media_dir = Path(settings.media_dir)
    new_photo = await _store_upload(photo, media_dir)
    try:
        unused_photo = await update_wish(
            session,
            wish,
            title=form.title,
            price=form.price,
            priority=form.priority,
            url=form.url,
            description=form.description,
            new_photo_name=new_photo,
            remove_photo=form.remove_photo,
        )
    except BaseException:  # commit failed: the new file is not referenced
        _remove_file(media_dir, new_photo)
        raise
    _remove_file(media_dir, unused_photo)
    await session.refresh(wish)
    return WishOut.model_validate(wish)


@router.delete("/{wish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wish(
    wish_id: int,
    user: MemberUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    wish = await _own_wish_or_404(session, wish_id, user)
    _remove_file(Path(settings.media_dir), await delete_wish(session, wish))


@router.get("/{wish_id}/photo", response_class=FileResponse)
async def wish_photo(
    wish_id: int,
    _: MemberUser,  # any user with access may see any photo
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    wish = await get_wish_for_reader(session, settings, wish_id)
    path = Path(settings.media_dir) / wish.photo_name if wish and wish.photo_name else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        # Each photo file is never modified (a replacement gets a new name and version),
        # and clients request it as ?v=<photo_version>, so it can be cached forever.
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
