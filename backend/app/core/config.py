from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TPS IB Management System"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://ib_app:ib_app@localhost:5432/ib_tps"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173"]

    default_timeline_start: str = "2025-10"
    default_weekly_start: str = "2025-11"

    backup_dir: str = "./backups"

    rate_limit_login: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
