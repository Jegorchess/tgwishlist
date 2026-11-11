from fastapi import FastAPI

from app.api.me import router as me_router
from app.api.wishes import router as wishes_router

app = FastAPI(title="Family Wishlist API")
app.include_router(me_router)
app.include_router(wishes_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
