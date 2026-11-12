"""A-1: invite-only access (issue #10)."""

import re

import pytest
from sqlalchemy import func, select

from app.bot.handlers import INVALID_INVITE, JOINED, PRIVATE, WELCOME, StartReply, start_reply
from app.main import app
from app.models import AccessGrant, WishItem
from app.services.access import current_invite_code, regenerate_invite_code
from tests.conftest import ADMIN_ID
from tests.helpers import auth, make_init_data

STRANGER = {"id": 777, "first_name": "Незнайомець"}
ADMIN = {"id": ADMIN_ID, "first_name": "Єгор"}

# Every /api route except /api/me must refuse users without access.
PROTECTED = [
    ("GET", "/api/wishes"),
    ("POST", "/api/wishes"),
    ("PATCH", "/api/wishes/{wish_id}"),
    ("DELETE", "/api/wishes/{wish_id}"),
    ("GET", "/api/wishes/{wish_id}/photo"),
    ("GET", "/api/invite"),
    ("POST", "/api/invite/regenerate"),
    ("GET", "/api/people"),
    ("GET", "/api/people/{user_id}/wishes"),
    ("POST", "/api/wishes/{wish_id}/reservation"),
    ("DELETE", "/api/wishes/{wish_id}/reservation"),
    ("GET", "/api/reservations"),
    ("GET", "/api/wishes/archive"),
    ("POST", "/api/wishes/{wish_id}/received"),
    ("POST", "/api/wishes/{wish_id}/restore"),
    ("POST", "/api/link-preview"),
    ("GET", "/api/link-preview/image"),
]


def as_user(user: dict) -> dict[str, str]:
    return auth(make_init_data(user=user))


# --- /api/me --------------------------------------------------------------------


async def test_me_reports_no_access_for_stranger(client):
    resp = await client.get("/api/me", headers=as_user(STRANGER))

    assert resp.status_code == 200
    assert resp.json()["has_access"] is False
    assert resp.json()["is_admin"] is False


async def test_me_reports_access_for_member(client):
    body = (await client.get("/api/me", headers=auth())).json()

    assert body["has_access"] is True
    assert body["is_admin"] is False


async def test_admin_always_has_access(client):
    body = (await client.get("/api/me", headers=as_user(ADMIN))).json()

    assert body["has_access"] is True
    assert body["is_admin"] is True


# --- every other endpoint is closed to strangers ------------------------------------


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_stranger_gets_403(client, method, path):
    data = {"title": "x"} if method in ("POST", "PATCH") else None
    url = re.sub(r"\{\w+\}", "1", path)

    resp = await client.request(method, url, data=data, headers=as_user(STRANGER))

    assert resp.status_code == 403


def test_all_api_routes_are_protected():
    """A new endpoint must be added to PROTECTED (and use MemberUser/AdminUser)."""
    routes = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/")
        for method in operations
    }
    assert routes == set(PROTECTED) | {("GET", "/api/me")}


async def test_stranger_cannot_create_wish(client, session_factory):
    await client.post("/api/wishes", data={"title": "x"}, headers=as_user(STRANGER))

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WishItem)) == 0


# --- invite link (admin only) ----------------------------------------------------


async def test_admin_gets_stable_invite_link(client):
    first = (await client.get("/api/invite", headers=as_user(ADMIN))).json()["link"]
    second = (await client.get("/api/invite", headers=as_user(ADMIN))).json()["link"]

    assert first == second
    assert first.startswith("https://t.me/test_bot?start=")
    assert len(first.split("start=")[1]) >= 12


async def test_member_cannot_manage_invite(client):
    assert (await client.get("/api/invite", headers=auth())).status_code == 403
    assert (await client.post("/api/invite/regenerate", headers=auth())).status_code == 403


async def test_regenerate_changes_link(client):
    old = (await client.get("/api/invite", headers=as_user(ADMIN))).json()["link"]
    new = (await client.post("/api/invite/regenerate", headers=as_user(ADMIN))).json()["link"]

    assert new != old
    assert (await client.get("/api/invite", headers=as_user(ADMIN))).json()["link"] == new


# --- bot /start ------------------------------------------------------------------


async def test_start_with_valid_code_grants_access(client, session_factory, settings):
    async with session_factory() as session:
        code = await current_invite_code(session)
        reply = await start_reply(session, settings, STRANGER["id"], code)

    assert reply == StartReply(JOINED, True)
    body = (await client.get("/api/me", headers=as_user(STRANGER))).json()
    assert body["has_access"] is True
    assert (await client.get("/api/wishes", headers=as_user(STRANGER))).status_code == 200


async def test_start_with_invalid_code_is_refused(session_factory, settings):
    async with session_factory() as session:
        await current_invite_code(session)
        reply = await start_reply(session, settings, STRANGER["id"], "wrong-code-123")
        granted = await session.get(AccessGrant, STRANGER["id"])

    assert reply == StartReply(INVALID_INVITE, False)
    assert granted is None


async def test_old_code_stops_working_but_access_is_kept(session_factory, settings):
    async with session_factory() as session:
        old = await current_invite_code(session)
        await start_reply(session, settings, 501, old)  # joined with the old link
        await regenerate_invite_code(session)

        late = await start_reply(session, settings, 502, old)
        early = await start_reply(session, settings, 501, None)

    assert late == StartReply(INVALID_INVITE, False)
    assert early == StartReply(WELCOME, True)


async def test_start_without_code(session_factory, settings):
    async with session_factory() as session:
        stranger = await start_reply(session, settings, STRANGER["id"], None)
        admin = await start_reply(session, settings, ADMIN_ID, None)

    assert stranger == StartReply(PRIVATE, False)
    assert admin == StartReply(WELCOME, True)


async def test_member_reusing_link_gets_welcome_once(session_factory, settings):
    async with session_factory() as session:
        code = await current_invite_code(session)
        await start_reply(session, settings, 600, code)
        again = await start_reply(session, settings, 600, code)
        grants = await session.scalar(
            select(func.count()).select_from(AccessGrant).where(AccessGrant.telegram_id == 600)
        )

    assert again == StartReply(WELCOME, True)
    assert grants == 1


# --- settings & edge cases -------------------------------------------------------


def test_admin_ids_parsing():
    from app.config import Settings

    assert Settings(admin_telegram_ids=" 12, 34 ,").admin_ids == {12, 34}
    assert Settings(admin_telegram_ids="").admin_ids == frozenset()


def test_malformed_admin_ids_fail_at_startup():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(admin_telegram_ids="123;456")


async def test_only_newest_active_code_works(session_factory, settings):
    from app.models import Invite

    async with session_factory() as session:
        # Two active codes can appear after concurrent first requests.
        session.add_all([Invite(code="older-code-aaaa"), Invite(code="newer-code-bbbb")])
        await session.commit()

        older = await start_reply(session, settings, 801, "older-code-aaaa")
        newer = await start_reply(session, settings, 802, "newer-code-bbbb")

    assert older == StartReply(INVALID_INVITE, False)
    assert newer == StartReply(JOINED, True)
