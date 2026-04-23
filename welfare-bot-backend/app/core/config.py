from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Welfare Bot API"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "welfare_bot"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Required for JWT — set in .env
    secret_key: str = "change-this-to-a-long-random-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()