"""Monthly refresh (EF-16): ETL, then retraining only when the data changed.

    python -m src.ops.refresh               # what the scheduler runs each month
    python -m src.ops.refresh --force-train # retrain even if no source file changed

The API keeps serving the previous campaign until the new one is promoted at the very end
of training (one transaction), so visitors never see a half-updated state.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from sqlalchemy import Engine

from src.config import get_settings

logger = logging.getLogger("agriprix.ops")


@dataclass
class RefreshOutcome:
    etl_run_id: int
    data_changed: bool
    training_run_id: int | None


def run_refresh(engine: Engine, *, force_train: bool = False, use_mlflow: bool = True,
                etl=None, train=None) -> RefreshOutcome:  # fmt: skip
    """Run the ETL then, if anything changed (or when forced), a training campaign.

    ``etl`` and ``train`` default to the real pipeline functions; tests inject fakes.
    """
    from src.etl.pipeline import run_etl
    from src.ml.train import run_training

    etl = etl or run_etl
    train = train or run_training
    sha = get_settings().git_sha

    summary = etl(engine, _raw_dir(), git_sha=sha)
    facts = summary.facts
    changed = bool(facts.inserted or facts.updated or facts.deleted)
    logger.info(
        "ETL run %s: +%d new, %d updated, -%d removed observations",
        summary.etl_run_id, facts.inserted, facts.updated, facts.deleted,
    )  # fmt: skip
    if not changed and not force_train:
        logger.info("No source data changed since the last run: training skipped")
        return RefreshOutcome(summary.etl_run_id, False, None)
    run_id = train(engine, git_sha=sha, use_mlflow=use_mlflow)
    logger.info("Training run %s promoted to production", run_id)
    return RefreshOutcome(summary.etl_run_id, changed, run_id)


def _raw_dir():
    from src.etl.cli import DEFAULT_RAW_DIR

    return DEFAULT_RAW_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgriPrix monthly refresh")
    parser.add_argument("--force-train", action="store_true")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("httpx", "urllib3", "mlflow", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from src.etl.db import make_writer_engine

    engine = make_writer_engine()
    try:
        outcome = run_refresh(engine, force_train=args.force_train, use_mlflow=not args.no_mlflow)
    finally:
        engine.dispose()
    trained = (
        f"training run {outcome.training_run_id}" if outcome.training_run_id else "no training"
    )
    print(
        f"Refresh done: ETL run {outcome.etl_run_id}, data changed: {outcome.data_changed}, {trained}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
