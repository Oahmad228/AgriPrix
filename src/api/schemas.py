"""Typed response models: they document the API in OpenAPI (/docs) and validate output."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Country(BaseModel):
    country_iso3: str
    country_name_fr: str
    default_currency: str
    primary_source: str
    lean_season_months: str | None
    max_observed_date: date | None
    ml_eligible_series: int


class Commodity(BaseModel):
    commodity_code: str
    commodity_name_en: str
    commodity_group: str
    is_food_security_basket: bool
    series: int


class Market(BaseModel):
    market_code: str
    country_iso3: str
    market_name: str
    admin1_region: str | None
    admin2_district: str | None
    latitude: float | None
    longitude: float | None
    granularity_level: str


class Series(BaseModel):
    series_id: int
    country_iso3: str
    market_code: str
    market_name: str
    commodity_code: str
    commodity_name_en: str
    commodity_group: str
    price_type: str
    unit_measure: str
    currency_code: str
    frequency: str = Field(description="MONTHLY or ANNUAL")
    value_type: str = Field(description="PRICE, INDEX or INFLATION_RATE")
    granularity_level: str = Field(description="MARKET or NATIONAL")
    first_obs_date: date | None
    last_obs_date: date | None
    is_ml_eligible: bool
    ineligibility_reason: str | None


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class SeriesPage(Page):
    items: list[Series]


class Observation(BaseModel):
    period: date = Field(description="First day of the month (MONTHLY) or of the year (ANNUAL)")
    value: float = Field(description="Value in the canonical unit of the series")
    raw_value: float
    raw_unit: str
    source_flag: str
    is_observed: bool = Field(description="False for aggregated, estimated or imputed values")


class SeriesHistory(BaseModel):
    series: Series
    observations: list[Observation]


class Forecast(BaseModel):
    series_id: int
    country_iso3: str
    market_name: str
    commodity_name_en: str
    unit_measure: str
    currency_code: str
    horizon_months: int
    origin_period: date
    last_value: float | None = Field(description="Observed value at the forecast origin")
    target_period: date
    yhat: float
    lower_80: float
    upper_80: float
    model: str
    test_picp_80: float | None = Field(
        description="Coverage of the 80 % interval measured on the final test window for this "
        "group, model and horizon"
    )


class ForecastResponse(BaseModel):
    training_run_id: int
    data_until: date
    items: list[Forecast]


class Anomaly(BaseModel):
    series_id: int
    country_iso3: str
    market_name: str
    commodity_name_en: str
    period: date
    observed_value: float
    expected_value: float
    deviation_pct: float = Field(description="observed / expected - 1, in %")
    z_score_robust: float
    yoy_change_pct: float | None
    direction: str
    severity: str
    explanation_fr: str


class AnomalyPage(Page):
    training_run_id: int
    items: list[Anomaly]


class ModelMetric(BaseModel):
    country_iso3: str | None
    commodity_group: str | None
    eval_window: str
    model_name: str
    horizon_months: int
    series: int
    mape_pct: float
    median_mase: float | None
    gain_vs_naive_pct: float | None = Field(
        description="1 - total absolute error / total absolute error of the persistence baseline"
    )
    picp_80: float | None
    is_champion_share: float = Field(description="Share of groups where this model is champion")


class MetricsResponse(BaseModel):
    training_run_id: int
    items: list[ModelMetric]


class RunInfo(BaseModel):
    training_run_id: int
    etl_run_id: int | None
    data_until: date
    git_sha: str | None
    finished_at: str | None
    mlflow_parent_run_id: str | None
    ml_eligible_series: int
    forecasts: int
    anomalies: int
