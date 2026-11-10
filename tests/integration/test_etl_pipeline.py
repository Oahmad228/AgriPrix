"""End-to-end ETL in an isolated schema: loading, constraints, idempotence, failure path."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from src.config import get_settings
from src.etl.pipeline import run_etl
from src.etl.quality import DataQualityError

from tests.conftest import wfp_row, write_wfp_csv


def scalar(engine: Engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def fetch_all(engine: Engine, sql: str) -> list[tuple]:
    # Always close connections: an open read transaction would block DROP SCHEMA.
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql)).all()]


def test_full_pipeline_loads_expected_catalog(warehouse: Engine, raw_dir: Path) -> None:
    summary = run_etl(warehouse, raw_dir, offline=True, git_sha="test")

    assert summary.rows_rejected == 1  # the negative price
    assert summary.series_total == 12
    assert summary.quality.eligible_series == 2
    eligible = {
        row[0]
        for row in fetch_all(
            warehouse, "SELECT commodity_code FROM dim_series_catalog WHERE is_ml_eligible"
        )
    }
    assert eligible == {"WFP_73", "FAO_CPI_23013"}

    reasons = dict(
        fetch_all(
            warehouse,
            "SELECT commodity_code || '/' || price_type, ineligibility_reason"
            " FROM dim_series_catalog WHERE country_iso3 = 'SEN' AND NOT is_ml_eligible",
        )
    )
    assert reasons == {
        "WFP_73/Wholesale": "NOT_RETAIL_PRICE",
        "WFP_64/Retail": "STALE_LAST_OBSERVATION",
        "WFP_114/Retail": "NOT_IN_FOOD_BASKET",
    }
    # 100 KG wholesale prices are stored per KG, raw value kept for audit.
    row = fetch_all(
        warehouse,
        "SELECT f.raw_value, f.observed_value, f.raw_unit, s.unit_measure"
        " FROM fact_price_observation f JOIN dim_series_catalog s USING (series_id)"
        " WHERE s.price_type = 'Wholesale' ORDER BY f.calendar_id LIMIT 1",
    )[0]
    assert (float(row[0]), float(row[1]), row[2], row[3]) == (100.0, 1.0, "100 KG", "KG")

    audit = fetch_all(
        warehouse, "SELECT status, rows_rejected, ml_eligible_series FROM etl_run_audit"
    )
    assert audit == [("SUCCESS", 1, 2)]
    assert scalar(warehouse, "SELECT COUNT(*) FROM etl_source_file") == 7
    assert scalar(warehouse, "SELECT reason_code FROM audit_rejected_rows") == "NON_POSITIVE_PRICE"
    # Annual producer prices: stored with an annual calendar id, never a month.
    assert (
        scalar(
            warehouse,
            "SELECT COUNT(*) FROM fact_price_observation WHERE frequency = 'ANNUAL'"
            " AND calendar_id % 100 <> 0",
        )
        == 0
    )


def test_second_run_is_idempotent_and_keeps_series_ids(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    sql = "SELECT string_agg(series_id || ':' || series_natural_key, ',' ORDER BY series_id) FROM dim_series_catalog"
    before = scalar(warehouse, sql)
    observations = scalar(warehouse, "SELECT COUNT(*) FROM fact_price_observation")
    run_etl(warehouse, raw_dir, offline=True)
    assert scalar(warehouse, sql) == before
    assert scalar(warehouse, "SELECT COUNT(*) FROM fact_price_observation") == observations


def test_composite_foreign_key_forbids_monthly_series_on_annual_period(
    warehouse: Engine, raw_dir: Path
) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    with pytest.raises(IntegrityError, match="fk_obs_calendar_freq"), warehouse.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO fact_price_observation (series_id, calendar_id, frequency,"
                " observed_value, raw_value, raw_unit, source_flag, is_observed, etl_run_id)"
                " SELECT series_id, 202400, 'MONTHLY', 1, 1, 'KG', 'actual', TRUE, 1"
                " FROM dim_series_catalog WHERE frequency = 'MONTHLY' LIMIT 1"
            )
        )


def test_aggregate_rows_cannot_be_flagged_observed(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    with pytest.raises(IntegrityError, match="chk_obs_source_flag"), warehouse.begin() as conn:
        conn.execute(
            text(
                "UPDATE fact_price_observation SET source_flag = 'aggregate'"
                " WHERE observation_id = (SELECT MIN(observation_id) FROM fact_price_observation)"
            )
        )


def test_readonly_role_can_read_but_not_write(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    schema = scalar(warehouse, "SELECT current_schema()")
    readonly = create_engine(get_settings().readonly_database_url)
    try:
        with readonly.connect() as conn:
            conn.execute(text(f'SET search_path TO "{schema}"'))
            assert conn.execute(text("SELECT COUNT(*) FROM dim_series_catalog")).scalar_one() == 12
            with pytest.raises(ProgrammingError, match="permission denied"):
                conn.execute(text("DELETE FROM dim_series_catalog"))
    finally:
        readonly.dispose()


def test_failed_quality_gate_rolls_back_and_is_audited(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    loaded = scalar(warehouse, "SELECT COUNT(*) FROM fact_price_observation")
    # Corrupt a source: 30 % of SEN rows now have negative prices (DQ-04 > 1 %).
    rows = [wfp_row(2024, m, price=-1) for m in range(1, 13)] + [
        wfp_row(2025, m) for m in range(1, 13)
    ]
    write_wfp_csv(raw_dir / "wfp_SEN.csv", rows)
    with pytest.raises(DataQualityError, match="DQ-04"):
        run_etl(warehouse, raw_dir, offline=True)
    assert scalar(warehouse, "SELECT COUNT(*) FROM fact_price_observation") == loaded
    last = fetch_all(
        warehouse,
        "SELECT status, error_message FROM etl_run_audit ORDER BY etl_run_id DESC LIMIT 1",
    )[0]
    assert last[0] == "FAILED"
    assert "DQ-04" in last[1]


def test_cli_offline_run_prints_traceable_summary(
    warehouse: Engine, raw_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from src.etl import cli, db

    monkeypatch.setattr(db, "make_writer_engine", lambda: warehouse)
    assert cli.main(["--offline", "--raw-dir", str(raw_dir)]) == 0
    out = capsys.readouterr().out
    assert "ETL run 1:" in out
    assert "12 series, 2 ML-eligible" in out


def test_incremental_load_only_touches_changed_rows(warehouse: Engine, raw_dir: Path) -> None:
    first = run_etl(warehouse, raw_dir, offline=True)
    assert first.facts.inserted == first.facts.staged
    assert (first.facts.updated, first.facts.deleted) == (0, 0)

    unchanged = run_etl(warehouse, raw_dir, offline=True)
    assert (unchanged.facts.inserted, unchanged.facts.updated, unchanged.facts.deleted) == (0, 0, 0)

    # HDX revises one price, drops one month and publishes a new month.
    path = raw_dir / "wfp_MLI.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header, rows = lines[0], lines[1:]
    rows[0] = rows[0].replace(",100,", ",150,")  # first row: price 100 -> 150
    rows.pop(5)  # one month disappears
    rows.append(rows[-1].replace("2024-12-15", "2025-01-15"))  # one new month
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

    revised = run_etl(warehouse, raw_dir, offline=True)
    assert (revised.facts.inserted, revised.facts.updated, revised.facts.deleted) == (1, 1, 1)
    assert (
        scalar(
            warehouse,
            "SELECT f.raw_value FROM fact_price_observation f JOIN dim_series_catalog s"
            " USING (series_id) WHERE s.country_iso3 = 'MLI' AND f.calendar_id = 202401",
        )
        == 150
    )
