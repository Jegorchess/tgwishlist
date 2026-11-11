import asyncio
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.auth.deps import MemberUser
from app.services.link_preview import (
    MAX_PAGE_BYTES,
    FetchFailed,
    PageFetcher,
    UnsafeUrl,
    decode_html,
    get_fetcher,
    parse_preview,
)
from app.services.photos import MAX_PHOTO_BYTES

router = APIRouter(prefix="/api/link-preview", tags=["link-preview"])

RASTER_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}

FetcherDep = Annotated[PageFetcher, Depends(get_fetcher)]


class PreviewIn(BaseModel):
    url: str = Field(max_length=2000)


class PreviewOut(BaseModel):
    """Every field may be null: the page had nothing usable (or didn't answer)."""

    title: str | None = None
    price: Decimal | None = None
    image_url: str | None = None


@router.post("")
async def link_preview(body: PreviewIn, _: MemberUser, fetcher: FetcherDep) -> PreviewOut:
    try:
        page = await fetcher.get(
            body.url, max_bytes=MAX_PAGE_BYTES, accept="text/html,application/xhtml+xml"
        )
    except UnsafeUrl as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except FetchFailed:
        return PreviewOut()  # the form simply stays as it is
    if "html" not in page.content_type:
        return PreviewOut()
    # CPU-bound on up to 2 MB of HTML: keep the event loop free.
    preview = await asyncio.to_thread(parse_preview, decode_html(page), page.url)
    return PreviewOut(title=preview.title, price=preview.price, image_url=preview.image_url)


@router.get("/image")
async def link_preview_image(
    _: MemberUser, fetcher: FetcherDep, url: Annotated[str, Query(max_length=2000)]
) -> Response:
    """Proxy the page's image so the app can attach it like a photo from the phone.

    The upload endpoint validates and re-encodes it as usual.
    """
    try:
        image = await fetcher.get(url, max_bytes=MAX_PHOTO_BYTES, accept="image/*")
    except UnsafeUrl as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except FetchFailed as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Image is not available") from exc
    if image.content_type not in RASTER_TYPES:  # no SVG: it's a document, not a photo
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Not a supported image")
    return Response(
        image.body,
        media_type=image.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": "attachment",
        },
    )
