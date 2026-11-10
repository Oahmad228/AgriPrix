"""Load the ML panel (eligible series, observed values only) from the warehouse."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Connection, text


def month_index(year: int | pd.Series, month: int | pd.Series):
    """Absolute month number: consecutive months differ by exactly 1."""
    return year * 12 + month - 1


def calendar_id_of(index: int) -> int:
    return (index // 12) * 100 + index % 12 + 1


@dataclass
class Panel:
    """Eligible series metadata + their observed monthly values (missing months absent)."""

    series: pd.DataFrame  # one row per series_id
    values: pd.DataFrame  # series_id, month_idx, value

    @property
    def last_month(self) -> int:
        return int(self.values["month_idx"].max())


SERIES_SQL = """
SELECT s.series_id, s.country_iso3, c.commodity_group, s.commodity_code, s.value_type,
       s.unit_measure, s.currency_code, co.lean_season_months
FROM dim_series_catalog s
JOIN dim_commodity c USING (commodity_code)
JOIN dim_country co USING (country_iso3)
WHERE s.is_ml_eligible
"""

# Only observed values (WFP 'actual', FAOSTAT A/X/B flags): aggregates, estimates and
# imputations never reach the models (ADR-009).
VALUES_SQL = """
SELECT f.series_id, cal.reference_year, cal.reference_month, f.observed_value
FROM fact_price_observation f
JOIN dim_series_catalog s ON s.series_id = f.series_id
JOIN dim_calendar cal ON cal.calendar_id = f.calendar_id
WHERE s.is_ml_eligible AND f.is_observed AND f.frequency = 'MONTHLY'
"""


def load_panel(conn: Connection) -> Panel:
    series = pd.read_sql(text(SERIES_SQL), conn)
    raw = pd.read_sql(text(VALUES_SQL), conn)
    values = pd.DataFrame(
        {
            "series_id": raw["series_id"].astype(int),
            "month_idx": month_index(raw["reference_year"], raw["reference_month"]).astype(int),
            "value": raw["observed_value"].astype(float),
        }
    )
    return Panel(series.sort_values("series_id").reset_index(drop=True), values)
