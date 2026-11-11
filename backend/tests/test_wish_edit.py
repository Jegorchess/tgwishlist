"""W-4: editing and deleting a wish (issue #8)."""

from sqlalchemy import func, select

from app.models import WishItem
from app.services.photos import MAX_PHOTO_BYTES
from tests.helpers import auth, make_init_data
from tests.test_wishes import OTHER_USER, add, image_bytes

FULL = {
    "title": "Навушники",
    "price": "249.99",
    "priority": "1",
    "url": "https://example.com/a",
    "description": "Чорні",
}


async def edit(client, wish_id, data, photo=None, init_data=None):
    files = {"photo": photo} if photo else None
    return await client.patch(
        f"/api/wishes/{wish_id}", data=data, files=files, headers=auth(init_data)
    )


async def get_wish(session_factory, wish_id) -> WishItem | None:
    async with session_factory() as session:
        return await session.get(WishItem, wish_id)


def photos(media_dir) -> list[str]:
    return sorted(p.name for p in media_dir.iterdir()) if media_dir.exists() else []


# --- editing ------------------------------------------------------------------


async def test_edit_replaces_all_fields(client, session_factory):
    wish = (await add(client, FULL)).json()

    resp = await edit(
        client,
        wish["id"],
        {"title": "Книга", "price": "40,50", "priority": "3", "url": "", "description": ""},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == wish["id"]
    assert body["title"] == "Книга"
    assert body["price"] == "40.50"
    assert body["priority"] == 3
    assert body["url"] is None
    assert body["description"] is None
    assert body["created_at"] == wish["created_at"]


async def test_edit_changes_position_in_sorted_list(client):
    first = (await add(client, {"title": "A", "priority": "1"})).json()
    await add(client, {"title": "B", "priority": "2"})

    await edit(client, first["id"], {"title": "A", "priority": "3"})

    titles = [w["title"] for w in (await client.get("/api/wishes", headers=auth())).json()]
    assert titles == ["B", "A"]


async def test_edit_validation_matches_create(client, session_factory):
    wish = (await add(client, FULL)).json()

    for data in [{"title": " "}, {"title": "A", "price": "-1"}, {"title": "A", "url": "nope"}]:
        assert (await edit(client, wish["id"], data)).status_code == 422

    stored = await get_wish(session_factory, wish["id"])
    assert stored.title == "Навушники"


async def test_edit_keeps_photo_by_default(client, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    body = (await edit(client, wish["id"], {"title": "Нова назва"})).json()

    assert body["has_photo"] is True
    assert body["photo_version"] == wish["photo_version"]
    assert len(photos(media_dir)) == 1


async def test_edit_replaces_photo_and_deletes_old_file(client, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()
    [old_file] = photos(media_dir)

    body = (
        await edit(client, wish["id"], FULL, photo=("n.jpg", image_bytes("JPEG"), "image/jpeg"))
    ).json()

    assert body["has_photo"] is True
    assert body["photo_version"] != wish["photo_version"]
    [new_file] = photos(media_dir)
    assert new_file != old_file
    resp = await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())
    assert resp.status_code == 200


async def test_edit_removes_photo(client, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    body = (await edit(client, wish["id"], {**FULL, "remove_photo": "true"})).json()

    assert body["has_photo"] is False
    assert body["photo_version"] is None
    assert photos(media_dir) == []


async def test_edit_with_invalid_photo_changes_nothing(client, session_factory, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    resp = await edit(client, wish["id"], {"title": "X"}, photo=("e.jpg", b"nope", "image/jpeg"))

    assert resp.status_code == 422
    assert (await get_wish(session_factory, wish["id"])).title == "Навушники"
    assert len(photos(media_dir)) == 1


async def test_cannot_edit_someone_elses_wish(client, session_factory, media_dir):
    wish = (await add(client, FULL)).json()

    resp = await edit(
        client,
        wish["id"],
        {"title": "Зламано"},
        photo=("p.png", image_bytes("PNG"), "image/png"),
        init_data=make_init_data(user=OTHER_USER),
    )

    assert resp.status_code == 404
    assert (await get_wish(session_factory, wish["id"])).title == "Навушники"
    assert photos(media_dir) == []  # nothing stored for a rejected request


async def test_edit_missing_wish_is_404(client):
    assert (await edit(client, 9999, {"title": "A"})).status_code == 404


async def test_edit_requires_auth(client):
    wish = (await add(client, FULL)).json()

    resp = await client.patch(f"/api/wishes/{wish['id']}", data={"title": "A"})

    assert resp.status_code == 401


# --- deleting -----------------------------------------------------------------


async def test_delete_removes_wish_and_photo(client, session_factory, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    resp = await client.delete(f"/api/wishes/{wish['id']}", headers=auth())

    assert resp.status_code == 204
    assert await get_wish(session_factory, wish["id"]) is None
    assert photos(media_dir) == []
    assert (await client.get("/api/wishes", headers=auth())).json() == []


async def test_cannot_delete_someone_elses_wish(client, session_factory):
    wish = (await add(client, FULL)).json()

    resp = await client.delete(
        f"/api/wishes/{wish['id']}", headers=auth(make_init_data(user=OTHER_USER))
    )

    assert resp.status_code == 404
    assert await get_wish(session_factory, wish["id"]) is not None


async def test_delete_missing_wish_is_404(client):
    assert (await client.delete("/api/wishes/9999", headers=auth())).status_code == 404


async def test_delete_requires_auth(client, session_factory):
    wish = (await add(client, FULL)).json()

    assert (await client.delete(f"/api/wishes/{wish['id']}")).status_code == 401
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WishItem)) == 1


async def test_new_photo_wins_over_remove_flag(client, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()
    [old_file] = photos(media_dir)

    body = (
        await edit(
            client,
            wish["id"],
            {**FULL, "remove_photo": "true"},
            photo=("n.jpg", image_bytes("JPEG"), "image/jpeg"),
        )
    ).json()

    assert body["has_photo"] is True
    [new_file] = photos(media_dir)
    assert new_file != old_file


async def test_too_large_photo_on_edit_keeps_old_one(client, media_dir):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()
    before = photos(media_dir)

    resp = await edit(
        client, wish["id"], FULL, photo=("big.jpg", b"\0" * (MAX_PHOTO_BYTES + 1), "image/jpeg")
    )

    assert resp.status_code == 413
    assert photos(media_dir) == before
    assert (await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())).status_code == 200


async def test_photo_is_gone_after_removal_or_deletion(client):
    a = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()
    b = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    await edit(client, a["id"], {**FULL, "remove_photo": "true"})
    await client.delete(f"/api/wishes/{b['id']}", headers=auth())

    for wish in (a, b):
        resp = await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())
        assert resp.status_code == 404


async def test_photo_response_is_cacheable(client):
    wish = (await add(client, FULL, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    resp = await client.get(
        f"/api/wishes/{wish['id']}/photo?v={wish['photo_version']}", headers=auth()
    )

    assert "immutable" in resp.headers["cache-control"]
    assert "private" in resp.headers["cache-control"]
