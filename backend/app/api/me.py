from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import CurrentInitData

router = APIRouter(prefix="/api", tags=["me"])


class MeOut(BaseModel):
    telegram_id: int
    first_name: str
    username: str | None
    start_param: str | None


@router.get("/me")
def me(init_data: CurrentInitData) -> MeOut:
    user = init_data.user
    return MeOut(
        telegram_id=user.id,
        first_name=user.first_name,
        username=user.username,
        start_param=init_data.start_param,
    )
