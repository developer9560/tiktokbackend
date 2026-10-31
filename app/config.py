"""Application settings with fixed local defaults and process-only secrets."""

import os

from pydantic import BaseModel, Field, SecretStr, field_validator


def _process_secret(name: str) -> SecretStr | None:
    value = os.environ.get(name)
    return SecretStr(value) if value else None


class Settings(BaseModel):
    brightdata_api_token: str = "6d7e9eb7-b797-45db-9877-9dd89e48c85b"
    brightdata_dataset_id: str | None = "gd_lu702nij2f790tmv9h"
    brightdata_keyword_dataset_id: str = "gd_lu702nij2f790tmv9h"
    brightdata_base_url: str = "https://api.brightdata.com"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: SecretStr | None = Field(default_factory=lambda: _process_secret("MYSQL_PASSWORD"))
    mysql_database: str = "tiktokdb"
    request_timeout_seconds: float = 120.0
    max_collection_duration_seconds: int = 1800
    max_search_batches: int = 1
    max_search_target_count: int = 5000
    language_confidence_threshold: float = 0.8
    snapshot_poll_interval_seconds: float = 5.0
    cors_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("request_timeout_seconds must be greater than zero")
        return value

    @field_validator("max_collection_duration_seconds", "max_search_batches")
    @classmethod
    def validate_collection_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("collection limits must be at least one")
        return value

    @field_validator("max_search_target_count")
    @classmethod
    def validate_target_count_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_search_target_count must be at least one")
        return value

    @field_validator("language_confidence_threshold")
    @classmethod
    def validate_language_threshold(cls, value: float) -> float:
        if not 0 < value <= 1:
            raise ValueError("language_confidence_threshold must be between zero and one")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
