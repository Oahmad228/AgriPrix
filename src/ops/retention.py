"""Retention of training campaigns (ADR-013): keep the database small on a free hosted plan.

Each campaign writes about 37 000 metrics and 23 000 alerts. Without a rule, a managed
database with a 0.5 GB quota fills up after a few months. We keep the analytical rows of
the active campaign and of the most recent ones; older campaigns keep only their
``training_run`` row (date, status, git sha, MLflow id), so the history stays auditable.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

logger = logging.getLogger("agriprix.ops")

# Every table whose rows belong to a training_run (V002, V003).
RUN_TABLES = (
    "fact_model_metrics_by_series",
    "fact_conformal_quantiles",
    "fact_champion_model",
    "fact_forecast",
    "fact_anomaly",
)


def prune_old_campaigns(engine: Engine, keep: int = 2) -> list[int]:
    """Delete analytical rows of campaigns older than the ``keep`` most recent ones.

    The production campaign is never pruned, even if it is not among the most recent.
    Returns the pruned run ids (those that still had rows).
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")
    with engine.begin() as conn:
        stale = [
            run_id
            for (run_id,) in conn.execute(
                text(
                    "SELECT run_id FROM training_run"
                    " WHERE NOT is_production_active AND status <> 'RUNNING'"
                    " AND run_id NOT IN (SELECT run_id FROM training_run"
                    "  WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT :keep)"
                    " ORDER BY run_id"
                ),
                {"keep": keep},
            )
        ]
        pruned = []
        for run_id in stale:
            deleted = sum(
                conn.execute(
                    text(f"DELETE FROM {table} WHERE run_id = :run_id"), {"run_id": run_id}
                ).rowcount
                for table in RUN_TABLES
            )
            if deleted:
                pruned.append(run_id)
                logger.info("Campaign %s pruned: %d analytical rows deleted", run_id, deleted)
    return pruned
