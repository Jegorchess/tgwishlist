"""R-1: reserving a gift — «Я дарую» (issue #14)."""

import pytest

from app.models import User, WishItem
from app.services.reservations import AlreadyReserved, reserve
from tests.conftest import ADMIN_ID
from tests.helpers import auth, make_init_data
from tests.test_wishes import image_bytes

OLENA = {"id": 43, "first_name": "Олена"}  # the wish owner
ME = {"id": 42, "first_name": "Єгор"}  # a gifter
MAMA = {"id": ADMIN_ID, "first_name": "Мама"}  # another gifter (admin => has access)
STRANGER = {"id": 777, "first_name": "Незнайомець"}


def as_user(user: dict) -> dict[str, str]:
    return auth(make_init_data(user=user))


async def olenas_wish(client, title: str = "Сукня", **extra) -> dict:
    resp = await client.post("/api/wishes", data={"title": title}, headers=as_user(OLENA), **extra)
    assert resp.status_code == 201
    return resp.json()


async def olenas_list(client, viewer: dict) -> list[dict]:
    people = (await client.get("/api/people", headers=as_user(viewer))).json()
    [olena] = [p for p in people if p["first_name"] == "Олена"]
    return (await client.get(f"/api/people/{olena['id']}/wishes", headers=as_user(viewer))).json()


async def reserve_as(client, user: dict, wish_id: int):
    return await client.post(f"/api/wishes/{wish_id}/reservation", headers=as_user(user))


async def cancel_as(client, user: dict, wish_id: int):
    return await client.delete(f"/api/wishes/{wish_id}/reservation", headers=as_user(user))


# --- reserving ----------------------------------------------------------------------


async def test_reserve_marks_wish_as_mine(client):
    wish = await olenas_wish(client)

    resp = await reserve_as(client, ME, wish["id"])

    assert resp.status_code == 201
    assert resp.json()["reservation"] == {"mine": True, "by_name": "Єгор"}
    [seen] = await olenas_list(client, ME)
    assert seen["reservation"] == {"mine": True, "by_name": "Єгор"}


async def test_others_see_who_is_gifting(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    [seen] = await olenas_list(client, MAMA)

    assert seen["reservation"] == {"mine": False, "by_name": "Єгор"}


async def test_free_wish_has_no_reservation(client):
    await olenas_wish(client)

    [seen] = await olenas_list(client, ME)

    assert seen["reservation"] is None


async def test_only_one_gifter_per_wish(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    resp = await reserve_as(client, MAMA, wish["id"])

    assert resp.status_code == 409
    [seen] = await olenas_list(client, MAMA)
    assert seen["reservation"]["by_name"] == "Єгор"


async def test_concurrent_reservation_loses_cleanly(client, session_factory):
    """Both passed the checks; the database primary key decides."""
    wish = await olenas_wish(client)
    mama_id = (await client.get("/api/me", headers=as_user(MAMA))).json()["id"]
    await reserve_as(client, ME, wish["id"])

    async with session_factory() as session:
        item = await session.get(WishItem, wish["id"])
        mama = await session.get(User, mama_id)
        with pytest.raises(AlreadyReserved):
            await reserve(session, item, mama)


async def test_cannot_reserve_own_wish(client):
    wish = await olenas_wish(client)

    assert (await reserve_as(client, OLENA, wish["id"])).status_code == 400


async def test_reserve_missing_wish_is_404(client):
    assert (await reserve_as(client, ME, 9999)).status_code == 404


async def test_stranger_cannot_reserve(client):
    wish = await olenas_wish(client)

    assert (await reserve_as(client, STRANGER, wish["id"])).status_code == 403


# --- the surprise -----------------------------------------------------------------


async def test_owner_never_sees_reservation(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    own = (await client.get("/api/wishes", headers=as_user(OLENA))).json()
    me_id = (await client.get("/api/me", headers=as_user(OLENA))).json()["id"]
    via_people = (await client.get(f"/api/people/{me_id}/wishes", headers=as_user(OLENA))).json()

    assert "reservation" not in own[0]
    assert via_people[0]["reservation"] is None
    assert "Єгор" not in str(own) + str(via_people)


async def test_editing_keeps_reservation(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    await client.patch(
        f"/api/wishes/{wish['id']}", data={"title": "Сукня синя"}, headers=as_user(OLENA)
    )

    [seen] = await olenas_list(client, ME)
    assert seen["title"] == "Сукня синя"
    assert seen["reservation"]["mine"] is True


# --- cancelling -------------------------------------------------------------------


async def test_cancel_frees_wish(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    assert (await cancel_as(client, ME, wish["id"])).status_code == 204

    [seen] = await olenas_list(client, MAMA)
    assert seen["reservation"] is None
    assert (await reserve_as(client, MAMA, wish["id"])).status_code == 201


async def test_only_gifter_can_cancel(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    for other in (MAMA, OLENA):
        assert (await cancel_as(client, other, wish["id"])).status_code == 404

    [seen] = await olenas_list(client, ME)
    assert seen["reservation"]["mine"] is True


# --- «Я дарую» ----------------------------------------------------------------------


async def test_my_reservations_list(client):
    first = await olenas_wish(
        client, "Сукня", files={"photo": ("p.png", image_bytes("PNG"), "image/png")}
    )
    second = await olenas_wish(client, "Книга")
    await olenas_wish(client, "Чужа бронь")
    await reserve_as(client, ME, first["id"])
    await reserve_as(client, ME, second["id"])

    resp = await client.get("/api/reservations", headers=as_user(ME))

    assert resp.status_code == 200
    items = resp.json()
    assert {i["wish"]["title"] for i in items} == {"Сукня", "Книга"}
    for item in items:
        assert item["owner"]["first_name"] == "Олена"
        assert item["owner"]["wish_count"] == 3
        assert item["wish"]["reservation"]["mine"] is True
        assert set(item["owner"]) == {"id", "first_name", "last_name", "photo_url", "wish_count"}


async def test_no_reservations_is_empty_list(client):
    assert (await client.get("/api/reservations", headers=as_user(ME))).json() == []


# --- deleting a reserved wish ---------------------------------------------------------


async def test_deleting_reserved_wish_notifies_gifter(client, notifier):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    resp = await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

    assert resp.status_code == 204
    assert notifier.sent == [(ME["id"], "Олена видалив(ла) хотєлку «Сукня», яку ти бронював(ла).")]
    assert (await client.get("/api/reservations", headers=as_user(ME))).json() == []


async def test_deleting_free_wish_notifies_nobody(client, notifier):
    wish = await olenas_wish(client)

    await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

    assert notifier.sent == []


# --- edge cases from review ---------------------------------------------------------


async def revoke(session_factory, telegram_id: int) -> None:
    from app.models import AccessGrant

    async with session_factory() as session:
        await session.delete(await session.get(AccessGrant, telegram_id))
        await session.commit()


async def test_owner_gets_400_even_when_reserved(client):
    """The status code must not reveal that someone reserved the owner's wish."""
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    assert (await reserve_as(client, OLENA, wish["id"])).status_code == 400


async def test_owner_delete_response_reveals_nothing(client):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])

    resp = await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

    assert resp.status_code == 204
    assert resp.content == b""


async def test_cannot_reserve_when_owner_lost_access(client, session_factory):
    wish = await olenas_wish(client)
    await revoke(session_factory, OLENA["id"])

    assert (await reserve_as(client, ME, wish["id"])).status_code == 404


async def test_my_reservations_hide_owner_without_access(client, session_factory):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])
    await revoke(session_factory, OLENA["id"])

    assert (await client.get("/api/reservations", headers=as_user(ME))).json() == []


async def test_gifter_without_access_is_not_notified(client, session_factory, notifier):
    wish = await olenas_wish(client)
    await reserve_as(client, ME, wish["id"])
    await revoke(session_factory, ME["id"])

    await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

    assert notifier.sent == []


async def test_reserving_a_just_deleted_wish_is_not_a_conflict(client, session_factory):
    from app.services.reservations import WishGone

    wish = await olenas_wish(client)
    me_id = (await client.get("/api/me", headers=as_user(ME))).json()["id"]
    async with session_factory() as session:
        stale = await session.get(WishItem, wish["id"])  # loaded before the deletion
        me = await session.get(User, me_id)
        await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

        with pytest.raises(WishGone):
            await reserve(session, stale, me)
