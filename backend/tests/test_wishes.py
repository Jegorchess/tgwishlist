"""W-2: adding a wish (issue #4)."""

import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.models import User, WishItem
from app.services.photos import MAX_PHOTO_BYTES, MAX_PIXELS, MAX_SIDE_PX
from tests.helpers import auth, make_init_data

OTHER_USER = {"id": 43, "first_name": "Мама"}


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (40, 30), exif: bool = False) -> bytes:
    img = Image.new("RGB", size, "red")
    buf = io.BytesIO()
    if fmt == "MPO":
        # Multi-picture JPEG, as saved by many phone cameras.
        img.save(buf, "MPO", save_all=True, append_images=[Image.new("RGB", size, "blue")])
    elif exif:
        meta = Image.Exif()
        meta[0x010F] = "SecretCam"  # Make
        img.save(buf, fmt, exif=meta)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


async def add(client, data=None, photo=None, init_data=None):
    files = {"photo": photo} if photo else None
    return await client.post(
        "/api/wishes", data=data or {"title": "Книга"}, files=files, headers=auth(init_data)
    )


async def count_wishes(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(WishItem))


# --- creating ---------------------------------------------------------------


async def test_title_only_uses_defaults(client, session_factory):
    resp = await add(client, {"title": "  Книга  "})

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Книга"
    assert body["priority"] == 2
    assert body["price"] is None
    assert body["url"] is None
    assert body["description"] is None
    assert body["has_photo"] is False
    assert body["created_at"]


async def test_all_fields_are_saved(client, session_factory):
    resp = await add(
        client,
        {
            "title": "Навушники",
            "price": "249,99",
            "priority": "1",
            "url": "https://example.com/item?id=1",
            "description": "Чорні, бездротові",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["price"] == "249.99"
    assert body["priority"] == 1
    assert body["url"] == "https://example.com/item?id=1"
    assert body["description"] == "Чорні, бездротові"


async def test_wish_belongs_to_current_user(client, session_factory):
    resp = await add(client, {"title": "Книга"})

    async with session_factory() as session:
        wish = await session.get(WishItem, resp.json()["id"])
        owner = await session.get(User, wish.owner_id)
    assert owner.telegram_id == 42


async def test_owner_in_body_is_ignored(client, session_factory):
    # Make another user exist, then try to create a wish on their behalf.
    await client.get("/api/me", headers=auth(make_init_data(user=OTHER_USER)))
    resp = await add(client, {"title": "Чуже", "owner_id": "1", "user_id": "1"})

    async with session_factory() as session:
        wish = await session.get(WishItem, resp.json()["id"])
        owner = await session.get(User, wish.owner_id)
    assert owner.telegram_id == 42


async def test_requires_auth(client, session_factory):
    resp = await client.post("/api/wishes", data={"title": "Книга"})

    assert resp.status_code == 401
    assert await count_wishes(session_factory) == 0


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "Книга", "price": "-1"},
        {"title": "Книга", "price": "1.005"},
        {"title": "Книга", "price": "дорого"},
        {"title": "Книга", "price": "100000000"},
        {"title": "Книга", "priority": "0"},
        {"title": "Книга", "priority": "4"},
        {"title": "Книга", "url": "example.com"},
        {"title": "Книга", "url": "ftp://example.com/file"},
        {"title": "Книга", "url": "javascript:alert(1)"},
        {"title": "Книга", "url": "https://exa mple.com"},
        {"title": "Книга", "description": "x" * 1001},
    ],
)
async def test_invalid_input_is_rejected(client, session_factory, data):
    resp = await client.post("/api/wishes", data=data, headers=auth())

    assert resp.status_code == 422
    assert await count_wishes(session_factory) == 0


async def test_limits_are_inclusive(client):
    resp = await add(
        client,
        {"title": "x" * 200, "description": "y" * 1000, "price": "0", "priority": "3"},
    )

    assert resp.status_code == 201
    assert resp.json()["price"] == "0.00"


# --- photos -----------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["JPEG", "MPO", "PNG", "WEBP", "HEIF"])
async def test_photo_formats_are_stored_as_jpeg(client, media_dir, fmt):
    resp = await add(client, photo=(f"p.{fmt.lower()}", image_bytes(fmt), "image/octet-stream"))

    assert resp.status_code == 201
    assert resp.json()["has_photo"] is True
    [stored] = list(media_dir.iterdir())
    with Image.open(stored) as img:
        assert img.format == "JPEG"


async def test_photo_is_downscaled_and_metadata_removed(client, media_dir):
    big = image_bytes("JPEG", size=(MAX_SIDE_PX * 2, MAX_SIDE_PX), exif=True)
    resp = await add(client, photo=("p.jpg", big, "image/jpeg"))

    assert resp.status_code == 201
    [stored] = list(media_dir.iterdir())
    with Image.open(stored) as img:
        assert max(img.size) == MAX_SIDE_PX
        assert not img.getexif()


async def test_mpo_fixture_really_is_mpo():
    assert Image.open(io.BytesIO(image_bytes("MPO"))).format == "MPO"


async def test_exif_rotation_is_applied(client, media_dir):
    img = Image.new("RGB", (40, 20), "red")
    meta = Image.Exif()
    meta[0x0112] = 6  # Orientation: rotate 90° clockwise
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=meta)

    await add(client, photo=("p.jpg", buf.getvalue(), "image/jpeg"))

    [stored] = list(media_dir.iterdir())
    with Image.open(stored) as out:
        assert out.size == (20, 40)


async def test_transparent_png_gets_white_background(client, media_dir):
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buf, "PNG")

    await add(client, photo=("p.png", buf.getvalue(), "image/png"))

    [stored] = list(media_dir.iterdir())
    with Image.open(stored) as out:
        r, g, b = out.getpixel((5, 5))
        assert min(r, g, b) > 240


async def test_huge_canvas_in_small_file_is_rejected(client, session_factory, media_dir):
    # A blank 1-bit PNG compresses to a few KB but would need GBs of RAM to decode.
    side = int(MAX_PIXELS**0.5) + 100
    buf = io.BytesIO()
    Image.new("1", (side, side)).save(buf, "PNG")
    assert len(buf.getvalue()) < MAX_PHOTO_BYTES

    resp = await add(client, photo=("bomb.png", buf.getvalue(), "image/png"))

    assert resp.status_code == 422
    assert await count_wishes(session_factory) == 0


async def test_non_image_is_rejected(client, session_factory, media_dir):
    resp = await add(client, photo=("evil.jpg", b"<script>alert(1)</script>", "image/jpeg"))

    assert resp.status_code == 422
    assert await count_wishes(session_factory) == 0
    assert not media_dir.exists() or not any(media_dir.iterdir())


async def test_unsupported_image_format_is_rejected(client, session_factory):
    resp = await add(client, photo=("p.gif", image_bytes("GIF"), "image/gif"))

    assert resp.status_code == 422
    assert await count_wishes(session_factory) == 0


async def test_too_large_photo_is_rejected(client, session_factory):
    resp = await add(client, photo=("p.jpg", b"\0" * (MAX_PHOTO_BYTES + 1), "image/jpeg"))

    assert resp.status_code == 413
    assert await count_wishes(session_factory) == 0


async def test_empty_file_field_means_no_photo(client):
    resp = await add(client, photo=("", b"", "application/octet-stream"))

    assert resp.status_code == 201
    assert resp.json()["has_photo"] is False


# --- reading the photo --------------------------------------------------------


async def test_owner_can_get_photo(client):
    wish = (await add(client, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    resp = await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(resp.content)).format == "JPEG"


async def test_photo_requires_auth(client):
    wish = (await add(client, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    assert (await client.get(f"/api/wishes/{wish['id']}/photo")).status_code == 401


async def test_other_user_cannot_get_photo(client):
    wish = (await add(client, photo=("p.png", image_bytes("PNG"), "image/png"))).json()

    resp = await client.get(
        f"/api/wishes/{wish['id']}/photo", headers=auth(make_init_data(user=OTHER_USER))
    )

    assert resp.status_code == 404


async def test_wish_without_photo_has_no_photo(client):
    wish = (await add(client)).json()

    assert (await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())).status_code == 404


async def test_missing_photo_file_is_404_not_500(client, media_dir):
    wish = (await add(client, photo=("p.png", image_bytes("PNG"), "image/png"))).json()
    for f in media_dir.iterdir():
        f.unlink()

    assert (await client.get(f"/api/wishes/{wish['id']}/photo", headers=auth())).status_code == 404
