from pathlib import Path

from fastapi.templating import Jinja2Templates
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_comma_list(v: str | list[str]) -> list[str]:
    if isinstance(v, list):
        return v
    return [x.strip() for x in v.split(",") if x.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "development"
    TESTING: bool = False
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    PAGINATION_SIZES: list[int] = [10, 20, 50, 100]
    EXPIRY_WARNING_DAYS: int = 90
    MAX_AGE: int = 86400
    SESSION_MAX_AGE: int = 86400
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
    ]

    DATABASE_URL: str | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5434"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "pillstore_db"
    TELEGRAM_BOT_TOKEN: str = ""

    @field_validator("ALLOWED_HOSTS", "ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: str | list[str]) -> list[str]:
        return _parse_comma_list(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def add_test_hosts(self) -> "Settings":
        if self.TESTING and "test" not in self.ALLOWED_HOSTS:
            self.ALLOWED_HOSTS = [*self.ALLOWED_HOSTS, "test", "testserver"]
        return self

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL and not self.TESTING:
            return self.DATABASE_URL
        db_name = self.POSTGRES_DB
        if self.TESTING and not db_name.endswith("_test"):
            db_name = f"{db_name}_test" if db_name == "pillstore_db" else db_name
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{db_name}"
        )


settings = Settings()

templates_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=templates_dir)
