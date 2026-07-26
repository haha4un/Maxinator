from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    SettingsConfigDict,
)


class _CommaSeparatedAdminIdsMixin:
    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "admin_max_ids" and isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]
        return super().prepare_field_value(
            field_name,
            field,
            value,
            value_is_complex,
        )


class _EnvSettingsSource(
    _CommaSeparatedAdminIdsMixin,
    EnvSettingsSource,
):
    pass


class _DotEnvSettingsSource(
    _CommaSeparatedAdminIdsMixin,
    DotEnvSettingsSource,
):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_bot_token: str
    database_url: str
    admin_max_ids: set[str] = Field(default_factory=set)
    patient_code_length: int = 6
    assignment_code_length: int = 8
    assignment_expiration_hours: int | None = 168

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (
            init_settings,
            _EnvSettingsSource(settings_cls),
            _DotEnvSettingsSource(
                settings_cls,
                env_file=dotenv_settings.env_file,
                env_file_encoding=dotenv_settings.env_file_encoding,
            ),
            file_secret_settings,
        )

    @field_validator("admin_max_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Any) -> set[str]:
        if value is None or value == "":
            return set()
        if isinstance(value, str):
            return {
                item.strip()
                for item in value.split(",")
                if item.strip()
            }
        return {str(item).strip() for item in value if str(item).strip()}

    @field_validator("patient_code_length", "assignment_code_length")
    @classmethod
    def validate_positive_code_length(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Code length must be positive")
        return value

    @field_validator("assignment_expiration_hours")
    @classmethod
    def validate_expiration_hours(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Expiration hours must be positive or null")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
