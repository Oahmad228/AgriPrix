"""Centralized application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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

    # Behind a managed platform (Render) the dashboard calls the API over the Internet: it
    # proves it is the dashboard with this shared secret and is not rate-limited. Empty =
    # disabled (Docker network deployments recognise internal calls by their address).
    api_internal_key: str = ""
    # Which X-Forwarded-For entry is the real visitor: "first" when our own proxy (Caddy)
    # rewrites the header, "last" when the platform's proxy appends the address it saw.
    forwarded_for_position: str = "first"

    # Empty locally (Docker network). "require" for a managed database such as Neon.
    postgres_sslmode: str = ""

    def _database_url(self, user: str, password: str) -> str:
        # URL.create quotes special characters, so generated passwords are always safe.
        url = URL.create(
            "postgresql+psycopg",
            username=user,
            password=password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.dw_db,
            query={"sslmode": self.postgres_sslmode} if self.postgres_sslmode else {},
        )
        return url.render_as_string(hide_password=False)

    @property
    def writer_database_url(self) -> str:
        """Return SQLAlchemy URL for the read-write ETL/ML role on agriprix_dw."""
        return self._database_url(self.dw_writer_user, self.dw_writer_password)

    @property
    def readonly_database_url(self) -> str:
        """Return SQLAlchemy URL for the read-only API role on agriprix_dw."""
        return self._database_url(self.dw_readonly_user, self.dw_readonly_password)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
