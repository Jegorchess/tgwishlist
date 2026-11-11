from sqlalchemy import func, select

from app.auth.telegram import TelegramUser
from app.models import User
from app.services.users import get_or_create_user

TG_USER = TelegramUser(id=42, first_name="Єгор")


async def test_concurrent_first_login_returns_existing_user(session_factory):
    """Another request created the user between our SELECT and INSERT."""
    async with session_factory() as other:
        winner = await get_or_create_user(other, TG_USER)

    async with session_factory() as session:
        real_scalar = session.scalar
        calls = 0

        async def scalar_missing_first(*args, **kwargs):
            # Simulate the race: the first lookup does not see the other request's row yet.
            nonlocal calls
            calls += 1
            return None if calls == 1 else await real_scalar(*args, **kwargs)

        session.scalar = scalar_missing_first
        user = await get_or_create_user(session, TG_USER)

    assert user.id == winner.id
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1
