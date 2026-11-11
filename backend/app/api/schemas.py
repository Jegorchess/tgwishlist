"""Response models shared by several routers."""

from pydantic import BaseModel

from app.api.wishes import WishOut


class PersonOut(BaseModel):
    """Only what lists need: no Telegram ID, username or language of other people."""

    id: int
    first_name: str
    last_name: str | None
    photo_url: str | None
    wish_count: int


class ReservationOut(BaseModel):
    mine: bool
    by_name: str


class OthersWishOut(WishOut):
    """A wish in someone else's list. ``reservation`` is never sent to the owner."""

    reservation: ReservationOut | None = None
