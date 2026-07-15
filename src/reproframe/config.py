from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REPROFRAME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mode: Literal["fixture", "gmi", "gemini-svg"] = "fixture"
    artifact_dir: Path = Path("artifacts/runs")
    max_iterations: int = Field(default=3, ge=1, le=5)
    gmi_image_model: str = "seedream-5.0-lite"
    gemini_text_model: str = "gemini-3.1-flash-lite"
    generation_timeout_seconds: int = Field(default=180, ge=30, le=900)
    gmi_api_key: str | None = Field(default=None, validation_alias="GMI_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    b2_key_id: str | None = Field(default=None, validation_alias="B2_KEY_ID")
    b2_app_key: str | None = Field(default=None, validation_alias="B2_APP_KEY")
    b2_bucket: str | None = Field(default=None, validation_alias="B2_BUCKET")
    b2_region: str | None = Field(default=None, validation_alias="B2_REGION")


@lru_cache
def get_settings() -> Settings:
    return Settings()
