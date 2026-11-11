"""Monthly refresh decisions and scheduler timing."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from src.ops.refresh import run_refresh
from src.ops.scheduler import next_run


@dataclass
class _Facts:
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


@dataclass
class _Summary:
    etl_run_id: int
    facts: _Facts


def _fakes(facts: _Facts):
    calls = {"train": 0}

    def etl(engine, raw_dir, git_sha):
        return _Summary(7, facts)

    def train(engine, git_sha, use_mlflow):
        calls["train"] += 1
        return 42

    return etl, train, calls


def test_training_skipped_when_no_source_data_changed() -> None:
    etl, train, calls = _fakes(_Facts())
    outcome = run_refresh(None, etl=etl, train=train)
    assert (outcome.etl_run_id, outcome.data_changed, outcome.training_run_id) == (7, False, None)
    assert calls["train"] == 0


@pytest.mark.parametrize("facts", [_Facts(inserted=12), _Facts(updated=1), _Facts(deleted=3)])
def test_any_change_triggers_training(facts: _Facts) -> None:
    etl, train, calls = _fakes(facts)
    assert run_refresh(None, etl=etl, train=train).training_run_id == 42
    assert calls["train"] == 1


def test_force_train_without_changes() -> None:
    etl, train, calls = _fakes(_Facts())
    assert run_refresh(None, force_train=True, etl=etl, train=train).training_run_id == 42


def at(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(2026, 11, 11, 10), at(2026, 11, 20, 3)),  # later this month
        (at(2026, 11, 20, 3), at(2026, 12, 20, 3)),  # exactly on the slot -> next month
        (at(2026, 12, 25, 0), at(2027, 1, 20, 3)),  # year rollover
    ],
)
def test_next_run(now: datetime, expected: datetime) -> None:
    assert next_run(now, day=20, hour=3) == expected


def test_day_is_clamped_to_exist_in_february() -> None:
    assert next_run(at(2027, 1, 30, 12), day=31, hour=3) == at(2027, 2, 28, 3)
