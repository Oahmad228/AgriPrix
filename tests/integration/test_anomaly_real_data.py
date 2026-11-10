"""KPI-M4 on the REAL warehouse (local runs only; skipped where the warehouse is empty, e.g. CI).

The catalog, thresholds and detection criterion were fixed a priori (commit d7bfac9). If this
test fails, the detector misses its objective: report it, never tune the catalog to pass.
"""

import pytest
from sqlalchemy import text
from src.anomaly.catalog import MAX_CALM_ALERT_RATE, MIN_EPISODE_RECALL
from src.anomaly.detector import load_scope, robust_scores
from src.anomaly.validation import validate
from src.etl.db import make_writer_engine


@pytest.fixture(scope="module")
def real_scope():
    engine = make_writer_engine()
    try:
        with engine.connect() as conn:
            has_data = (
                conn.execute(
                    text("SELECT to_regclass('public.fact_price_observation') IS NOT NULL")
                ).scalar_one()
                and conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM public.fact_price_observation)")
                ).scalar_one()
            )
            if not has_data:
                pytest.skip("real warehouse not loaded (run `make etl` locally)")
            yield load_scope(conn)
    finally:
        engine.dispose()


def test_kpi_m4_on_reference_shocks(real_scope) -> None:
    meta, prices = real_scope
    result = validate(robust_scores(prices)["z"], meta)
    assert result.recall >= MIN_EPISODE_RECALL, result.episodes
    assert result.calm_rate <= MAX_CALM_ALERT_RATE, result.calm_by_country
