"""Retention keeps the active and recent campaigns, and only the run row of older ones."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from src.etl.pipeline import run_etl
from src.ml.train import run_training
from src.ops.retention import RUN_TABLES, prune_old_campaigns


def counts(engine: Engine) -> dict[int, int]:
    union = " UNION ALL ".join(f"SELECT run_id FROM {table}" for table in RUN_TABLES)
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT run_id, COUNT(*) FROM ({union}) t GROUP BY run_id"))
        return dict(rows.all())


def test_prune_keeps_recent_and_active_campaigns(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    runs = [run_training(warehouse, git_sha="test", use_mlflow=False) for _ in range(3)]
    assert set(counts(warehouse)) == set(runs)

    assert prune_old_campaigns(warehouse, keep=2) == [runs[0]]
    assert set(counts(warehouse)) == {runs[1], runs[2]}
    with warehouse.connect() as conn:
        kept_runs = conn.execute(text("SELECT COUNT(*) FROM training_run")).scalar_one()
    assert kept_runs == 3  # the audit trail of the pruned campaign stays
    assert prune_old_campaigns(warehouse, keep=2) == []  # idempotent

    # The production campaign survives even when it is not among the most recent.
    with warehouse.begin() as conn:
        conn.execute(text("UPDATE training_run SET is_production_active = FALSE"))
        conn.execute(
            text("UPDATE training_run SET is_production_active = TRUE WHERE run_id = :r"),
            {"r": runs[1]},
        )
    assert prune_old_campaigns(warehouse, keep=1) == []
    assert set(counts(warehouse)) == {runs[1], runs[2]}


def test_prune_rejects_keep_zero(warehouse: Engine) -> None:
    with pytest.raises(ValueError):
        prune_old_campaigns(warehouse, keep=0)
