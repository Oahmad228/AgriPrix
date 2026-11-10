"""Compute ML-eligible series counts from a folder of raw files, without any database.

Used to reconcile the ETL with the Phase 0-2 audit on the frozen 2026-11-03 snapshot:
    python -m src.etl.reconcile data/raw/snapshot_20261103
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.etl.eligibility import build_series_catalog
from src.etl.pipeline import local_files, parse_all
from src.etl.transform import normalize, resolve_duplicates


def eligible_counts(raw_dir: Path) -> dict[str, int]:
    parsed, _rejects, _rows = parse_all(local_files(raw_dir))
    observations, _duplicates = resolve_duplicates(normalize(parsed))
    catalog = build_series_catalog(observations)
    eligible = catalog[catalog["is_ml_eligible"]]
    return {k: int(v) for k, v in eligible.groupby("country_iso3").size().items()}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.WARNING)
    counts = eligible_counts(Path(args[0]))
    print(counts, "total:", sum(counts.values()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
