"""CLI entry point for the AgriPrix forecasting campaign (`make train`).

Usage (inside the job-runner container, after `make etl`):
    python -m src.ml.cli              # backtest, champions, forecasts, MLflow tracking
    python -m src.ml.cli --no-mlflow  # same without the MLflow server
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.config import get_settings


def run_ml_status() -> dict[str, str]:
    """Return static metadata about the ML entry point (used by smoke tests)."""
    settings = get_settings()
    return {
        "pipeline": "ml_training",
        "status": "ready",
        "mlflow_tracking_uri": settings.mlflow_tracking_uri,
        "git_sha": settings.git_sha,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgriPrix forecasting campaign")
    parser.add_argument("--no-mlflow", action="store_true", help="skip MLflow tracking")
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("httpx", "urllib3", "mlflow", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from src.etl.db import make_writer_engine
    from src.ml.train import run_training

    engine = make_writer_engine()
    try:
        run_id = run_training(engine, git_sha=settings.git_sha, use_mlflow=not args.no_mlflow)
    finally:
        engine.dispose()
    print(f"Training run {run_id} finished and promoted to production.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
