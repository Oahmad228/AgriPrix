"""CLI entry point for the AgriPrix ETL pipeline (`make etl`).

Usage (inside the job-runner container):
    python -m src.etl.cli             # download verified sources, then load the warehouse
    python -m src.etl.cli --offline   # reuse files already in data/raw (MD5 still recorded)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config import get_settings

DEFAULT_RAW_DIR = Path("data/raw")


def run_etl_status() -> dict[str, str]:
    """Return static metadata about the ETL entry point (used by smoke tests)."""
    settings = get_settings()
    return {
        "pipeline": "etl",
        "status": "ready",
        "database": settings.dw_db,
        "writer_user": settings.dw_writer_user,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgriPrix ETL: sources -> star schema")
    parser.add_argument("--offline", action="store_true", help="use files already in --raw-dir")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx logs every request URL at INFO, including HDX's pre-signed S3 URLs that embed
    # temporary AWS tokens: keep them out of logs and CI output.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Imported lazily so that `--help` and the smoke tests stay fast.
    from src.etl.db import make_writer_engine
    from src.etl.pipeline import run_etl

    engine = make_writer_engine()
    try:
        summary = run_etl(engine, args.raw_dir, git_sha=settings.git_sha, offline=args.offline)
    finally:
        engine.dispose()
    print(
        f"ETL run {summary.etl_run_id}: {summary.rows_read} rows read, "
        f"{summary.facts.staged} observations in sources (+{summary.facts.inserted} new, "
        f"{summary.facts.updated} updated, -{summary.facts.deleted} removed), "
        f"{summary.rows_rejected} rejected "
        f"({summary.quality.reject_rate:.3%}), {summary.series_total} series, "
        f"{summary.quality.eligible_series} ML-eligible"
    )
    for warning in summary.quality.warnings:
        print(f"WARNING {warning}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
