"""A-2: taking access away (issue #22)."""

from app.bot.handlers import BLOCKED, JOINED, WELCOME, StartReply, start_reply
from app.services.access import current_invite_code
from tests.conftest import ADMIN_ID
from tests.helpers import auth, make_init_data
from tests.test_wishes import image_bytes

ADMIN = {"id": ADMIN_ID, "first_name": "Єгор"}
OLENA = {"id": 43, "first_name": "Олена"}
ME = {"id": 42, "first_name": "Мама"}


def as_user(user: dict) -> dict[str, str]:
    return auth(make_init_data(user=user))


async def revoke(client, telegram_id: int, user: dict = ADMIN):
    return await client.post(f"/api/admin/members/{telegram_id}/revoke", headers=as_user(user))


async def restore(client, telegram_id: int, user: dict = ADMIN):
    return await client.post(f"/api/admin/members/{telegram_id}/restore", headers=as_user(user))


async def members(client) -> list[dict]:
    resp = await client.get("/api/admin/members", headers=as_user(ADMIN))
    assert resp.status_code == 200
    return resp.json()


# --- the members list ---------------------------------------------------------------


async def test_members_lists_everyone_who_joined(client):
    await client.get("/api/me", headers=as_user(OLENA))  # Olena opened the app

    result = {m["telegram_id"]: m for m in await members(client)}

    assert set(result) == {42, 43}  # the conftest grants
    assert result[43]["first_name"] == "Олена"
    assert result[43]["revoked"] is False
    assert result[42]["first_name"] == "Без імені"  # joined, never opened the app


async def test_name_from_bot_is_shown_before_first_open(client, session_factory, settings):
    async with session_factory() as session:
        code = await current_invite_code(session)
        assert await start_reply(session, settings, 900, code, "Бабуся") == StartReply(JOINED, True)

    [newest] = [m for m in await members(client) if m["telegram_id"] == 900]
    assert newest["first_name"] == "Бабуся"


async def test_members_is_admin_only(client):
    assert (await client.get("/api/admin/members", headers=as_user(OLENA))).status_code == 403


# --- revoking -------------------------------------------------------------------


async def test_revoked_person_loses_access(client):
    assert (await revoke(client, OLENA["id"])).status_code == 204

    me = (await client.get("/api/me", headers=as_user(OLENA))).json()
    assert me["has_access"] is False
    assert (await client.get("/api/wishes", headers=as_user(OLENA))).status_code == 403
    [olena] = [m for m in await members(client) if m["telegram_id"] == OLENA["id"]]
    assert olena["revoked"] is True


async def test_revoked_persons_wishes_disappear_for_others(client):
    await client.post("/api/wishes", data={"title": "Сукня"}, headers=as_user(OLENA))
    assert len((await client.get("/api/people", headers=as_user(ME))).json()) == 1

    await revoke(client, OLENA["id"])

    assert (await client.get("/api/people", headers=as_user(ME))).json() == []


async def test_revoking_releases_reservations(client):
    wish = (await client.post("/api/wishes", data={"title": "Книга"}, headers=as_user(ME))).json()
    await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(OLENA))

    await revoke(client, OLENA["id"])

    resp = await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(ADMIN))
    assert resp.status_code == 201  # free again


async def test_blocked_person_cannot_rejoin_with_link(session_factory, settings, client):
    await revoke(client, OLENA["id"])

    async with session_factory() as session:
        code = await current_invite_code(session)
        with_link = await start_reply(session, settings, OLENA["id"], code)
        without = await start_reply(session, settings, OLENA["id"], None)

    assert with_link == StartReply(BLOCKED, False)
    assert without == StartReply(BLOCKED, False)


async def test_admins_cannot_be_revoked(client):
    assert (await revoke(client, ADMIN_ID)).status_code == 400


async def test_unknown_member_is_404(client):
    assert (await revoke(client, 555)).status_code == 404
    assert (await restore(client, 555)).status_code == 404


async def test_only_admin_can_revoke_or_restore(client):
    assert (await revoke(client, OLENA["id"], user=ME)).status_code == 403
    assert (await restore(client, OLENA["id"], user=ME)).status_code == 403
    me = (await client.get("/api/me", headers=as_user(OLENA))).json()
    assert me["has_access"] is True


# --- restoring ------------------------------------------------------------------


async def test_restore_gives_access_back(client, session_factory, settings):
    await revoke(client, OLENA["id"])

    assert (await restore(client, OLENA["id"])).status_code == 204

    me = (await client.get("/api/me", headers=as_user(OLENA))).json()
    assert me["has_access"] is True
    async with session_factory() as session:
        assert await start_reply(session, settings, OLENA["id"], None) == StartReply(WELCOME, True)


async def test_revoke_twice_is_harmless(client):
    await revoke(client, OLENA["id"])

    assert (await revoke(client, OLENA["id"])).status_code == 204


# --- review follow-ups ----------------------------------------------------------------


async def test_admin_who_joined_by_link_is_marked(client, session_factory, settings):
    async with session_factory() as session:
        from app.models import AccessGrant

        session.add(AccessGrant(telegram_id=ADMIN_ID, first_name="Єгор"))
        await session.commit()

    flags = {m["telegram_id"]: m["is_admin"] for m in await members(client)}

    assert flags[ADMIN_ID] is True
    assert flags[OLENA["id"]] is False


async def test_revoked_owners_list_and_photos_are_gone(client):
    wish = (
        await client.post(
            "/api/wishes",
            data={"title": "Сукня"},
            files={"photo": ("p.png", image_bytes("PNG"), "image/png")},
            headers=as_user(OLENA),
        )
    ).json()
    olena_id = (await client.get("/api/me", headers=as_user(OLENA))).json()["id"]

    await revoke(client, OLENA["id"])

    photo = await client.get(f"/api/wishes/{wish['id']}/photo", headers=as_user(ME))
    wishes = await client.get(f"/api/people/{olena_id}/wishes", headers=as_user(ME))
    assert photo.status_code == 404
    assert wishes.status_code == 404


async def test_revoked_gifter_loses_reservations(client):
    wish = (await client.post("/api/wishes", data={"title": "Книга"}, headers=as_user(ME))).json()
    await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(OLENA))

    await revoke(client, OLENA["id"])
    await restore(client, OLENA["id"])

    assert (await client.get("/api/reservations", headers=as_user(OLENA))).json() == []
