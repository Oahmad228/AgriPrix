"""Post-load data quality gates (DQ-04 rate, DQ-05, DQ-06, DQ-07), checked in SQL."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import Connection, text

logger = logging.getLogger("agriprix.etl.quality")

MAX_REJECT_RATE = 0.01  # DQ-04: more than 1 % rejected rows means the source changed shape
MAX_ELIGIBLE_DROP = 0.05  # DQ-07: alert when eligible series drop by more than 5 %


class DataQualityError(RuntimeError):
    """A blocking quality gate failed: the whole load is rolled back."""


@dataclass
class QualityReport:
    reject_rate: float
    eligible_series: int
    previous_eligible_series: int | None
    warnings: list[str] = field(default_factory=list)


def check_reject_rate(rows_read: int, rows_rejected: int) -> float:
    rate = rows_rejected / rows_read if rows_read else 1.0
    if rate >= MAX_REJECT_RATE:
        raise DataQualityError(
            f"DQ-04: {rows_rejected}/{rows_read} rows rejected ({rate:.2%} >= {MAX_REJECT_RATE:.0%})"
        )
    return rate


def run_post_load_checks(
    conn: Connection, etl_run_id: int, rows_read: int, rows_rejected: int
) -> QualityReport:
    rate = check_reject_rate(rows_read, rows_rejected)

    duplicates = conn.execute(
        text(
            "SELECT COUNT(*) FROM (SELECT series_id, calendar_id, source_flag"
            " FROM fact_price_observation GROUP BY 1, 2, 3 HAVING COUNT(*) > 1) d"
        )
    ).scalar_one()
    if duplicates:
        raise DataQualityError(f"DQ-05: {duplicates} duplicated observations")

    bad_eligible = conn.execute(
        text(
            "SELECT COUNT(*) FROM dim_series_catalog s WHERE s.is_ml_eligible AND ("
            " s.frequency <> 'MONTHLY' OR NOT EXISTS (SELECT 1 FROM fact_price_observation f"
            "  WHERE f.series_id = s.series_id AND f.is_observed))"
        )
    ).scalar_one()
    if bad_eligible:
        raise DataQualityError(f"DQ-06: {bad_eligible} eligible series are annual or unobserved")

    eligible = conn.execute(
        text("SELECT COUNT(*) FROM dim_series_catalog WHERE is_ml_eligible")
    ).scalar_one()
    previous = conn.execute(
        text(
            "SELECT ml_eligible_series FROM etl_run_audit WHERE status = 'SUCCESS'"
            " AND etl_run_id <> :run ORDER BY etl_run_id DESC LIMIT 1"
        ),
        {"run": etl_run_id},
    ).scalar_one_or_none()
    report = QualityReport(rate, eligible, previous)
    if previous and eligible < previous * (1 - MAX_ELIGIBLE_DROP):
        message = f"DQ-07: eligible series dropped from {previous} to {eligible}"
        logger.warning(message)
        report.warnings.append(message)
    return report
