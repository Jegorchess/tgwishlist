from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
