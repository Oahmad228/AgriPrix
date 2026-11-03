"""CLI entry point for the AgriPrix ML and anomaly pipeline (`make train`)."""

import logging

from src.config import get_settings


def run_ml_status() -> dict[str, str]:
    """Return status metadata for the ML training entry point."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("agriprix.ml")
    logger.info(
        "AgriPrix ML CLI ready (tracking URI: %s, git_sha: %s)",
        settings.mlflow_tracking_uri,
        settings.git_sha,
    )
    return {
        "pipeline": "ml_training",
        "status": "ready",
        "mlflow_tracking_uri": settings.mlflow_tracking_uri,
        "git_sha": settings.git_sha,
    }


if __name__ == "__main__":  # pragma: no cover
    run_ml_status()
