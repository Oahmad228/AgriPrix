"""CLI entry point for the AgriPrix ETL pipeline (`make etl`)."""

import logging

from src.config import get_settings


def run_etl_status() -> dict[str, str]:
    """Return status metadata for the ETL runner entry point."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("agriprix.etl")
    logger.info(
        "AgriPrix ETL CLI ready for database %s on host %s", settings.dw_db, settings.postgres_host
    )
    return {
        "pipeline": "etl",
        "status": "ready",
        "database": settings.dw_db,
        "writer_user": settings.dw_writer_user,
    }


if __name__ == "__main__":  # pragma: no cover
    run_etl_status()
