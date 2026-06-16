"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    master_key: str | None = None
    database_url: str = "sqlite:///data/clinicalsafe_nim.db"
    nvidia_api_key: str | None = None
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_default_model: str = "meta/llama-3.3-70b-instruct"
    nim_timeout_seconds: int = 120
    log_level: str = "INFO"


settings = Settings()
