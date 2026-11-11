"""W-1: the user profile is created automatically on first login (issue #2)."""

from sqlalchemy import func, select

from app.models import User
from tests.helpers import auth, make_init_data

TG_USER = {
    "id": 42,
    "first_name": "Єгор",
    "last_name": "Шахматенко",
    "username": "jegor",
    "language_code": "uk",
    "photo_url": "https://t.me/i/userpic/320/jegor.jpg",
}


async def count_users(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(User))


async def test_first_login_creates_user(client, session_factory):
    resp = await client.get("/api/me", headers=auth(make_init_data(user=TG_USER)))

    assert resp.status_code == 200
    async with session_factory() as session:
        user = await session.scalar(select(User))
    assert user is not None
    assert user.telegram_id == 42
    assert user.first_name == "Єгор"
    assert user.last_name == "Шахматенко"
    assert user.username == "jegor"
    assert user.language_code == "uk"
    assert user.photo_url == TG_USER["photo_url"]
    assert user.created_at is not None


async def test_me_returns_profile_from_db(client, session_factory):
    resp = await client.get(
        "/api/me", headers=auth(make_init_data(user=TG_USER, start_param="join_abc"))
    )

    async with session_factory() as session:
        user = await session.scalar(select(User))
    assert resp.json() == {
        "id": user.id,
        "telegram_id": 42,
        "first_name": "Єгор",
        "last_name": "Шахматенко",
        "username": "jegor",
        "language_code": "uk",
        "photo_url": TG_USER["photo_url"],
        "start_param": "join_abc",
        "has_access": True,
        "is_admin": False,
    }


async def test_optional_fields_may_be_missing(client):
    resp = await client.get(
        "/api/me", headers=auth(make_init_data(user={"id": 7, "first_name": "A"}))
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["last_name"] is None
    assert body["username"] is None
    assert body["photo_url"] is None


async def test_repeated_login_does_not_duplicate(client, session_factory):
    first = await client.get("/api/me", headers=auth(make_init_data(user=TG_USER)))
    second = await client.get("/api/me", headers=auth(make_init_data(user=TG_USER)))

    assert first.json()["id"] == second.json()["id"]
    assert await count_users(session_factory) == 1


async def test_repeated_login_keeps_stored_profile(client):
    first = await client.get("/api/me", headers=auth(make_init_data(user=TG_USER)))
    renamed = {**TG_USER, "first_name": "Нове", "username": "new_nick", "photo_url": None}
    second = await client.get("/api/me", headers=auth(make_init_data(user=renamed)))

    assert second.json() == first.json()


async def test_different_users_get_different_profiles(client, session_factory):
    a = await client.get("/api/me", headers=auth(make_init_data(user=TG_USER)))
    b = await client.get(
        "/api/me", headers=auth(make_init_data(user={"id": 43, "first_name": "Мама"}))
    )

    assert a.json()["id"] != b.json()["id"]
    assert b.json()["first_name"] == "Мама"
    assert await count_users(session_factory) == 2


async def test_missing_init_data_is_401_and_creates_nothing(client, session_factory):
    resp = await client.get("/api/me")

    assert resp.status_code == 401
    assert await count_users(session_factory) == 0


async def test_forged_init_data_is_401_and_creates_nothing(client, session_factory):
    resp = await client.get("/api/me", headers=auth(make_init_data(token="999:OTHER")))

    assert resp.status_code == 401
    assert await count_users(session_factory) == 0
