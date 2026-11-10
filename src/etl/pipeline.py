"""ETL orchestration: extract (verified files) -> parse -> normalize -> load -> quality gates."""

from __future__ import annotations

import logging
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import Engine, text

from src.etl import db, load
from src.etl.eligibility import build_series_catalog
from src.etl.parsers import parse_faostat_zip, parse_wfp_csv
from src.etl.quality import QualityReport, run_post_load_checks
from src.etl.sources import SOURCES, RetrievedFile, fetch_all, md5_of
from src.etl.transform import normalize, resolve_duplicates

logger = logging.getLogger("agriprix.etl")


@contextmanager
def _stage(name: str) -> Iterator[None]:
    """Log the wall-clock duration of a pipeline stage."""
    start = time.perf_counter()
    yield
    logger.info("stage %-20s %6.1f s", name, time.perf_counter() - start)


@dataclass
class EtlSummary:
    etl_run_id: int
    rows_read: int
    facts: load.FactLoadStats
    rows_rejected: int
    series_total: int
    quality: QualityReport


def local_files(raw_dir: Path) -> list[RetrievedFile]:
    """Use files already present in raw_dir without contacting providers (--offline).

    Their MD5 is still computed and recorded, so the run stays traceable.
    """
    files = []
    for spec in SOURCES:
        path = raw_dir / spec.filename
        if not path.exists():
            raise FileNotFoundError(f"--offline: {path} is missing")
        data = path.read_bytes()
        files.append(
            RetrievedFile(spec, path, f"file://{path.name}", len(data), md5_of(data), None, True)
        )
    return files


def parse_all(files: list[RetrievedFile]) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    observations, rejects, rows_read = [], [], 0
    for f in files:
        if f.spec.kind == "hdx":
            result = parse_wfp_csv(f.path, f.spec.country_iso3, f.spec.name)
        else:
            kind = "cpi" if "Consumer" in f.spec.filename else "prices"
            result = parse_faostat_zip(f.path, kind, f.spec.name)
        logger.info(
            "%s: %d rows read, %d parsed, %d rejected",
            f.spec.name,
            result.rows_read,
            len(result.observations),
            len(result.rejects),
        )
        observations.append(result.observations)
        rejects.append(result.rejects)
        rows_read += result.rows_read
    with warnings.catch_warnings():
        # FAOSTAT frames have all-NA geographic columns (national grain); pandas warns that
        # a future version will keep their dtype. Our columns are object either way.
        warnings.filterwarnings("ignore", "The behavior of DataFrame concatenation", FutureWarning)
        obs = pd.concat([o for o in observations if not o.empty], ignore_index=True)
    # Monthly rows carry a month, annual FAOSTAT rows carry none: nullable integer type.
    obs["reference_month"] = obs["reference_month"].astype("Int64")
    non_empty_rejects = [r for r in rejects if not r.empty]
    all_rejects = (
        pd.concat(non_empty_rejects, ignore_index=True) if non_empty_rejects else rejects[0]
    )
    return obs, all_rejects, rows_read


def run_etl(
    engine: Engine,
    raw_dir: Path,
    *,
    git_sha: str = "dev-local",
    offline: bool = False,
    client: httpx.Client | None = None,
) -> EtlSummary:
    with engine.begin() as conn:
        db.apply_migrations(conn)
    with engine.begin() as conn:
        etl_run_id = conn.execute(
            text(
                "INSERT INTO etl_run_audit (status, git_sha) VALUES ('RUNNING', :sha)"
                " RETURNING etl_run_id"
            ),
            {"sha": git_sha},
        ).scalar_one()

    try:
        with _stage("extract"):
            files = local_files(raw_dir) if offline else fetch_all(raw_dir, client=client)
        with _stage("parse"):
            parsed, parse_rejects, rows_read = parse_all(files)
        with _stage("transform + catalog"):
            observations, duplicate_rejects = resolve_duplicates(normalize(parsed))
            rejects = pd.concat(
                [r for r in (parse_rejects, duplicate_rejects) if not r.empty] or [parse_rejects],
                ignore_index=True,
            )
            catalog = build_series_catalog(observations)

        with engine.begin() as conn:
            with _stage("load dimensions"):
                load.upsert_reference_data(conn)
                load.upsert_markets_and_commodities(conn, observations)
                series_ids = load.upsert_series(conn, catalog)
            with _stage("load facts"):
                facts = load.load_observations(conn, observations, series_ids, etl_run_id)
                load.load_rejects(conn, rejects, etl_run_id)
                load.record_source_files(conn, files, etl_run_id)
                load.refresh_country_max_dates(conn)
            with _stage("quality gates"):
                report = run_post_load_checks(conn, etl_run_id, rows_read, len(rejects))
            conn.execute(
                text(
                    "UPDATE etl_run_audit SET status = 'SUCCESS', finished_at = clock_timestamp(),"
                    " rows_read = :read, rows_upserted = :loaded, rows_rejected = :rejected,"
                    " ml_eligible_series = :eligible WHERE etl_run_id = :run"
                ),
                {
                    "read": rows_read,
                    "loaded": facts.upserted,
                    "rejected": len(rejects),
                    "eligible": report.eligible_series,
                    "run": etl_run_id,
                },
            )
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE etl_run_audit SET status = 'FAILED', finished_at = clock_timestamp(),"
                    " error_message = :msg WHERE etl_run_id = :run"
                ),
                {"msg": f"{type(exc).__name__}: {exc}"[:2000], "run": etl_run_id},
            )
        raise

    return EtlSummary(etl_run_id, rows_read, facts, len(rejects), len(catalog), report)
