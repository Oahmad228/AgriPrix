"""Training campaign: rolling-origin backtest, conformal calibration, champions, forecasts."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from src.etl import db
from src.ml import tracking
from src.ml.data import Panel, calendar_id_of, load_panel
from src.ml.evaluation import apply_interval, conformal_quantiles, select_champion
from src.ml.features import build_supervised, seasonal_scale
from src.ml.models import BASELINES, MODEL_NAMES, make_model
from src.ml.windows import (
    HISTORY_CAP_MONTHS,
    HORIZONS,
    MIN_TRAIN_OBSERVATIONS,
    SELECTION_WINDOWS,
    TEST_W3,
    WINDOWS,
)

logger = logging.getLogger("agriprix.ml")
PROD_WINDOW = "PROD_FINAL"
GROUP_KEYS = ["country_iso3", "commodity_group"]


@contextmanager
def _stage(name: str) -> Iterator[None]:
    start = time.perf_counter()
    yield
    logger.info("stage %-22s %7.1f s", name, time.perf_counter() - start)


@dataclass
class TrainingResult:
    predictions: pd.DataFrame  # backtest predictions, all windows/models
    metrics: pd.DataFrame  # one row per (series, model, horizon, window)
    quantiles: pd.DataFrame
    champions: pd.DataFrame
    forecasts: pd.DataFrame  # production forecasts of the champions
    report: dict[str, float] = field(default_factory=dict)


def _train_rows(data: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    """Pairs whose target month is <= T (no buffer leakage), last 10 years only."""
    mask = (
        data["target"].notna()
        & (data["target_month_idx"] <= cutoff)
        & (data["target_month_idx"] > cutoff - HISTORY_CAP_MONTHS)
    )
    return data[mask]


def _testable_series(panel: Panel, cutoff: int) -> set[int]:
    before = panel.values[panel.values["month_idx"] <= cutoff]
    counts = before.groupby("series_id").size()
    return set(counts[counts >= MIN_TRAIN_OBSERVATIONS].index)


SupervisedCache = dict[tuple[str, str, int], pd.DataFrame]


def backtest(panel: Panel) -> tuple[pd.DataFrame, SupervisedCache]:
    """Predictions of every model, horizon and window, with the model frozen at T.

    Also returns the supervised frames, reused for the production forecasts.
    """
    frames, cache = [], {}
    testable = {w.name: _testable_series(panel, w.cutoff) for w in WINDOWS}
    for (country, group), meta in panel.series.groupby(GROUP_KEYS):
        ids = meta["series_id"].tolist()
        lean = meta["lean_season_months"].iloc[0]
        for horizon in HORIZONS:
            data = build_supervised(panel, ids, horizon, lean)
            cache[(country, group, horizon)] = data
            for window in WINDOWS:
                train = _train_rows(data, window.cutoff)
                evaluate = data[
                    data["target"].notna()
                    & data["target_month_idx"].isin(window.eval_months)
                    & data["series_id"].isin(testable[window.name])
                ]
                if train.empty or evaluate.empty:
                    continue
                base = evaluate[
                    ["series_id", "month_idx", "target_month_idx", "actual_value", "snaive_value"]
                ].assign(
                    horizon_months=horizon,
                    eval_window=window.name,
                    country_iso3=country,
                    commodity_group=group,
                )
                for name in MODEL_NAMES:
                    model = make_model(name).fit(train)
                    frames.append(base.assign(prediction=model.predict(evaluate), model_name=name))
        logger.info("backtest done for %s/%s (%d series)", country, group, len(ids))
    return pd.concat(frames, ignore_index=True), cache


QUANTILE_KEYS = [*GROUP_KEYS, "model_name", "horizon_months"]


def _quantile_table(residual_rows: pd.DataFrame) -> pd.DataFrame:
    """Conformal quantiles of relative errors per (country, group, model, horizon)."""
    rel = (residual_rows["actual_value"] - residual_rows["prediction"]) / residual_rows[
        "prediction"
    ]
    rows = []
    for key, errors in rel.groupby([residual_rows[k] for k in QUANTILE_KEYS]):
        q_low, q_high = conformal_quantiles(errors.to_numpy())
        rows.append(
            dict(zip(QUANTILE_KEYS, key, strict=True))
            | {"n_calibration_residuals": len(errors), "q_rel_10": q_low, "q_rel_90": q_high}
        )
    return pd.DataFrame(rows)


def calibrate(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach 80 % intervals to windows that have a calibration window (W1, W3).

    Quantiles are computed per (country, group, model, horizon) on the relative errors of
    the calibration window and applied, unchanged, to the evaluated window.
    """
    tables = []
    for window in [w for w in WINDOWS if w.calibrated_by]:
        table = _quantile_table(predictions[predictions["eval_window"] == window.calibrated_by])
        tables.append(
            table.assign(eval_window=window.name, calibration_window=window.calibrated_by)
        )
    quantiles = pd.concat(tables, ignore_index=True)
    merged = predictions.merge(
        quantiles[[*QUANTILE_KEYS, "eval_window", "q_rel_10", "q_rel_90"]],
        on=[*QUANTILE_KEYS, "eval_window"],
        how="left",
    )
    lower, upper = apply_interval(
        merged["prediction"].to_numpy(),
        merged["q_rel_10"].to_numpy(),
        merged["q_rel_90"].to_numpy(),
    )
    merged["lower_80"], merged["upper_80"] = lower, upper  # NaN where no calibration
    return merged.drop(columns=["q_rel_10", "q_rel_90"]), quantiles


def compute_metrics(panel: Panel, predictions: pd.DataFrame) -> pd.DataFrame:
    """Per (series, model, horizon, window) metrics, vectorized (see series_metrics)."""
    p = predictions
    error = p["actual_value"] - p["prediction"]
    inside = (p["actual_value"] >= p["lower_80"]) & (p["actual_value"] <= p["upper_80"])
    work = pd.DataFrame(
        {
            "abs_err": error.abs(),
            "sq_err": error**2,
            "ape": error.abs() / p["actual_value"] * 100,
            "sn_abs": (p["actual_value"] - p["snaive_value"]).abs(),
            "inside": inside.astype(float).where(p["lower_80"].notna()),
        }
    )
    keys = ["series_id", "model_name", "horizon_months", "eval_window", *GROUP_KEYS]
    agg = work.groupby([p[k] for k in keys]).agg(
        n_eval_points=("abs_err", "size"),
        mae=("abs_err", "mean"),
        mse=("sq_err", "mean"),
        mape=("ape", "mean"),
        sn_mae=("sn_abs", "mean"),
        picp_80=("inside", "mean"),
    )
    agg = agg.reset_index()
    agg["rmse"] = np.sqrt(agg.pop("mse"))
    sn_mae = agg.pop("sn_mae")
    agg["rel_mae"] = (agg["mae"] / sn_mae).where(sn_mae > 0)

    cutoffs = {w.name: w.cutoff for w in WINDOWS}
    scales = []
    for window_name, ids in agg.groupby("eval_window")["series_id"]:
        scale = seasonal_scale(panel, ids.unique().tolist(), cutoffs[window_name])
        scales.append(
            pd.DataFrame(
                {"eval_window": window_name, "series_id": scale.index, "scale": scale.values}
            )
        )
    agg = agg.merge(pd.concat(scales), on=["eval_window", "series_id"], how="left")
    agg["mase"] = (agg["mae"] / agg.pop("scale")).where(lambda v: np.isfinite(v))
    return agg


def choose_champions(metrics: pd.DataFrame) -> pd.DataFrame:
    selection = metrics[metrics["eval_window"].isin(SELECTION_WINDOWS)]
    rows = []
    for (country, group, horizon), block in selection.groupby([*GROUP_KEYS, "horizon_months"]):
        name, rel_mae, mase, rule = select_champion(block)
        rows.append(
            {
                "country_iso3": country,
                "commodity_group": group,
                "horizon_months": horizon,
                "champion_model_name": name,
                "median_rel_mae_val": rel_mae,
                "median_mase_val": mase,
                "selection_rule": rule,
            }
        )
    return pd.DataFrame(rows)


def production_forecasts(
    panel: Panel, champions: pd.DataFrame, predictions: pd.DataFrame, cache: SupervisedCache
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Refit each champion on all data and forecast h months after each series' last month.

    Intervals use quantiles calibrated on the champion's TEST_W3 errors (most recent regime).
    """
    cutoff = panel.last_month
    last_obs = panel.values.groupby("series_id")["month_idx"].max()
    forecasts, quantile_rows = [], []
    champion_of = champions.set_index([*GROUP_KEYS, "horizon_months"])["champion_model_name"]
    for (country, group), _meta in panel.series.groupby(GROUP_KEYS):
        for horizon in HORIZONS:
            name = champion_of.get((country, group, horizon), "Naive")
            data = cache[(country, group, horizon)]
            model = make_model(name).fit(_train_rows(data, cutoff))
            origins = data[data["month_idx"] == data["series_id"].map(last_obs)]
            point = model.predict(origins)

            calib = predictions[
                (predictions["eval_window"] == TEST_W3.name)
                & (predictions["country_iso3"] == country)
                & (predictions["commodity_group"] == group)
                & (predictions["model_name"] == name)
                & (predictions["horizon_months"] == horizon)
            ]
            errors = (
                (calib["actual_value"] - calib["prediction"]) / calib["prediction"]
            ).to_numpy()
            q_low, q_high = conformal_quantiles(errors)
            lower, upper = apply_interval(point, q_low, q_high)
            quantile_rows.append(
                {
                    "country_iso3": country,
                    "commodity_group": group,
                    "model_name": name,
                    "horizon_months": horizon,
                    "eval_window": PROD_WINDOW,
                    "calibration_window": TEST_W3.name,
                    "n_calibration_residuals": len(errors),
                    "q_rel_10": q_low,
                    "q_rel_90": q_high,
                }
            )
            forecasts.append(
                pd.DataFrame(
                    {
                        "series_id": origins["series_id"].to_numpy(),
                        "origin_calendar_id": [
                            calendar_id_of(int(m)) for m in origins["month_idx"]
                        ],
                        "target_calendar_id": [
                            calendar_id_of(int(m) + horizon) for m in origins["month_idx"]
                        ],
                        "horizon_months": horizon,
                        "yhat_point": point,
                        "yhat_lower_80": lower,
                        "yhat_upper_80": upper,
                        "champion_model_name": name,
                        "country_iso3": country,
                        "commodity_group": group,
                    }
                )
            )
    return pd.concat(forecasts, ignore_index=True), pd.DataFrame(quantile_rows)


def headline_report(metrics: pd.DataFrame, champions: pd.DataFrame) -> dict[str, float]:
    """W3 (final test) and W1 (2022 shock) figures of the champions, per horizon.

    skill_vs_X = 1 - total absolute error of the champions / total absolute error of
    baseline X on the same points (KPI-M2). Both the seasonal naive (KPI-M2 as written)
    and the stricter persistence benchmark (Naive) are reported.
    """
    champ = metrics.merge(
        champions[[*GROUP_KEYS, "horizon_months", "champion_model_name"]],
        left_on=[*GROUP_KEYS, "horizon_months", "model_name"],
        right_on=[*GROUP_KEYS, "horizon_months", "champion_model_name"],
    )
    report: dict[str, float] = {}
    for window in ("TEST_W3_25_26", "VAL_W1_2022"):
        tag = "W3" if window.startswith("TEST") else "W1"
        for horizon in HORIZONS:
            in_scope = (metrics["eval_window"] == window) & (metrics["horizon_months"] == horizon)
            c = champ[(champ["eval_window"] == window) & (champ["horizon_months"] == horizon)]
            if c.empty:
                continue
            total = lambda frame: float((frame["mae"] * frame["n_eval_points"]).sum())  # noqa: E731
            covered = c[c["picp_80"].notna()]
            report[f"{tag}_h{horizon}_series"] = float(len(c))
            report[f"{tag}_h{horizon}_points"] = float(c["n_eval_points"].sum())
            report[f"{tag}_h{horizon}_median_mase"] = float(c["mase"].median())
            report[f"{tag}_h{horizon}_median_rel_mae"] = float(c["rel_mae"].median())
            report[f"{tag}_h{horizon}_mape"] = float(
                np.average(c["mape"], weights=c["n_eval_points"])
            )
            if not covered.empty:
                report[f"{tag}_h{horizon}_picp_80"] = float(
                    np.average(covered["picp_80"], weights=covered["n_eval_points"])
                )
            for baseline in BASELINES:
                b = metrics[in_scope & (metrics["model_name"] == baseline)]
                report[f"{tag}_h{horizon}_skill_vs_{baseline}"] = 1 - total(c) / total(b)
    return report


def run_training(engine: Engine, *, git_sha: str = "dev-local", use_mlflow: bool = True) -> int:
    """Run a full campaign and make it the production run; return its run_id."""
    with engine.begin() as conn:
        db.apply_migrations(conn)
        etl_run = conn.execute(
            text("SELECT MAX(etl_run_id) FROM etl_run_audit WHERE status = 'SUCCESS'")
        ).scalar_one()
        run_id = conn.execute(
            text(
                "INSERT INTO training_run (status, etl_run_id, git_sha) VALUES ('RUNNING', :etl, :sha)"
                " RETURNING run_id"
            ),
            {"etl": etl_run, "sha": git_sha},
        ).scalar_one()
    try:
        with engine.connect() as conn, _stage("load panel"):
            panel = load_panel(conn)
        if panel.series.empty:
            raise RuntimeError("no ML-eligible series in the warehouse: run the ETL first")
        with _stage("backtest (4 windows)"):
            predictions, cache = backtest(panel)
        with _stage("conformal + metrics"):
            predictions, quantiles = calibrate(predictions)
            metrics = compute_metrics(panel, predictions)
            champions = choose_champions(metrics)
        with _stage("production forecasts"):
            forecasts, prod_quantiles = production_forecasts(panel, champions, predictions, cache)
        result = TrainingResult(
            predictions,
            metrics,
            pd.concat([quantiles, prod_quantiles], ignore_index=True),
            champions,
            forecasts,
            headline_report(metrics, champions),
        )
        with _stage("mlflow tracking"):
            run_ids = (
                tracking.log_campaign(run_id, git_sha, panel, result)
                if use_mlflow
                else tracking.NO_MLFLOW
            )
        with _stage("write warehouse"):
            _write(engine, run_id, panel, result, run_ids)
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE training_run SET status = 'FAILED', finished_at = clock_timestamp(),"
                    " error_message = :msg WHERE run_id = :run"
                ),
                {"msg": f"{type(exc).__name__}: {exc}"[:2000], "run": run_id},
            )
        raise
    for key, value in sorted(result.report.items()):
        logger.info("report %-28s %.4f", key, value)
    return run_id


def _write(engine: Engine, run_id: int, panel: Panel, result: TrainingResult, run_ids) -> None:
    group_run = run_ids.group_runs
    with engine.begin() as conn:
        metric_cols = [
            "series_id", "model_name", "horizon_months", "eval_window", "n_eval_points",
            "mae", "rmse", "mape", "mase", "rel_mae", "picp_80",
        ]  # fmt: skip
        m = result.metrics
        db.copy_rows(
            conn,
            "fact_model_metrics_by_series",
            ["run_id", *metric_cols, "mlflow_group_run_id"],
            (
                (run_id, *(_sql(r[c]) for c in metric_cols),
                 group_run.get((r["country_iso3"], r["commodity_group"], r["model_name"])))
                for r in m.to_dict("records")
            ),
        )  # fmt: skip
        q_cols = [
            "country_iso3", "commodity_group", "model_name", "horizon_months", "eval_window",
            "calibration_window", "n_calibration_residuals", "q_rel_10", "q_rel_90",
        ]  # fmt: skip
        db.copy_rows(
            conn,
            "fact_conformal_quantiles",
            ["run_id", *q_cols],
            ((run_id, *(_sql(r[c]) for c in q_cols)) for r in result.quantiles.to_dict("records")),
        )
        c_cols = [
            "country_iso3", "commodity_group", "horizon_months", "champion_model_name",
            "median_rel_mae_val", "median_mase_val", "selection_rule",
        ]  # fmt: skip
        db.copy_rows(
            conn,
            "fact_champion_model",
            ["run_id", *c_cols],
            ((run_id, *(_sql(r[c]) for c in c_cols)) for r in result.champions.to_dict("records")),
        )
        f_cols = [
            "series_id", "origin_calendar_id", "target_calendar_id", "horizon_months",
            "yhat_point", "yhat_lower_80", "yhat_upper_80", "champion_model_name",
        ]  # fmt: skip
        db.copy_rows(
            conn,
            "fact_forecast",
            ["run_id", *f_cols, "mlflow_group_run_id"],
            (
                (run_id, *(_sql(r[c]) for c in f_cols),
                 group_run.get((r["country_iso3"], r["commodity_group"], r["champion_model_name"])))
                for r in result.forecasts.to_dict("records")
            ),
        )  # fmt: skip
        conn.execute(
            text("UPDATE training_run SET is_production_active = FALSE WHERE is_production_active")
        )
        conn.execute(
            text(
                "UPDATE training_run SET status = 'SUCCESS', finished_at = clock_timestamp(),"
                " is_production_active = TRUE, mlflow_parent_run_id = :parent,"
                " max_data_date = make_date(:y, :m, 1) WHERE run_id = :run"
            ),
            {
                "parent": run_ids.parent_run_id,
                "y": panel.last_month // 12,
                "m": panel.last_month % 12 + 1,
                "run": run_id,
            },
        )


def _sql(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value
