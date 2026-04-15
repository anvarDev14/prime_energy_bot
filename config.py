from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Channel
    CHANNEL_ID: str = ""  # e.g. @prime_energy_uz

    # MoySklad
    MOYSKLAD_TOKEN: str = ""
    MOYSKLAD_BONUS_FIELD_ID: str = ""  # custom field UUID

    # SerpAPI
    SERP_API_KEY: str = ""

    # Unsplash
    UNSPLASH_ACCESS_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///prime_energy.db"

    # Redis (optional)
    REDIS_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
