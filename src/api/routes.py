"""Read-only business routes of the public API (US-12)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Connection, text

from src.api import schemas
from src.api.db import get_connection
from src.api.explain import explain_anomaly
from src.api.limits import limited

router = APIRouter(prefix="/api/v1")
Conn = Annotated[Connection, Depends(get_connection)]
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0)]

ACTIVE_RUN = "(SELECT run_id FROM training_run WHERE is_production_active)"


def _active_run(conn: Connection) -> dict:
    row = (
        conn.execute(
            text("SELECT run_id, max_data_date FROM training_run WHERE is_production_active")
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(503, "No active training run: forecasts are not available yet")
    return dict(row)


def _where(conditions: list[str]) -> str:
    return " WHERE " + " AND ".join(conditions) if conditions else ""


@router.get("/countries", response_model=list[schemas.Country], tags=["Référentiels"])
@limited
def list_countries(request: Request, conn: Conn):
    """Countries covered, with their currency, lean season and latest data date."""
    rows = conn.execute(
        text(
            "SELECT c.*, COUNT(s.series_id) FILTER (WHERE s.is_ml_eligible) AS ml_eligible_series"
            " FROM dim_country c LEFT JOIN dim_series_catalog s USING (country_iso3)"
            " GROUP BY c.country_iso3 ORDER BY c.country_iso3"
        )
    ).mappings()
    return [dict(r) for r in rows]


@router.get("/commodities", response_model=list[schemas.Commodity], tags=["Référentiels"])
@limited
def list_commodities(
    request: Request,
    conn: Conn,
    country: str | None = None,
    basket_only: Annotated[bool, Query(description="Only the food-security basket")] = True,
):
    conditions, params = [], {}
    if country:
        conditions.append("s.country_iso3 = :country")
        params["country"] = country.upper()
    if basket_only:
        conditions.append("c.is_food_security_basket")
    rows = conn.execute(
        text(
            "SELECT c.commodity_code, c.commodity_name_en, c.commodity_group,"
            " c.is_food_security_basket, COUNT(*) AS series"
            " FROM dim_commodity c JOIN dim_series_catalog s USING (commodity_code)"
            + _where(conditions)
            + " GROUP BY 1, 2, 3, 4 ORDER BY c.commodity_group, c.commodity_name_en"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]


@router.get("/markets", response_model=list[schemas.Market], tags=["Référentiels"])
@limited
def list_markets(request: Request, conn: Conn, country: str | None = None):
    conditions, params = [], {}
    if country:
        conditions.append("country_iso3 = :country")
        params["country"] = country.upper()
    rows = conn.execute(
        text(
            "SELECT * FROM dim_market" + _where(conditions) + " ORDER BY country_iso3, market_name"
        ),
        params,
    ).mappings()
    return [dict(r) for r in rows]


SERIES_SELECT = """
SELECT s.series_id, s.country_iso3, s.market_code, m.market_name, s.commodity_code,
       c.commodity_name_en, c.commodity_group, s.price_type, s.unit_measure, s.currency_code,
       s.frequency, s.value_type, s.granularity_level, s.first_obs_date, s.last_obs_date,
       s.is_ml_eligible, s.ineligibility_reason
FROM dim_series_catalog s
JOIN dim_market m USING (market_code)
JOIN dim_commodity c USING (commodity_code)
"""


@router.get("/series", response_model=schemas.SeriesPage, tags=["Séries"])
@limited
def list_series(
    request: Request,
    conn: Conn,
    country: str | None = None,
    commodity_group: str | None = None,
    market_code: str | None = None,
    price_type: Annotated[
        str,
        Query(
            description="Market series are filtered on this price type (default 'Retail', what "
            "households pay); national series (Morocco) are always kept. Use 'all' to disable."
        ),
    ] = "Retail",
    frequency: Literal["MONTHLY", "ANNUAL"] | None = None,
    value_type: Literal["PRICE", "INDEX", "INFLATION_RATE"] | None = None,
    granularity_level: Literal["MARKET", "NATIONAL"] | None = None,
    eligible_only: bool = False,
    limit: Limit = 100,
    offset: Offset = 0,
):
    conditions, params = [], {"limit": limit, "offset": offset}
    filters = {
        "s.country_iso3": country.upper() if country else None,
        "c.commodity_group": commodity_group,
        "s.market_code": market_code,
        "s.frequency": frequency,
        "s.value_type": value_type,
        "s.granularity_level": granularity_level,
    }
    for i, (column, value) in enumerate(filters.items()):
        if value is not None:
            conditions.append(f"{column} = :p{i}")
            params[f"p{i}"] = value
    if price_type.lower() != "all":
        conditions.append("(s.granularity_level = 'NATIONAL' OR s.price_type = :price_type)")
        params["price_type"] = price_type
    if eligible_only:
        conditions.append("s.is_ml_eligible")
    where = _where(conditions)
    total = conn.execute(
        text(
            "SELECT COUNT(*) FROM dim_series_catalog s JOIN dim_commodity c USING (commodity_code)"
            + where
        ),
        params,
    ).scalar_one()
    rows = conn.execute(
        text(SERIES_SELECT + where + " ORDER BY s.series_id LIMIT :limit OFFSET :offset"), params
    ).mappings()
    return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


@router.get("/series/{series_id}/history", response_model=schemas.SeriesHistory, tags=["Séries"])
@limited
def series_history(
    request: Request,
    conn: Conn,
    series_id: int,
    start: date | None = None,
    end: date | None = None,
    observed_only: Annotated[
        bool, Query(description="Hide aggregated, estimated and imputed values")
    ] = False,
):
    series = (
        conn.execute(text(SERIES_SELECT + " WHERE s.series_id = :sid"), {"sid": series_id})
        .mappings()
        .one_or_none()
    )
    if series is None:
        raise HTTPException(404, f"Unknown series {series_id}")
    conditions, params = ["f.series_id = :sid"], {"sid": series_id}
    if start:
        conditions.append("cal.period_start_date >= :start")
        params["start"] = start
    if end:
        conditions.append("cal.period_start_date <= :end")
        params["end"] = end
    if observed_only:
        conditions.append("f.is_observed")
    rows = conn.execute(
        text(
            "SELECT cal.period_start_date AS period, f.observed_value AS value, f.raw_value,"
            " f.raw_unit, f.source_flag, f.is_observed"
            " FROM fact_price_observation f JOIN dim_calendar cal USING (calendar_id)"
            + _where(conditions)
            + " ORDER BY cal.period_start_date, f.source_flag"
        ),
        params,
    ).mappings()
    return {"series": dict(series), "observations": [dict(r) for r in rows]}


@router.get("/forecasts", response_model=schemas.ForecastResponse, tags=["Prévisions"])
@limited
def list_forecasts(
    request: Request,
    conn: Conn,
    series_id: int | None = None,
    country: str | None = None,
    commodity_group: str | None = None,
    horizon: Annotated[int | None, Query(description="1, 3 or 6 months")] = None,
    limit: Limit = 300,
):
    """Forecasts of the active run (champion model per group and horizon, 80 % interval)."""
    if horizon is not None and horizon not in (1, 3, 6):
        raise HTTPException(422, "horizon must be 1, 3 or 6")
    run = _active_run(conn)
    conditions, params = ["f.run_id = :run"], {"run": run["run_id"], "limit": limit}
    for column, key, value in (
        ("f.series_id", "sid", series_id),
        ("s.country_iso3", "country", country.upper() if country else None),
        ("c.commodity_group", "grp", commodity_group),
        ("f.horizon_months", "h", horizon),
    ):
        if value is not None:
            conditions.append(f"{column} = :{key}")
            params[key] = value
    rows = conn.execute(
        text(
            " SELECT f.series_id, s.country_iso3, m.market_name, c.commodity_name_en,"
            "  s.unit_measure, s.currency_code, f.horizon_months,"
            "  o.period_start_date AS origin_period, t.period_start_date AS target_period,"
            "  f.yhat_point AS yhat, f.yhat_lower_80 AS lower_80, f.yhat_upper_80 AS upper_80,"
            "  f.champion_model_name AS model, ch.test_picp_80"
            " FROM fact_forecast f"
            " JOIN dim_series_catalog s USING (series_id)"
            " JOIN dim_market m USING (market_code)"
            " JOIN dim_commodity c USING (commodity_code)"
            " JOIN dim_calendar o ON o.calendar_id = f.origin_calendar_id"
            " JOIN dim_calendar t ON t.calendar_id = f.target_calendar_id"
            " LEFT JOIN fact_champion_model ch ON ch.run_id = f.run_id"
            "  AND ch.country_iso3 = s.country_iso3 AND ch.commodity_group = c.commodity_group"
            "  AND ch.horizon_months = f.horizon_months"
            + _where(conditions)
            + " ORDER BY f.series_id, f.horizon_months LIMIT :limit"
        ),
        params,
    ).mappings()
    return {
        "training_run_id": run["run_id"],
        "data_until": run["max_data_date"],
        "items": [dict(r) for r in rows],
    }


@router.get("/anomalies", response_model=schemas.AnomalyPage, tags=["Anomalies"])
@limited
def list_anomalies(
    request: Request,
    conn: Conn,
    country: str | None = None,
    commodity_group: str | None = None,
    series_id: int | None = None,
    since: date | None = None,
    until: date | None = None,
    severity: Literal["WARNING", "CRITICAL"] | None = None,
    direction: Literal["UP", "DOWN"] | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    """Price alerts (|robust z| >= 2.5) of the active run, most recent first."""
    run = _active_run(conn)
    conditions, params = (
        ["a.run_id = :run"],
        {"run": run["run_id"], "limit": limit, "offset": offset},
    )
    for column, key, value in (
        ("s.country_iso3", "country", country.upper() if country else None),
        ("c.commodity_group", "grp", commodity_group),
        ("a.series_id", "sid", series_id),
        ("a.severity", "sev", severity),
        ("a.direction", "dir", direction),
    ):
        if value is not None:
            conditions.append(f"{column} = :{key}")
            params[key] = value
    if since:
        conditions.append("cal.period_start_date >= :since")
        params["since"] = since
    if until:
        conditions.append("cal.period_start_date <= :until")
        params["until"] = until
    joins = (
        " FROM fact_anomaly a JOIN dim_series_catalog s USING (series_id)"
        " JOIN dim_market m USING (market_code) JOIN dim_commodity c USING (commodity_code)"
        " JOIN dim_calendar cal ON cal.calendar_id = a.calendar_id"
    )
    where = _where(conditions)
    total = conn.execute(text("SELECT COUNT(*)" + joins + where), params).scalar_one()
    rows = conn.execute(
        text(
            "SELECT a.series_id, s.country_iso3, m.market_name, c.commodity_name_en,"
            " cal.period_start_date AS period, a.observed_value, a.expected_value,"
            " a.z_score_robust, a.yoy_change_pct, a.direction, a.severity,"
            " s.currency_code, s.unit_measure"
            + joins
            + where
            + " ORDER BY cal.period_start_date DESC, ABS(a.z_score_robust) DESC"
            " LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings()
    items = []
    for r in rows:
        observed, expected = float(r["observed_value"]), float(r["expected_value"])
        items.append(
            {
                **{
                    k: r[k]
                    for k in (
                        "series_id",
                        "country_iso3",
                        "market_name",
                        "commodity_name_en",
                        "period",
                        "z_score_robust",
                        "yoy_change_pct",
                        "direction",
                        "severity",
                    )
                },  # fmt: skip
                "observed_value": observed,
                "expected_value": expected,
                "deviation_pct": round((observed / expected - 1) * 100, 1),
                "explanation_fr": explain_anomaly(
                    commodity=r["commodity_name_en"],
                    market=r["market_name"],
                    country=r["country_iso3"],
                    period=r["period"],
                    observed=observed,
                    expected=expected,
                    currency=r["currency_code"],
                    unit=r["unit_measure"],
                    severity=r["severity"],
                ),
            }
        )
    return {
        "training_run_id": run["run_id"],
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/models/metrics", response_model=schemas.MetricsResponse, tags=["Modèles"])
@limited
def model_metrics(
    request: Request,
    conn: Conn,
    country: str | None = None,
    commodity_group: str | None = None,
    window: Literal["VAL_W1_2022", "VAL_W2_24_25", "TEST_W3_25_26"] = "TEST_W3_25_26",
):
    """Out-of-sample quality of each model family per horizon (same points for every model)."""
    run = _active_run(conn)
    conditions = ["m.run_id = :run", "m.eval_window = :window"]
    params = {"run": run["run_id"], "window": window}
    if country:
        conditions.append("s.country_iso3 = :country")
        params["country"] = country.upper()
    if commodity_group:
        conditions.append("c.commodity_group = :grp")
        params["grp"] = commodity_group
    where = _where(conditions)
    rows = conn.execute(
        text(
            "WITH m AS (SELECT m.*, s.country_iso3, c.commodity_group"
            "  FROM fact_model_metrics_by_series m JOIN dim_series_catalog s USING (series_id)"
            "  JOIN dim_commodity c USING (commodity_code)" + where + "),"
            " naive AS (SELECT horizon_months, SUM(mae * n_eval_points) AS err FROM m"
            "  WHERE model_name = 'Naive' GROUP BY 1),"
            " champ AS (SELECT horizon_months, champion_model_name, COUNT(*) AS n,"
            "  SUM(COUNT(*)) OVER (PARTITION BY horizon_months) AS total"
            "  FROM fact_champion_model WHERE run_id = :run"
            + (" AND country_iso3 = :country" if country else "")
            + (" AND commodity_group = :grp" if commodity_group else "")
            + "  GROUP BY 1, 2)"
            " SELECT m.model_name, m.horizon_months, COUNT(*) AS series,"
            "  SUM(m.mape * m.n_eval_points) / SUM(m.n_eval_points) AS mape_pct,"
            "  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY m.mase) AS median_mase,"
            "  100 * (1 - SUM(m.mae * m.n_eval_points) / NULLIF(MAX(n.err), 0)) AS gain_vs_naive_pct,"
            "  SUM(m.picp_80 * m.n_eval_points) / NULLIF(SUM(m.n_eval_points)"
            "   FILTER (WHERE m.picp_80 IS NOT NULL), 0) AS picp_80,"
            "  COALESCE(MAX(ch.n::float / ch.total), 0) AS is_champion_share"
            " FROM m JOIN naive n USING (horizon_months)"
            " LEFT JOIN champ ch ON ch.horizon_months = m.horizon_months"
            "  AND ch.champion_model_name = m.model_name"
            " GROUP BY 1, 2 ORDER BY 2, 1"
        ),
        params,
    ).mappings()
    items = [
        {**dict(r), "country_iso3": params.get("country"), "commodity_group": commodity_group,
         "eval_window": window}
        for r in rows
    ]  # fmt: skip
    return {"training_run_id": run["run_id"], "items": items}


@router.get("/runs/active", response_model=schemas.RunInfo, tags=["Modèles"])
@limited
def active_run(request: Request, conn: Conn):
    """Which data and code version the API is currently serving."""
    row = (
        conn.execute(
            text(
                "SELECT r.run_id AS training_run_id, r.etl_run_id, r.max_data_date AS data_until,"
                " r.git_sha, r.finished_at::text AS finished_at, r.mlflow_parent_run_id,"
                " (SELECT COUNT(*) FROM dim_series_catalog WHERE is_ml_eligible) AS ml_eligible_series,"
                " (SELECT COUNT(*) FROM fact_forecast f WHERE f.run_id = r.run_id) AS forecasts,"
                " (SELECT COUNT(*) FROM fact_anomaly a WHERE a.run_id = r.run_id) AS anomalies"
                f" FROM training_run r WHERE r.run_id = {ACTIVE_RUN}"
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(503, "No active training run yet")
    return dict(row)
