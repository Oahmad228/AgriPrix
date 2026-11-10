"""Load the normalized observations into the star schema (one atomic transaction)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Connection, text

from src.etl.db import copy_rows
from src.etl.reference import COUNTRIES, UNIT_CONVERSIONS, calendar_rows
from src.etl.sources import RetrievedFile

logger = logging.getLogger("agriprix.etl.load")


def _none(value):
    """Convert pandas missing markers to SQL NULL."""
    return None if value is None or (not isinstance(value, str) and pd.isna(value)) else value


def upsert_reference_data(conn: Connection) -> None:
    conn.execute(
        text(
            "INSERT INTO dim_country (country_iso3, country_name_fr, default_currency,"
            " primary_source, lean_season_months) VALUES (:iso, :name, :cur, :src, :lean)"
            " ON CONFLICT (country_iso3) DO UPDATE SET country_name_fr = EXCLUDED.country_name_fr,"
            " default_currency = EXCLUDED.default_currency,"
            " primary_source = EXCLUDED.primary_source,"
            " lean_season_months = EXCLUDED.lean_season_months"
        ),
        [
            {
                "iso": c.iso3,
                "name": c.name_fr,
                "cur": c.currency,
                "src": c.primary_source,
                "lean": c.lean_season_months,
            }
            for c in COUNTRIES
        ],
    )
    conn.execute(
        text(
            "INSERT INTO ref_unit_conversion (raw_unit, canonical_unit, multiplier_to_canonical,"
            " is_metric_convertible) VALUES (:raw, :canon, :mult, :metric)"
            " ON CONFLICT (raw_unit) DO UPDATE SET canonical_unit = EXCLUDED.canonical_unit,"
            " multiplier_to_canonical = EXCLUDED.multiplier_to_canonical,"
            " is_metric_convertible = EXCLUDED.is_metric_convertible"
        ),
        [
            {
                "raw": u.raw_unit,
                "canon": u.canonical_unit,
                "mult": u.multiplier,
                "metric": u.is_metric_convertible,
            }
            for u in UNIT_CONVERSIONS
        ],
    )
    conn.execute(
        text(
            "INSERT INTO dim_calendar (calendar_id, frequency, reference_year, reference_month,"
            " period_start_date, wfp_reference_date, quarter_num)"
            " VALUES (:id, :freq, :y, :m, :start, :wfp, :q) ON CONFLICT (calendar_id) DO NOTHING"
        ),
        [
            {"id": r[0], "freq": r[1], "y": r[2], "m": r[3], "start": r[4], "wfp": r[5], "q": r[6]}
            for r in calendar_rows()
        ],
    )


def upsert_markets_and_commodities(conn: Connection, obs: pd.DataFrame) -> None:
    markets = obs.drop_duplicates("market_code", keep="last")
    conn.execute(
        text(
            "INSERT INTO dim_market (market_code, country_iso3, source_market_id, market_name,"
            " admin1_region, admin2_district, latitude, longitude, granularity_level)"
            " VALUES (:code, :iso, :sid, :name, :a1, :a2, :lat, :lon, :grain)"
            " ON CONFLICT (market_code) DO UPDATE SET market_name = EXCLUDED.market_name,"
            " admin1_region = EXCLUDED.admin1_region, admin2_district = EXCLUDED.admin2_district,"
            " latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude"
        ),
        [
            {
                "code": r.market_code,
                "iso": r.country_iso3,
                "sid": _none(r.source_market_id),
                "name": r.market_name,
                "a1": _none(r.admin1_region),
                "a2": _none(r.admin2_district),
                "lat": _none(r.latitude),
                "lon": _none(r.longitude),
                "grain": r.granularity_level,
            }
            for r in markets.itertuples()
        ],
    )
    commodities = obs.drop_duplicates("commodity_code", keep="last")
    conn.execute(
        text(
            "INSERT INTO dim_commodity (commodity_code, source_commodity_id, commodity_name_en,"
            " commodity_group, category, is_food_security_basket)"
            " VALUES (:code, :sid, :name, :grp, :cat, :basket)"
            " ON CONFLICT (commodity_code) DO UPDATE SET"
            " commodity_name_en = EXCLUDED.commodity_name_en,"
            " commodity_group = EXCLUDED.commodity_group, category = EXCLUDED.category,"
            " is_food_security_basket = EXCLUDED.is_food_security_basket"
        ),
        [
            {
                "code": r.commodity_code,
                "sid": _none(r.source_commodity_id),
                "name": r.commodity_name_en,
                "grp": r.commodity_group,
                "cat": _none(r.category),
                "basket": bool(r.is_food_security_basket),
            }
            for r in commodities.itertuples()
        ],
    )


SERIES_COLUMNS = [
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
    "total_observed_count",
    "recent_continuous_months",
    "max_consecutive_missing",
    "first_obs_date",
    "last_obs_date",
    "is_ml_eligible",
    "ineligibility_reason",
]


def upsert_series(conn: Connection, catalog: pd.DataFrame) -> dict[str, int]:
    """Upsert the catalog by natural key; series_id stays stable across runs."""
    placeholders = ", ".join(f":{c}" for c in SERIES_COLUMNS)
    # Identity columns (key parts) never change for a given key; only statistics do.
    stats_columns = SERIES_COLUMNS[SERIES_COLUMNS.index("total_observed_count") :]
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in stats_columns)
    conn.execute(
        text(
            f"INSERT INTO dim_series_catalog ({', '.join(SERIES_COLUMNS)}) VALUES ({placeholders})"
            f" ON CONFLICT (series_natural_key) DO UPDATE SET {updates}"
        ),
        [{c: _none(row[c]) for c in SERIES_COLUMNS} for _, row in catalog.iterrows()],
    )
    # A series that vanished from the latest source files keeps its id (history, future
    # forecasts) but can no longer be eligible.
    conn.execute(
        text(
            "UPDATE dim_series_catalog SET is_ml_eligible = FALSE, total_observed_count = 0,"
            " recent_continuous_months = 0, ineligibility_reason = 'ABSENT_FROM_SOURCE'"
            " WHERE series_natural_key <> ALL(:keys)"
        ),
        {"keys": list(catalog["series_natural_key"])},
    )
    return dict(
        conn.execute(text("SELECT series_natural_key, series_id FROM dim_series_catalog")).all()
    )


@dataclass
class FactLoadStats:
    staged: int
    inserted: int
    updated: int
    deleted: int

    @property
    def upserted(self) -> int:
        return self.inserted + self.updated


FACT_KEY = ("series_id", "calendar_id", "source_flag")
FACT_COLUMNS = [
    "series_id",
    "calendar_id",
    "frequency",
    "observed_value",
    "raw_value",
    "raw_unit",
    "source_flag",
    "is_observed",
    "etl_run_id",
]


def load_observations(
    conn: Connection, obs: pd.DataFrame, series_ids: dict[str, int], etl_run_id: int
) -> FactLoadStats:
    """Synchronize the fact table with this run's observations (incremental load).

    Rows are first COPYed into a constraint-free temporary staging table, then merged
    with three set-based statements. Only new rows pay the foreign-key checks, so a
    monthly refresh that adds a few thousand rows is fast, while the first load or a
    full source revision still converges to exactly the content of the source files.
    Rows absent from the sources (e.g. a flag changed from 'aggregate' to 'actual',
    which changes the key) are deleted, so no stale duplicate can survive.
    """
    conn.execute(
        text(
            "CREATE TEMP TABLE stage_observation"
            " (LIKE fact_price_observation INCLUDING DEFAULTS) ON COMMIT DROP"
        )
    )
    rows = (
        (
            series_ids[r.series_natural_key],
            int(r.calendar_id),
            r.frequency,
            float(r.observed_value),
            float(r.raw_value),
            r.raw_unit,
            r.source_flag,
            bool(r.is_observed),
            etl_run_id,
        )
        for r in obs.itertuples()
    )
    staged = copy_rows(conn, "stage_observation", FACT_COLUMNS, rows)
    conn.execute(text("ANALYZE stage_observation"))

    join = " AND ".join(f"f.{k} = s.{k}" for k in FACT_KEY)
    deleted = conn.execute(
        text(
            "DELETE FROM fact_price_observation f WHERE NOT EXISTS"
            f" (SELECT 1 FROM stage_observation s WHERE {join})"
        )
    ).rowcount
    updated = conn.execute(
        text(
            "UPDATE fact_price_observation f SET observed_value = s.observed_value,"
            " raw_value = s.raw_value, raw_unit = s.raw_unit, is_observed = s.is_observed,"
            " etl_run_id = s.etl_run_id, ingested_at = now()"
            f" FROM stage_observation s WHERE {join} AND"
            " (f.observed_value, f.raw_value, f.raw_unit, f.is_observed)"
            " IS DISTINCT FROM (s.observed_value, s.raw_value, s.raw_unit, s.is_observed)"
        )
    ).rowcount
    columns = ", ".join(FACT_COLUMNS)
    inserted = conn.execute(
        text(
            f"INSERT INTO fact_price_observation ({columns})"
            f" SELECT {', '.join('s.' + c for c in FACT_COLUMNS)} FROM stage_observation s"
            f" WHERE NOT EXISTS (SELECT 1 FROM fact_price_observation f WHERE {join})"
        )
    ).rowcount
    logger.info(
        "facts: %d staged, %d inserted, %d updated, %d deleted", staged, inserted, updated, deleted
    )
    return FactLoadStats(staged, inserted, updated, deleted)


def load_rejects(conn: Connection, rejects: pd.DataFrame, etl_run_id: int) -> int:
    rows = (
        (etl_run_id, r.source_file, int(r.line_number), r.reason_code, r.raw_payload_json)
        for r in rejects.itertuples()
    )
    columns = ["etl_run_id", "source_file", "line_number", "reason_code", "raw_payload_json"]
    return copy_rows(conn, "audit_rejected_rows", columns, rows)


def record_source_files(conn: Connection, files: list[RetrievedFile], etl_run_id: int) -> None:
    conn.execute(
        text(
            "INSERT INTO etl_source_file (etl_run_id, source_name, url, size_bytes, md5,"
            " remote_last_modified, from_cache) VALUES (:run, :name, :url, :size, :md5, :lm, :cache)"
        ),
        [
            {
                "run": etl_run_id,
                "name": f.spec.name,
                "url": f.url,
                "size": f.size_bytes,
                "md5": f.md5,
                "lm": f.last_modified,
                "cache": f.from_cache,
            }
            for f in files
        ],
    )


def refresh_country_max_dates(conn: Connection) -> None:
    conn.execute(
        text(
            "UPDATE dim_country c SET max_observed_date = sub.max_date FROM ("
            " SELECT s.country_iso3, MAX(cal.period_start_date) AS max_date"
            " FROM fact_price_observation f"
            " JOIN dim_series_catalog s ON s.series_id = f.series_id"
            " JOIN dim_calendar cal ON cal.calendar_id = f.calendar_id"
            " WHERE f.frequency = 'MONTHLY' GROUP BY s.country_iso3) sub"
            " WHERE sub.country_iso3 = c.country_iso3"
        )
    )
