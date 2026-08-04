"""Centralised, typed configuration loaded from the local .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings; credentials remain outside version-controlled files."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "duckdb:///data/stock_agent.duckdb"
    openai_api_key: str | None = None
    openai_model: str | None = None
    tushare_token: str | None = None


settings = Settings()
