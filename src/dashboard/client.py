"""HTTP client of the AgriPrix API (the dashboard never touches the database, EF-13)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
TIMEOUT = httpx.Timeout(10.0)


class ApiError(RuntimeError):
    """The API could not answer: shown to the visitor as a clear, non-technical message."""


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", params=clean, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise ApiError("Le service de données ne répond pas pour le moment.") from exc
    if response.status_code == 503:
        raise ApiError("Les prévisions ne sont pas encore calculées sur ce serveur.")
    if response.status_code == 429:
        raise ApiError("Trop de demandes en peu de temps : réessayez dans une minute.")
    if response.status_code >= 400:
        raise ApiError(f"Le service de données a refusé la demande (code {response.status_code}).")
    return response.json()


# Data change once a month: an hour of cache keeps the dashboard fast and spares the API's
# per-client quota, without serving stale numbers after a monthly refresh for long.
CACHE_TTL = 3600


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def countries() -> list[dict]:
    return _get("/api/v1/countries")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def commodities(country: str) -> list[dict]:
    return _get("/api/v1/commodities", {"country": country})


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def series(
    country: str, commodity_group: str | None = None, frequency: str = "MONTHLY"
) -> list[dict]:
    page = _get(
        "/api/v1/series",
        {
            "country": country,
            "commodity_group": commodity_group,
            "frequency": frequency,
            "limit": 1000,
        },
    )
    return page["items"]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def history(series_id: int) -> dict:
    return _get(f"/api/v1/series/{series_id}/history")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def forecasts(series_id: int | None = None, country: str | None = None,
              commodity_group: str | None = None, horizon: int | None = None) -> dict:  # fmt: skip
    return _get(
        "/api/v1/forecasts",
        {"series_id": series_id, "country": country, "commodity_group": commodity_group,
         "horizon": horizon, "limit": 1000},
    )  # fmt: skip


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def anomalies(country: str | None = None, commodity_group: str | None = None,
              series_id: int | None = None, since: str | None = None, limit: int = 1000) -> dict:  # fmt: skip
    return _get(
        "/api/v1/anomalies",
        {"country": country, "commodity_group": commodity_group, "series_id": series_id,
         "since": since, "limit": limit},
    )  # fmt: skip


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def model_metrics(
    window: str, country: str | None = None, commodity_group: str | None = None
) -> dict:
    return _get(
        "/api/v1/models/metrics",
        {"window": window, "country": country, "commodity_group": commodity_group},
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def active_run() -> dict:
    return _get("/api/v1/runs/active")


def health() -> dict:
    try:
        return _get("/api/v1/health")
    except ApiError as exc:
        return {"status": "unreachable", "error": str(exc)}
