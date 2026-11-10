"""Robust seasonal anomaly score (docs/05-conception.md section 3.2).

For a monthly series with log price L[t]:
  trend     T[t] = median(L[t-12 .. t-1])               (trailing: only the past year)
  seasonal  S[m] = median over years of (L - T) for calendar month m
  residual  r[t] = L[t] - T[t] - S[m(t)]
  scale     s[m] = 1.4826 * MAD of the residuals of month m   (comparable to a std dev)
  score     z[t] = r[t] / max(s[m], 0.02)
  expected  P_expected[t] = exp(T[t] + S[m])
Medians and the MAD are insensitive to past extreme values, so one historical shock
does not mask the next one. Missing months stay NaN (no interpolation).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import Connection, text

from src.anomaly.catalog import CRITICAL_Z, WARNING_Z

MIN_OBSERVED_MONTHS = 60  # >= 5 points per calendar month for the seasonal medians
MAD_CONSISTENCY = 1.4826
MIN_SCALE = 0.02  # floor: a 2 % move is never "abnormal" on its own

# Scope: monthly, observed, food-basket retail series (+ Moroccan food CPI), with enough
# history. Unlike ML eligibility, stale series are kept: they are needed to score 2008/2012.
SCOPE_SQL = """
SELECT s.series_id, s.country_iso3, c.commodity_group, s.market_code,
       cal.reference_year, cal.reference_month, f.observed_value
FROM dim_series_catalog s
JOIN dim_commodity c USING (commodity_code)
JOIN fact_price_observation f ON f.series_id = s.series_id
JOIN dim_calendar cal ON cal.calendar_id = f.calendar_id
WHERE s.frequency = 'MONTHLY' AND f.is_observed AND c.is_food_security_basket
  AND (s.granularity_level = 'NATIONAL' OR s.price_type = 'Retail')
"""


def load_scope(conn: Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (series metadata, months x series matrix of observed prices)."""
    raw = pd.read_sql(text(SCOPE_SQL), conn)
    raw["month_idx"] = raw["reference_year"] * 12 + raw["reference_month"] - 1
    counts = raw.groupby("series_id").size()
    raw = raw[raw["series_id"].isin(counts[counts >= MIN_OBSERVED_MONTHS].index)]
    if raw.empty:
        return pd.DataFrame(
            columns=["country_iso3", "commodity_group", "market_code"]
        ), pd.DataFrame()
    meta = raw.drop_duplicates("series_id").set_index("series_id")[
        ["country_iso3", "commodity_group", "market_code"]
    ]
    prices = raw.pivot(index="month_idx", columns="series_id", values="observed_value")
    prices = prices.reindex(range(int(prices.index.min()), int(prices.index.max()) + 1))
    return meta, prices


def robust_scores(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute trend, expected value, residual and robust z for every (month, series)."""
    log_p = np.log(prices)
    trend = log_p.shift(1).rolling(12, min_periods=6).median()
    detrended = log_p - trend
    month = pd.Series(log_p.index % 12, index=log_p.index)
    seasonal = detrended.groupby(month).transform("median")
    residual = detrended - seasonal
    centre = residual.groupby(month).transform("median")
    mad = (residual - centre).abs().groupby(month).transform("median")
    scale = (MAD_CONSISTENCY * mad).clip(lower=MIN_SCALE)
    z = residual / scale
    return {
        "z": z,
        "residual": residual,
        "expected": np.exp(trend + seasonal),
        "yoy_pct": (prices / prices.shift(12) - 1) * 100,
        "observed": prices,
    }


def alerts(scores: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Long table of the months whose |z| >= WARNING_Z, with direction and severity."""
    # Round first (the warehouse stores 3 decimals) so that severity always matches |z|.
    z = scores["z"].stack().round(3)
    z = z[z.abs() >= WARNING_Z]
    index = z.index
    frame = pd.DataFrame(
        {
            "month_idx": index.get_level_values(0),
            "series_id": index.get_level_values(1),
            "z_score_robust": z.to_numpy(),
            "log_residual": scores["residual"].stack().reindex(index).to_numpy(),
            "expected_value": scores["expected"].stack().reindex(index).to_numpy(),
            "observed_value": scores["observed"].stack().reindex(index).to_numpy(),
            "yoy_change_pct": scores["yoy_pct"].stack(future_stack=True).reindex(index).to_numpy(),
        }
    )
    frame["direction"] = np.where(frame["z_score_robust"] > 0, "UP", "DOWN")
    frame["severity"] = np.where(frame["z_score_robust"].abs() >= CRITICAL_Z, "CRITICAL", "WARNING")
    return frame.reset_index(drop=True)
