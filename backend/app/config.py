from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    # URL where the Mini App frontend is served (must be HTTPS for Telegram).
    webapp_url: str = "http://localhost:5173"
    # How long a signed initData stays valid, in seconds.
    init_data_max_age: int = 24 * 60 * 60
    # Allow the "dev" auth bypass. NEVER enable in production.
    dev_auth: bool = False
    database_url: str = "postgresql+asyncpg://wishlist:wishlist@localhost:5433/wishlist"
    # Where uploaded wish photos are stored (a Docker volume in production).
    media_dir: str = "media"
    # Comma-separated Telegram IDs that always have access and manage the invite link.
    admin_telegram_ids: str = ""
    # Bot username for invite links; looked up via the Telegram API when empty.
    bot_username: str = ""

    @field_validator("admin_telegram_ids")
    @classmethod
    def check_admin_ids(cls, value: str) -> str:
        parts = [x for x in value.replace(" ", "").split(",") if x]
        if not all(x.isdigit() for x in parts):
            raise ValueError("ADMIN_TELEGRAM_IDS must be comma-separated numeric Telegram IDs")
        return ",".join(parts)

    @property
    def admin_ids(self) -> frozenset[int]:
        return frozenset(int(x) for x in self.admin_telegram_ids.split(",") if x)


@lru_cache
def get_settings() -> Settings:
    return Settings()
