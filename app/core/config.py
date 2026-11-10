"""Configurações da aplicação carregadas do ambiente."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da API e da integração com o LinkedIn."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""
    linkedin_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
    )
    http_timeout_seconds: float = Field(default=30, gt=0)
    cache_backend: str = "sqlite"
    cache_sqlite_path: Path = Path("./data/jobs_cache.db")


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância reutilizável das configurações."""

    return Settings()
