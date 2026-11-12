"""ARC-1: «Отримано» and the archive (issue #21)."""

from tests.helpers import auth, make_init_data
from tests.test_wishes import image_bytes

OLENA = {"id": 43, "first_name": "Олена"}  # owner
ME = {"id": 42, "first_name": "Єгор"}  # gifter
STRANGER = {"id": 777, "first_name": "Незнайомець"}


def as_user(user: dict) -> dict[str, str]:
    return auth(make_init_data(user=user))


async def wish_of(client, user: dict, title: str = "Сукня", **extra) -> dict:
    resp = await client.post("/api/wishes", data={"title": title}, headers=as_user(user), **extra)
    assert resp.status_code == 201
    return resp.json()


async def received(client, user: dict, wish_id: int):
    return await client.post(f"/api/wishes/{wish_id}/received", headers=as_user(user))


async def titles(client, user: dict, path: str) -> list[str]:
    return [w["title"] for w in (await client.get(path, headers=as_user(user))).json()]


async def olena_id(client) -> int:
    return (await client.get("/api/me", headers=as_user(OLENA))).json()["id"]


# --- marking as received ----------------------------------------------------------


async def test_received_wish_moves_to_archive(client):
    keep = await wish_of(client, OLENA, "Книга")
    done = await wish_of(client, OLENA, "Сукня")

    resp = await received(client, OLENA, done["id"])

    assert resp.status_code == 200
    assert resp.json()["received_at"] is not None
    assert await titles(client, OLENA, "/api/wishes") == [keep["title"]]
    assert await titles(client, OLENA, "/api/wishes/archive") == ["Сукня"]


async def test_archive_is_newest_first(client):
    for title in ("Перше", "Друге"):
        wish = await wish_of(client, OLENA, title)
        await received(client, OLENA, wish["id"])

    assert await titles(client, OLENA, "/api/wishes/archive") == ["Друге", "Перше"]


async def test_restore_brings_wish_back(client):
    wish = await wish_of(client, OLENA)
    await received(client, OLENA, wish["id"])

    resp = await client.post(f"/api/wishes/{wish['id']}/restore", headers=as_user(OLENA))

    assert resp.status_code == 200
    assert resp.json()["received_at"] is None
    assert await titles(client, OLENA, "/api/wishes") == ["Сукня"]
    assert await titles(client, OLENA, "/api/wishes/archive") == []


async def test_archived_wish_can_be_deleted(client):
    wish = await wish_of(client, OLENA)
    await received(client, OLENA, wish["id"])

    resp = await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(OLENA))

    assert resp.status_code == 204
    assert await titles(client, OLENA, "/api/wishes/archive") == []


# --- hidden from everyone else ------------------------------------------------------


async def test_others_dont_see_received_wishes(client):
    await wish_of(client, OLENA, "Книга")
    done = await wish_of(client, OLENA, "Сукня")
    await received(client, OLENA, done["id"])

    [person] = (await client.get("/api/people", headers=as_user(ME))).json()
    their_list = await titles(client, ME, f"/api/people/{person['id']}/wishes")

    assert person["wish_count"] == 1
    assert their_list == ["Книга"]


async def test_person_with_only_received_wishes_is_hidden(client):
    wish = await wish_of(client, OLENA)
    await received(client, OLENA, wish["id"])

    assert (await client.get("/api/people", headers=as_user(ME))).json() == []


async def test_received_photo_visible_to_owner_only(client):
    wish = await wish_of(client, OLENA, files={"photo": ("p.png", image_bytes("PNG"), "image/png")})
    await received(client, OLENA, wish["id"])

    own = await client.get(f"/api/wishes/{wish['id']}/photo", headers=as_user(OLENA))
    other = await client.get(f"/api/wishes/{wish['id']}/photo", headers=as_user(ME))

    assert own.status_code == 200
    assert other.status_code == 404


async def test_cannot_reserve_received_wish(client):
    wish = await wish_of(client, OLENA)
    await received(client, OLENA, wish["id"])

    resp = await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(ME))

    assert resp.status_code == 404


# --- the reservation and the gifter ---------------------------------------------------


async def test_receiving_closes_reservation_and_thanks_gifter(client, notifier):
    wish = await wish_of(client, OLENA)
    await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(ME))

    resp = await received(client, OLENA, wish["id"])

    assert "reservation" not in resp.json()  # the owner still learns nothing
    assert notifier.sent == [(ME["id"], "🎉 Олена отримав(ла) «Сукня»")]
    assert (await client.get("/api/reservations", headers=as_user(ME))).json() == []


async def test_receiving_free_wish_notifies_nobody(client, notifier):
    wish = await wish_of(client, OLENA)

    await received(client, OLENA, wish["id"])

    assert notifier.sent == []


async def test_receiving_twice_is_harmless(client, notifier):
    wish = await wish_of(client, OLENA)
    await client.post(f"/api/wishes/{wish['id']}/reservation", headers=as_user(ME))
    await received(client, OLENA, wish["id"])

    resp = await received(client, OLENA, wish["id"])

    assert resp.status_code == 200
    assert len(notifier.sent) == 1


# --- access -----------------------------------------------------------------------


async def test_only_owner_can_receive_or_restore(client):
    wish = await wish_of(client, OLENA)

    assert (await received(client, ME, wish["id"])).status_code == 404
    await received(client, OLENA, wish["id"])
    restore = await client.post(f"/api/wishes/{wish['id']}/restore", headers=as_user(ME))
    assert restore.status_code == 404
    assert await titles(client, OLENA, "/api/wishes/archive") == ["Сукня"]


async def test_archive_is_private(client):
    wish = await wish_of(client, OLENA)
    await received(client, OLENA, wish["id"])

    assert await titles(client, ME, "/api/wishes/archive") == []
    stranger = await client.get("/api/wishes/archive", headers=as_user(STRANGER))
    assert stranger.status_code == 403


async def test_my_reservations_count_ignores_archive(client):
    reserved = await wish_of(client, OLENA, "Сукня")
    await wish_of(client, OLENA, "Книга")
    archived = await wish_of(client, OLENA, "Шарф")
    await client.post(f"/api/wishes/{reserved['id']}/reservation", headers=as_user(ME))
    await received(client, OLENA, archived["id"])

    [item] = (await client.get("/api/reservations", headers=as_user(ME))).json()

    assert item["owner"]["wish_count"] == 2


async def test_reservation_on_received_wish_is_hidden(client, session_factory):
    """Race guard: a reservation that slipped onto a received wish isn't listed."""
    from app.models import Reservation, WishItem

    wish = await wish_of(client, OLENA)
    me_id = (await client.get("/api/me", headers=as_user(ME))).json()["id"]
    await received(client, OLENA, wish["id"])
    async with session_factory() as session:
        assert (await session.get(WishItem, wish["id"])).received_at is not None
        session.add(Reservation(wish_id=wish["id"], reserver_id=me_id))
        await session.commit()

    assert (await client.get("/api/reservations", headers=as_user(ME))).json() == []
