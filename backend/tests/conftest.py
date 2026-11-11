import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import Settings, get_settings
from app.db import Base, get_session
from app.main import app
from app.models import AccessGrant
from app.services.notify import get_notifier
from tests.helpers import MAX_AGE, TOKEN

# In-memory SQLite by default; CI also runs the suite against PostgreSQL.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

if not TEST_DATABASE_URL.startswith("sqlite"):
    # The fixtures drop all tables: never point them at a real database.
    assert make_url(TEST_DATABASE_URL).database.endswith("_test"), (
        "TEST_DATABASE_URL must point at a database whose name ends with _test"
    )


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    kwargs = {"poolclass": StaticPool} if TEST_DATABASE_URL.startswith("sqlite") else {}
    engine = create_async_engine(TEST_DATABASE_URL, **kwargs)
    if TEST_DATABASE_URL.startswith("sqlite"):
        # Enforce foreign keys like PostgreSQL does.
        event.listen(
            engine.sync_engine,
            "connect",
            lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"),
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def media_dir(tmp_path):
    return tmp_path / "media"


ADMIN_ID = 1000
MEMBER_IDS = (42, 43)  # users of the existing tests have joined via the invite link


@pytest.fixture
def settings(media_dir) -> Settings:
    return Settings(
        bot_token=TOKEN,
        init_data_max_age=MAX_AGE,
        dev_auth=False,
        media_dir=str(media_dir),
        admin_telegram_ids=str(ADMIN_ID),
        bot_username="test_bot",
    )


class FakeNotifier:
    """Collects bot messages instead of sending them to Telegram."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
async def client(session_factory, settings, notifier) -> AsyncIterator[AsyncClient]:
    async with session_factory() as session:
        session.add_all(AccessGrant(telegram_id=tid) for tid in MEMBER_IDS)
        await session.commit()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_notifier] = lambda: notifier
    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
