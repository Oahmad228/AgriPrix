"""Series catalog statistics and ML eligibility (docs/05-conception.md section 2.2).

A monthly series is eligible for 1/3/6-month forecasting only if ALL of these hold:
  1. frequency is MONTHLY (annual FAOSTAT producer prices never are);
  2. it belongs to the food-security basket (WFP rice, millet, sorghum, maize, beans,
     or the Moroccan food CPI 23013);
  3. WFP series are retail prices (what households pay);
  4. relative freshness: last observed month >= latest month of the country file - 3;
  5. its most recent continuous segment holds >= 60 observed months, where "continuous"
     tolerates at most 3 consecutive missing months. Missing months are left missing:
     nothing is interpolated.
Only observed values count (WFP 'actual', FAOSTAT A/X/B flags); aggregates, estimates
and imputations are stored but never make a series eligible.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

MIN_CONTINUOUS_MONTHS = 60
MAX_CONSECUTIVE_MISSING = 3
FRESHNESS_MONTHS = 3

SERIES_ATTRIBUTES = [
    "series_natural_key",
    "market_code",
    "country_iso3",
    "commodity_code",
    "price_type",
    "unit_measure",
    "currency_code",
    "frequency",
    "value_type",
    "granularity_level",
]


def recent_segment(month_indices: Sequence[int]) -> tuple[int, int | None]:
    """Return (observed months in the most recent continuous segment, longest gap inside it).

    ``month_indices`` are sorted, unique absolute month numbers (year*12 + month-1).
    The segment is walked backwards from the last observation and stops at the first
    gap of more than MAX_CONSECUTIVE_MISSING missing months.
    """
    if len(month_indices) == 0:
        return 0, None
    count, longest_gap = 1, 0
    for later, earlier in zip(month_indices[:0:-1], month_indices[-2::-1], strict=True):
        gap = later - earlier - 1
        if gap > MAX_CONSECUTIVE_MISSING:
            break
        longest_gap = max(longest_gap, gap)
        count += 1
    return count, longest_gap


def ineligibility_reason(
    series: pd.Series, recent_months: int, last_obs_index: int | None, country_max_index: int
) -> str | None:
    """Return the first failed eligibility rule, or None when the series is eligible."""
    if series["frequency"] != "MONTHLY":
        return "ANNUAL_FREQUENCY"
    if not series["is_food_security_basket"]:
        return "NOT_IN_FOOD_BASKET"
    if series["granularity_level"] == "MARKET" and series["price_type"] != "Retail":
        return "NOT_RETAIL_PRICE"
    if last_obs_index is None:
        return "NO_OBSERVED_VALUE"
    if last_obs_index < country_max_index - FRESHNESS_MONTHS:
        return "STALE_LAST_OBSERVATION"
    if recent_months < MIN_CONTINUOUS_MONTHS:
        return "SHORT_CONTINUOUS_SEGMENT"
    return None


def build_series_catalog(obs: pd.DataFrame) -> pd.DataFrame:
    """One row per series with observation statistics and the eligibility verdict."""
    obs = obs.assign(
        _month_index=obs["reference_year"].astype(int) * 12
        + obs["reference_month"].fillna(1).astype(int)
        - 1
    )
    monthly = obs[obs["frequency"] == "MONTHLY"]
    country_max = monthly.groupby("country_iso3")["_month_index"].max().to_dict()

    attributes = (
        obs.groupby("series_natural_key", sort=True)
        .agg({c: "first" for c in SERIES_ATTRIBUTES[1:]} | {"is_food_security_basket": "first"})
        .reset_index()
    )
    observed = obs[obs["is_observed"]]
    per_series = observed.groupby("series_natural_key")["_month_index"].apply(
        lambda s: sorted(set(s))
    )
    first_year = observed.groupby("series_natural_key")["reference_year"].min()
    last_year = observed.groupby("series_natural_key")["reference_year"].max()

    rows = []
    for _, series in attributes.iterrows():
        key = series["series_natural_key"]
        months = per_series.get(key, [])
        total = len(months)
        if series["frequency"] == "MONTHLY":
            recent, longest_gap = recent_segment(months)
            first = _month_start(months[0]) if months else None
            last = _month_start(months[-1]) if months else None
            last_index = months[-1] if months else None
        else:
            recent, longest_gap = 0, None
            first = pd.Timestamp(int(first_year[key]), 1, 1).date() if total else None
            last = pd.Timestamp(int(last_year[key]), 1, 1).date() if total else None
            last_index = None
        reason = ineligibility_reason(
            series, recent, last_index, country_max.get(series["country_iso3"], 0)
        )
        rows.append(
            {
                **{c: series[c] for c in SERIES_ATTRIBUTES},
                "total_observed_count": total,
                "recent_continuous_months": recent,
                "max_consecutive_missing": longest_gap,
                "first_obs_date": first,
                "last_obs_date": last,
                "is_ml_eligible": reason is None,
                "ineligibility_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def _month_start(month_index: int):
    return pd.Timestamp(month_index // 12, month_index % 12 + 1, 1).date()
