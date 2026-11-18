"""Error metrics, split-conformal intervals and champion selection (ADR-003, ADR-004)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

ALPHA = 0.20  # 80 % prediction intervals


def series_metrics(group: pd.DataFrame, scale: float | None) -> dict[str, float]:
    """Metrics of one (series, model, horizon, window) on price levels."""
    error = group["actual_value"] - group["prediction"]
    mae = float(error.abs().mean())
    snaive_mae = float((group["actual_value"] - group["snaive_value"]).abs().mean())
    metrics = {
        "n_eval_points": len(group),
        "mae": mae,
        "rmse": float(math.sqrt((error**2).mean())),
        "mape": float((error.abs() / group["actual_value"]).mean() * 100),
        "mase": mae / scale if scale and scale > 0 else np.nan,
        "rel_mae": mae / snaive_mae if snaive_mae > 0 else np.nan,
    }
    if "lower_80" in group and group["lower_80"].notna().all():
        inside = (group["actual_value"] >= group["lower_80"]) & (
            group["actual_value"] <= group["upper_80"]
        )
        metrics["picp_80"] = float(inside.mean())
    else:
        metrics["picp_80"] = np.nan
    return metrics


def conformal_quantiles(relative_errors: np.ndarray, alpha: float = ALPHA) -> tuple[float, float]:
    """Split-conformal bounds on relative errors e = (y - yhat) / yhat.

    Finite-sample correction: with n calibration errors the upper bound is the
    ceil((n + 1)(1 - alpha/2))-th smallest error and the lower bound the
    floor((n + 1) alpha/2)-th, which guarantees >= 1 - alpha coverage when future
    errors are exchangeable with the calibration errors.
    """
    errors = np.sort(np.asarray(relative_errors, dtype=float))
    n = len(errors)
    if n == 0:
        raise ValueError("no calibration residuals")
    upper_rank = min(n, math.ceil((n + 1) * (1 - alpha / 2)))
    lower_rank = max(1, math.floor((n + 1) * alpha / 2))
    return float(errors[lower_rank - 1]), float(errors[upper_rank - 1])


def apply_interval(
    prediction: np.ndarray, q_low: float, q_high: float
) -> tuple[np.ndarray, np.ndarray]:
    """Interval of the v1.0-baseline method (signed relative errors, ADR-004 sections 1-2).

    Kept for the comparison report and the frozen research reference: when every recent
    error has the same sign the interval excludes its own forecast (ADR-004 section 3).
    """
    lower = np.maximum(0.0, prediction * (1 + q_low))
    upper = prediction * (1 + q_high)
    return lower, upper


def log_errors(actual: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    """ln(actual / prediction): symmetric for over- and under-estimation (NaN if <= 0)."""
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.log(actual / prediction)
    out[(actual <= 0) | (prediction <= 0)] = np.nan
    return out


def log_conformal_radius(errors: np.ndarray, alpha: float = ALPHA) -> float:
    """Split-conformal radius on |ln(actual / prediction)| (ADR-004 section 3).

    With n calibration errors the radius is the ceil((n + 1)(1 - alpha))-th smallest absolute
    log error, i.e. the 80th percentile with the finite-sample correction that guarantees
    >= 1 - alpha coverage when future errors are exchangeable with the calibration errors.
    """
    values = np.sort(np.abs(np.asarray(errors, dtype=float)))
    values = values[~np.isnan(values)]
    n = len(values)
    if n == 0:
        raise ValueError("no calibration residuals")
    rank = min(n, math.ceil((n + 1) * (1 - alpha)))
    return float(values[rank - 1])


def apply_log_interval(prediction: np.ndarray, radius) -> tuple[np.ndarray, np.ndarray]:
    """prediction x exp(-radius) .. prediction x exp(+radius): positive, forecast at the
    centre on the log scale, so the served forecast is always inside its interval."""
    prediction = np.asarray(prediction, dtype=float)
    radius = np.asarray(radius, dtype=float)
    return prediction * np.exp(-radius), prediction * np.exp(radius)


def median_bias(errors: np.ndarray) -> float:
    """Median ln(actual / prediction) of the calibration errors: < 0 = the model recently
    over-estimated. Shown to visitors as exp(bias) - 1, never applied to the forecast."""
    values = np.asarray(errors, dtype=float)
    values = values[~np.isnan(values)]
    if values.size == 0:
        raise ValueError("no calibration residuals")
    return float(np.median(values))


CHAMPION_RULE = (
    "lowest median MASE on VAL_W1+VAL_W2 among Naive, SeasonalNaive, Ridge_Seasonal and "
    "LightGBM_Global (a learned model wins only if it beats the best baseline) - ADR-010"
)


def select_champion(metrics: pd.DataFrame) -> tuple[str, float | None, float | None, str]:
    """Pick the champion of one (group, horizon) on validation windows only.

    Rule (ADR-010, replaces ADR-003 2.4): the family with the lowest median MASE over
    the series x validation windows, *both baselines included*. A learned model is
    therefore served only when it beats the persistence and the seasonal naive.
    """
    summary = metrics.groupby("model_name").agg(
        median_rel_mae=("rel_mae", "median"), median_mase=("mase", "median")
    )
    best = summary["median_mase"].idxmin()
    row = summary.loc[best]
    return str(best), _f(row["median_rel_mae"]), _f(row["median_mase"]), CHAMPION_RULE


def _f(value) -> float | None:
    return None if pd.isna(value) else float(value)
