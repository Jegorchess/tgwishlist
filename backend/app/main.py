from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.invite import router as invite_router
from app.api.link_preview import router as link_preview_router
from app.api.me import router as me_router
from app.api.people import router as people_router
from app.api.reservations import router as reservations_router
from app.api.share import router as share_router
from app.api.wishes import router as wishes_router

app = FastAPI(title="Family Wishlist API")
app.include_router(me_router)
app.include_router(invite_router)
app.include_router(admin_router)
app.include_router(people_router)
app.include_router(reservations_router)
app.include_router(share_router)
app.include_router(link_preview_router)
app.include_router(wishes_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
