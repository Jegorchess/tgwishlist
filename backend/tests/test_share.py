"""SH-1: sharing my list (issue #24)."""

from app.bot.handlers import (
    BLOCKED,
    JOINED,
    PRIVATE,
    SHARED_LIST,
    WELCOME,
    StartReply,
    start_reply,
)
from app.services.access import current_invite_code, revoke_access
from app.services.share import app_url_for_person, share_code
from tests.helpers import auth, make_init_data

STRANGER_ID = 777


async def test_share_link_points_to_my_list(client):
    me = (await client.get("/api/me", headers=auth())).json()

    resp = await client.get("/api/share-link", headers=auth())

    assert resp.status_code == 200
    assert resp.json() == {"link": f"https://t.me/test_bot?startapp=list_{me['id']}"}
    assert str(me["telegram_id"]) not in resp.json()["link"]


async def test_member_opening_shared_link_gets_that_list(client, session_factory, settings):
    async with session_factory() as session:
        reply = await start_reply(session, settings, 42, share_code(5))

    assert reply == StartReply(SHARED_LIST, True, 5)


async def test_shared_link_grants_no_access(session_factory, settings):
    async with session_factory() as session:
        reply = await start_reply(session, settings, STRANGER_ID, share_code(5))

    assert reply == StartReply(PRIVATE, False)


async def test_blocked_person_gets_blocked_message(client, session_factory, settings):
    async with session_factory() as session:
        await revoke_access(session, 43)
        reply = await start_reply(session, settings, 43, share_code(5))

    assert reply == StartReply(BLOCKED, False)


async def test_invite_codes_still_work(session_factory, settings):
    async with session_factory() as session:
        code = await current_invite_code(session)
        joined = await start_reply(session, settings, STRANGER_ID, code)
        plain = await start_reply(session, settings, STRANGER_ID, None)

    assert joined == StartReply(JOINED, True)
    assert plain == StartReply(WELCOME, True)


def test_share_code_can_never_look_like_an_invite_code():
    """Invite codes are 16 characters; share codes are at most 15."""
    assert len(share_code(9_999_999_999)) < 16


async def test_odd_list_codes_are_not_treated_as_shares(client, session_factory, settings):
    async with session_factory() as session:
        for code in ("list_", "list_abc", "list_12345678901", "xlist_5"):
            reply = await start_reply(session, settings, 42, code)
            assert reply == StartReply(WELCOME, True)  # a member: just the normal greeting


async def test_stranger_cannot_get_share_link(client):
    stranger = auth(make_init_data(user={"id": STRANGER_ID, "first_name": "X"}))

    assert (await client.get("/api/share-link", headers=stranger)).status_code == 403


async def test_my_own_link_gives_the_normal_greeting(client, session_factory, settings):
    me = (await client.get("/api/me", headers=auth())).json()

    async with session_factory() as session:
        reply = await start_reply(session, settings, me["telegram_id"], share_code(me["id"]))

    assert reply == StartReply(WELCOME, True)


def test_app_url_for_person():
    assert app_url_for_person("https://x.example", None) == "https://x.example"
    assert app_url_for_person("https://x.example/", 5) == "https://x.example/?person=5"
    assert (
        app_url_for_person("https://x.example/app?v=2", 5) == "https://x.example/app?v=2&person=5"
    )
    assert app_url_for_person("https://x.example/?person=1", 5) == "https://x.example/?person=5"
