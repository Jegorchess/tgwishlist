"""Storing wish photos uploaded from the phone.

Every upload is re-encoded to JPEG: this normalises HEIC (iPhone) for all browsers,
caps the resolution, and drops EXIF metadata such as GPS coordinates.
"""

import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_SIDE_PX = 1600
MAX_PIXELS = 60_000_000  # fits 50 MP phone cameras; bigger canvases are refused
# MPO = multi-picture JPEG produced by many phone cameras.
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}
_CHUNK = 64 * 1024


class PhotoError(ValueError):
    pass


class PhotoTooLarge(PhotoError):
    pass


class InvalidPhoto(PhotoError):
    pass


async def read_limited(upload: UploadFile, limit: int = MAX_PHOTO_BYTES) -> bytes:
    """Read the upload, failing as soon as it exceeds ``limit`` bytes."""
    buf = bytearray()
    while chunk := await upload.read(_CHUNK):
        buf.extend(chunk)
        if len(buf) > limit:
            raise PhotoTooLarge(f"Фото завелике (максимум {limit // (1024 * 1024)} МБ)")
    return bytes(buf)


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert to RGB, putting transparent areas on white instead of black."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def save_photo(data: bytes, media_dir: Path) -> str:
    """Validate the image by its content, re-encode it and return the stored file name."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise InvalidPhoto("Підтримуються лише JPEG, PNG, WebP або HEIC")
            # Checked before decoding: a tiny file can declare a huge canvas.
            if img.width * img.height > MAX_PIXELS:
                raise InvalidPhoto("Фото має завелику роздільну здатність")
            img.draft("RGB", (MAX_SIDE_PX, MAX_SIDE_PX))  # cheap JPEG downscale on decode
            img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))  # shrink before any full-size copies
            img = ImageOps.exif_transpose(img)
            img = _to_rgb(img)
            out = io.BytesIO()
            img.save(out, "JPEG", quality=85, optimize=True)  # no exif= -> metadata dropped
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise InvalidPhoto("Файл не є зображенням") from exc

    media_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (media_dir / name).write_bytes(out.getvalue())
    return name
