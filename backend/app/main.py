from fastapi import FastAPI

from app.api.me import router as me_router

app = FastAPI(title="Family Wishlist API")
app.include_router(me_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
