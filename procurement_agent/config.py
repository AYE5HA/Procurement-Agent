from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    analysis_provider: str = "azure"
    azure_ai_foundry_endpoint: str = ""
    azure_ai_foundry_api_key: str = ""
    foundry_model_name: str = "gpt-4o"
    database_url: str = "sqlite:///./data/procurement_agent.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    api_access_key: str = ""
    rate_limit_requests: int = Field(default=20, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    max_contract_characters: int = Field(default=100_000, ge=1_000)
    max_processing_drift_seconds: float = Field(default=120.0, gt=0)
    analysis_timeout_seconds: float = Field(default=90.0, gt=0)
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("analysis_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"deterministic", "azure"}:
            raise ValueError("ANALYSIS_PROVIDER must be azure or deterministic")
        return normalized

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.analysis_provider == "azure" and not (
            self.azure_ai_foundry_endpoint and self.azure_ai_foundry_api_key
        ):
            raise ValueError(
                "Microsoft Foundry requires AZURE_AI_FOUNDRY_ENDPOINT and "
                "AZURE_AI_FOUNDRY_API_KEY"
            )
        credential_values = (
            self.azure_ai_foundry_endpoint.lower(),
            self.azure_ai_foundry_api_key.lower(),
        )
        if self.analysis_provider == "azure" and any(
            marker in value
            for value in credential_values
            for marker in ("your-", "placeholder", "example")
        ):
            raise ValueError("Microsoft Foundry credentials cannot contain placeholder values")
        if self.environment == "production" and self.analysis_provider != "azure":
            raise ValueError("Production deployments must use Microsoft Foundry")
        if self.environment == "production" and "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not permitted in production")
        return self

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only SQLite DATABASE_URL values are currently supported")
        return Path(self.database_url.removeprefix(prefix)).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
