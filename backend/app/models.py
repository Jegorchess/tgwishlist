from datetime import datetime
from decimal import Decimal
from enum import IntEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    photo_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Priority(IntEnum):
    """Lower value = more wanted (used for sorting)."""

    HIGH = 1  # «Дуже хочу»
    MEDIUM = 2  # «Хочу»
    LOW = 3  # «Було б непогано»


class WishItem(Base):
    __tablename__ = "wish_items"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 3", name="ck_wish_items_priority"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_wish_items_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    priority: Mapped[int] = mapped_column(SmallInteger, default=Priority.MEDIUM)
    url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    # File name inside settings.media_dir; never exposed directly.
    photo_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_photo(self) -> bool:
        return self.photo_name is not None

    @property
    def photo_version(self) -> str | None:
        """Changes whenever the photo is replaced, so clients know to refetch it."""
        return self.photo_name[:12] if self.photo_name else None


class AccessGrant(Base):
    """A Telegram account that joined via an invite link and may use the app."""

    __tablename__ = "access_grants"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invite(Base):
    """Invite codes; only the newest active one works."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reservation(Base):
    """«Я дарую»: one gifter per wish. Never shown to the wish's owner."""

    __tablename__ = "reservations"

    # The primary key on wish_id guarantees a single reservation per wish.
    wish_id: Mapped[int] = mapped_column(
        ForeignKey("wish_items.id", ondelete="CASCADE"), primary_key=True
    )
    reserver_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
