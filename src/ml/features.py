"""Supervised dataset for direct multi-horizon forecasting on log prices.

For an origin month t (an observed month of a series) and a horizon h, the model predicts
    target = ln(P[t+h]) - ln(P[t])
i.e. the log-return over h months. Working on log-returns relative to the last known
price makes markets with very different price levels comparable, which is what lets a
single "global" model learn from all markets of a (country, commodity group).

Every feature only uses prices observed at or before t (causal). Missing months stay
NaN: nothing is interpolated. LightGBM handles NaN natively; the Ridge model gets a
0 ("no change") plus an explicit missing-value indicator column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.data import Panel

LAGS = (1, 2, 3, 6, 12)
NUMERIC_FEATURES = [
    *(f"lag_{k}" for k in LAGS),
    "seasonal_level",  # ln P[t+h-12] - ln P[t]: same month last year vs now
    "seasonal_change",  # ln P[t+h-12] - ln P[t-12]: last year's change over the same h
    "roll_mean_3",
    "roll_mean_12",
    "volatility_12",
    "target_month_sin",
    "target_month_cos",
    "target_in_lean_season",
]


def wide_log_prices(panel: Panel, series_ids: list[int]) -> pd.DataFrame:
    """Months x series matrix of ln(price), NaN where a month was not observed."""
    subset = panel.values[panel.values["series_id"].isin(series_ids)]
    wide = subset.pivot(index="month_idx", columns="series_id", values="value")
    full_index = range(int(wide.index.min()), int(wide.index.max()) + 1)
    return np.log(wide.reindex(full_index))


def _lean_months(spec: str | None) -> set[int]:
    return {int(m) for m in spec.split(",")} if spec else set()


def build_supervised(
    panel: Panel, series_ids: list[int], horizon: int, lean_season: str | None
) -> pd.DataFrame:
    """One row per (series, observed origin month) with features, target and baselines."""
    log_p = wide_log_prices(panel, series_ids)
    shift_seasonal = 12 - horizon
    blocks = {
        **{f"lag_{k}": log_p.shift(k) - log_p for k in LAGS},
        "seasonal_level": log_p.shift(shift_seasonal) - log_p,
        "seasonal_change": log_p.shift(shift_seasonal) - log_p.shift(12),
        "roll_mean_3": log_p.rolling(3, min_periods=1).mean() - log_p,
        "roll_mean_12": log_p.rolling(12, min_periods=1).mean() - log_p,
        "volatility_12": log_p.diff().rolling(12, min_periods=3).std(),
        "target": log_p.shift(-horizon) - log_p,
        "anchor_log": log_p,
    }
    long = pd.concat(
        {name: frame.stack(future_stack=True) for name, frame in blocks.items()}, axis=1
    )
    long.index.names = ["month_idx", "series_id"]
    long = long[long["anchor_log"].notna()].reset_index()

    target_month = (long["month_idx"] + horizon) % 12 + 1
    long["target_month_sin"] = np.sin(2 * np.pi * target_month / 12)
    long["target_month_cos"] = np.cos(2 * np.pi * target_month / 12)
    long["target_in_lean_season"] = target_month.isin(_lean_months(lean_season)).astype(float)
    long["target_month_idx"] = long["month_idx"] + horizon
    long["horizon"] = horizon
    long["anchor_value"] = np.exp(long["anchor_log"])
    long["actual_value"] = np.exp(long["anchor_log"] + long["target"])
    # Seasonal naive: price of the same month one year earlier; falls back to the last
    # observed price when that month is missing (recorded for transparency).
    long["snaive_fallback"] = long["seasonal_level"].isna()
    long["snaive_value"] = np.exp(long["anchor_log"] + long["seasonal_level"].fillna(0.0))
    commodity = panel.series.set_index("series_id")["commodity_code"]
    long["commodity_code"] = long["series_id"].map(commodity)
    return long


def seasonal_scale(panel: Panel, series_ids: list[int], cutoff: int) -> pd.Series:
    """MASE denominator per series: in-sample mean |P[t] - P[t-12]| over t <= cutoff."""
    prices = np.exp(wide_log_prices(panel, series_ids))
    diffs = (prices - prices.shift(12)).abs()
    return diffs[diffs.index <= cutoff].mean()
