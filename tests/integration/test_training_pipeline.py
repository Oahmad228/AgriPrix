"""End-to-end training campaign on the synthetic warehouse (no MLflow server needed)."""

from pathlib import Path

from sqlalchemy import Engine, text
from src.etl.pipeline import run_etl
from src.ml.train import run_training


def rows(engine: Engine, sql: str) -> list[tuple]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql)).all()]


def test_training_campaign_writes_versioned_results(warehouse: Engine, raw_dir: Path) -> None:
    run_etl(warehouse, raw_dir, offline=True)
    run_id = run_training(warehouse, git_sha="test", use_mlflow=False)

    assert rows(warehouse, "SELECT status, is_production_active, etl_run_id FROM training_run") == [
        ("SUCCESS", True, 1)
    ]
    # 2 eligible series (SEN millet, MAR food CPI) x 3 horizons, one forecast each.
    forecasts = rows(
        warehouse,
        "SELECT s.commodity_code, f.horizon_months, f.origin_calendar_id, f.target_calendar_id,"
        " f.yhat_lower_80 <= f.yhat_upper_80"
        " FROM fact_forecast f JOIN dim_series_catalog s USING (series_id)"
        " ORDER BY 1, 2",
    )
    assert [(c, h) for c, h, *_ in forecasts] == [
        ("FAO_CPI_23013", 1), ("FAO_CPI_23013", 3), ("FAO_CPI_23013", 6),
        ("WFP_73", 1), ("WFP_73", 3), ("WFP_73", 6),
    ]  # fmt: skip
    millet = {h: (origin, target) for code, h, origin, target, _ in forecasts if code == "WFP_73"}
    assert millet == {1: (202609, 202610), 3: (202609, 202612), 6: (202609, 202703)}
    assert all(ordered for *_, ordered in forecasts)

    champions = rows(
        warehouse, "SELECT COUNT(*), COUNT(DISTINCT selection_rule) > 0 FROM fact_champion_model"
    )
    assert champions == [(6, True)]  # 2 groups x 3 horizons
    windows = {
        w
        for (w,) in rows(warehouse, "SELECT DISTINCT eval_window FROM fact_model_metrics_by_series")
    }
    assert windows == {"CAL_W0_2021", "VAL_W1_2022", "VAL_W2_24_25", "TEST_W3_25_26"}
    # Intervals are calibrated for W1 and W3 (+ production) only, never on their own errors.
    calibrations = set(
        rows(
            warehouse,
            "SELECT DISTINCT eval_window, calibration_window FROM fact_conformal_quantiles",
        )
    )
    assert calibrations == {
        ("VAL_W1_2022", "CAL_W0_2021"),
        ("TEST_W3_25_26", "VAL_W2_24_25"),
        ("PROD_FINAL", "TEST_W3_25_26"),
    }
    picp = rows(
        warehouse,
        "SELECT COUNT(*) FILTER (WHERE picp_80 IS NOT NULL) FROM fact_model_metrics_by_series"
        " WHERE eval_window IN ('VAL_W2_24_25', 'CAL_W0_2021')",
    )
    assert picp == [(0,)]

    second = run_training(warehouse, git_sha="test", use_mlflow=False)
    assert second == run_id + 1
    active = rows(warehouse, "SELECT run_id FROM training_run WHERE is_production_active")
    assert active == [(second,)]


def test_cli_and_mlflow_tracking(
    warehouse: Engine, raw_dir: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    """The CLI runs the campaign and logs 1 parent + (groups x models) child runs."""
    import mlflow
    from src.etl import db
    from src.ml import cli, tracking

    run_etl(warehouse, raw_dir, offline=True)
    store = f"file:{tmp_path / 'mlruns'}"
    monkeypatch.setattr(db, "make_writer_engine", lambda: warehouse)
    monkeypatch.setattr(
        tracking, "get_settings", lambda: type("S", (), {"mlflow_tracking_uri": store})()
    )
    assert cli.main([]) == 0
    assert "Training run 1 finished" in capsys.readouterr().out

    client = mlflow.tracking.MlflowClient(tracking_uri=store)
    experiment = client.get_experiment_by_name(tracking.EXPERIMENT)
    runs = client.search_runs([experiment.experiment_id])
    parents = [r for r in runs if "mlflow.parentRunId" not in r.data.tags]
    children = [r for r in runs if "mlflow.parentRunId" in r.data.tags]
    assert len(parents) == 1
    assert len(children) == 2 * 4  # 2 groups x 4 model families
    assert parents[0].data.tags["training_run_id"] == "1"
    assert any(k.startswith("TEST_W3_25_26_h6") for k in children[0].data.metrics)
    parent_id = rows(warehouse, "SELECT mlflow_parent_run_id FROM training_run")[0][0]
    assert parent_id == parents[0].info.run_id


def test_generated_reports_only_contain_computed_figures(
    warehouse: Engine, raw_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    from src.eda import report as eda
    from src.ml import report as ml_report

    run_etl(warehouse, raw_dir, offline=True)
    run_training(warehouse, use_mlflow=False)
    monkeypatch.setattr(eda, "OUT_DIR", tmp_path)

    with warehouse.connect() as conn:
        obs, meta = eda.load(conn)
        run, metrics, champions = ml_report.load_run(conn)
    eda_md = eda.render(obs, meta)
    assert "**2 séries éligibles**" in eda_md
    assert "etl_run_id = 1" in eda_md
    assert {p.name for p in tmp_path.glob("*.png")} == {
        "01-segments-continus.png",
        "02-saisonnalite-cereales.png",
        "03-variation-annuelle.png",
    }
    ml_md = ml_report.render(run, metrics, champions)
    assert "training_run.run_id = 1" in ml_md
    assert "| 6 mois | 2 |" in ml_md  # W3, 2 series at 6 months
    assert "ADR-010" in ml_md
