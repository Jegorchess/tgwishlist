from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.auth.deps import CurrentInitData, CurrentUser

router = APIRouter(prefix="/api", tags=["me"])


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    photo_url: str | None
    start_param: str | None = None


@router.get("/me")
def me(user: CurrentUser, init_data: CurrentInitData) -> MeOut:
    out = MeOut.model_validate(user)
    out.start_param = init_data.start_param
    return out
