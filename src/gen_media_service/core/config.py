from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    HOST: str = "localhost"
    PORT: int = 5432
    USER: str = "postgres"
    PASSWORD: str = "postgres"
    NAME: str = "gen_media"

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
        )


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    ALPHA_BASE_URL: str = "http://localhost:8101"
    BETA_BASE_URL: str = "http://localhost:8102"
    PROVIDER_TIMEOUT: float = 60.0
    PROVIDER_HTTP_TIMEOUT: float = 5.0
    WEBHOOK_SECRET: str = "dev-webhook-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "gen-media-service"
    DEBUG: bool = False
    MAX_ACTIVE_TASKS: int = 3
    WATCHDOG_INTERVAL_SECONDS: float = 1.0
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)

    def validate_for_api(self) -> None:
        if not self.providers.WEBHOOK_SECRET:
            raise ValueError("WEBHOOK_SECRET must be set")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
