"""P-1: people and their wish lists (issue #11)."""

from app.models import AccessGrant
from tests.conftest import ADMIN_ID
from tests.helpers import auth, make_init_data
from tests.test_wishes import image_bytes

ME = {"id": 42, "first_name": "Єгор", "username": "jegor", "language_code": "uk"}
OLENA = {"id": 43, "first_name": "Олена", "last_name": "Коваль", "username": "olena"}
ADMIN = {"id": ADMIN_ID, "first_name": "Адмін"}
STRANGER = {"id": 777, "first_name": "Незнайомець"}


def as_user(user: dict) -> dict[str, str]:
    return auth(make_init_data(user=user))


async def add_as(client, user: dict, title: str, priority: str = "2", **extra):
    resp = await client.post(
        "/api/wishes",
        data={"title": title, "priority": priority},
        headers=as_user(user),
        **extra,
    )
    assert resp.status_code == 201
    return resp.json()


async def people(client, viewer: dict = ME) -> list[dict]:
    resp = await client.get("/api/people", headers=as_user(viewer))
    assert resp.status_code == 200
    return resp.json()


# --- the people list ------------------------------------------------------------


async def test_shows_people_with_wishes_except_me(client):
    await add_as(client, ME, "Моє")
    await add_as(client, OLENA, "Сукня")
    await add_as(client, OLENA, "Книга")

    result = await people(client)

    assert len(result) == 1
    olena = result[0]
    assert olena["first_name"] == "Олена"
    assert olena["last_name"] == "Коваль"
    assert olena["wish_count"] == 2


async def test_person_without_wishes_is_hidden_but_can_browse(client):
    await add_as(client, OLENA, "Сукня")
    await client.get("/api/me", headers=as_user(ME))  # I have a profile but no wishes

    assert [p["first_name"] for p in await people(client, OLENA)] == []
    assert [p["first_name"] for p in await people(client, ME)] == ["Олена"]


async def test_sorted_by_name(client, session_factory):
    async with session_factory() as session:
        session.add_all(AccessGrant(telegram_id=tid) for tid in (51, 52, 53))
        await session.commit()
    for tid, name in [(51, "яна"), (52, "Андрій"), (53, "Богдан")]:
        await add_as(client, {"id": tid, "first_name": name}, "Щось")

    names = [p["first_name"] for p in await people(client)]

    assert names == ["Андрій", "Богдан", "яна"]


async def test_admin_is_listed(client):
    await add_as(client, ADMIN, "Ноутбук")

    assert [p["first_name"] for p in await people(client)] == ["Адмін"]


async def test_strangers_are_never_listed(client, session_factory):
    """A stranger who opened the Mini App has a users row but no access."""
    await add_as(client, OLENA, "Сукня")
    await client.get("/api/me", headers=as_user(STRANGER))

    assert [p["first_name"] for p in await people(client)] == ["Олена"]


async def test_no_private_fields_are_exposed(client):
    await add_as(client, OLENA, "Сукня")

    [olena] = await people(client)

    assert set(olena) == {"id", "first_name", "last_name", "photo_url", "wish_count"}


async def test_stranger_cannot_list_people(client):
    assert (await client.get("/api/people", headers=as_user(STRANGER))).status_code == 403


# --- someone else's list --------------------------------------------------------


async def test_view_someone_elses_list_sorted(client):
    await add_as(client, OLENA, "Хочу", "2")
    await add_as(client, OLENA, "Дуже хочу", "1")
    [olena] = await people(client)

    resp = await client.get(f"/api/people/{olena['id']}/wishes", headers=as_user(ME))

    assert resp.status_code == 200
    assert [w["title"] for w in resp.json()] == ["Дуже хочу", "Хочу"]


async def test_someone_elses_photo_is_visible_to_members(client):
    wish = await add_as(
        client, OLENA, "Сукня", files={"photo": ("p.png", image_bytes("PNG"), "image/png")}
    )

    resp = await client.get(f"/api/wishes/{wish['id']}/photo", headers=as_user(ME))

    assert resp.status_code == 200


async def test_stranger_cannot_view_lists_or_photos(client):
    wish = await add_as(
        client, OLENA, "Сукня", files={"photo": ("p.png", image_bytes("PNG"), "image/png")}
    )
    [olena] = await people(client)

    for url in (f"/api/people/{olena['id']}/wishes", f"/api/wishes/{wish['id']}/photo"):
        assert (await client.get(url, headers=as_user(STRANGER))).status_code == 403


async def test_list_of_stranger_or_missing_user_is_404(client):
    stranger_id = (await client.get("/api/me", headers=as_user(STRANGER))).json()["id"]

    for user_id in (stranger_id, 9999):
        resp = await client.get(f"/api/people/{user_id}/wishes", headers=as_user(ME))
        assert resp.status_code == 404


async def test_cannot_edit_or_delete_someone_elses_wish(client):
    wish = await add_as(client, OLENA, "Сукня")

    edit = await client.patch(
        f"/api/wishes/{wish['id']}", data={"title": "Зламано"}, headers=as_user(ME)
    )
    delete = await client.delete(f"/api/wishes/{wish['id']}", headers=as_user(ME))

    assert edit.status_code == 404
    assert delete.status_code == 404
    [olena] = await people(client)
    titles = [
        w["title"]
        for w in (await client.get(f"/api/people/{olena['id']}/wishes", headers=as_user(ME))).json()
    ]
    assert titles == ["Сукня"]


async def test_photo_hidden_when_owner_has_no_access(client, session_factory):
    wish = await add_as(
        client, OLENA, "Сукня", files={"photo": ("p.png", image_bytes("PNG"), "image/png")}
    )
    async with session_factory() as session:
        await session.delete(await session.get(AccessGrant, OLENA["id"]))
        await session.commit()

    resp = await client.get(f"/api/wishes/{wish['id']}/photo", headers=as_user(ME))

    assert resp.status_code == 404
    assert await people(client) == []


def test_ukrainian_alphabet_order():
    from app.services.people import name_sort_key

    names = ["Їжак", "Ігор", "Євген", "Ґанна", "Гліб", "Іван", "Дмитро", "anna", "Яна"]
    ordered = sorted(names, key=lambda n: name_sort_key(n, None))

    assert ordered == ["Гліб", "Ґанна", "Дмитро", "Євген", "Іван", "Ігор", "Їжак", "Яна", "anna"]
    # The apostrophe is ignored: «Мар'яна» sorts as «Марʼяна» == «Маряна».
    assert sorted(["Марта", "Мар'яна"], key=lambda n: name_sort_key(n, None)) == [
        "Марта",
        "Мар'яна",
    ]


def test_same_first_name_sorted_by_last_name():
    from app.services.people import name_sort_key

    people = [("Олена", "Шевченко"), ("Олена", "Бойко"), ("Олена", None)]
    ordered = sorted(people, key=lambda p: name_sort_key(*p))

    assert ordered == [("Олена", None), ("Олена", "Бойко"), ("Олена", "Шевченко")]
