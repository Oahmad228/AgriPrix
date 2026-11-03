"""Centralized application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and database configuration parameters."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    git_sha: str = "dev-local"

    postgres_host: str = "db"
    postgres_port: int = 5432
    dw_db: str = "agriprix_dw"

    dw_writer_user: str = "agriprix_etl_writer"
    dw_writer_password: str = "agriprix_writer_local_dev"

    dw_readonly_user: str = "agriprix_api_readonly"
    dw_readonly_password: str = "agriprix_readonly_local_dev"

    mlflow_tracking_uri: str = "http://mlflow:5000"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_rate_limit: str = "60/minute"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501,http://dashboard:8501"
    enable_currency_conversion: bool = False

    api_base_url: str = "http://api:8000"

    @property
    def writer_database_url(self) -> str:
        """Return SQLAlchemy URL for the read-write ETL/ML role on agriprix_dw."""
        return (
            f"postgresql+psycopg://{self.dw_writer_user}:{self.dw_writer_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.dw_db}"
        )

    @property
    def readonly_database_url(self) -> str:
        """Return SQLAlchemy URL for the read-only API role on agriprix_dw."""
        return (
            f"postgresql+psycopg://{self.dw_readonly_user}:{self.dw_readonly_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.dw_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
