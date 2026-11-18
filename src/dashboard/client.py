"""HTTP client of the AgriPrix API (the dashboard never touches the database, EF-13)."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
# A free hosted API sleeps when idle and needs up to about a minute to wake up.
TIMEOUT = httpx.Timeout(float(os.getenv("API_TIMEOUT_SECONDS", "10")))
# Shared secret that exempts the dashboard from the per-visitor quota (see src/api/limits.py).
HEADERS = {"X-Internal-Key": key} if (key := os.getenv("API_INTERNAL_KEY")) else {}


class ApiError(RuntimeError):
    """The API could not answer: shown to the visitor as a clear, non-technical message."""


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        response = httpx.get(
            f"{API_BASE_URL}{path}", params=clean, headers=HEADERS, timeout=TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise ApiError("Le service de données ne répond pas pour le moment.") from exc
    if response.status_code == 503:
        raise ApiError("Les prévisions ne sont pas encore calculées sur ce serveur.")
    if response.status_code == 429:
        raise ApiError("Trop de demandes en peu de temps : réessayez dans une minute.")
    if response.status_code >= 400:
        raise ApiError(f"Le service de données a refusé la demande (code {response.status_code}).")
    return response.json()


# Data change once a month. Every cached answer is keyed on the active training run: a
# light query (/runs/active, cached one minute) gives its id, so a monthly publication shows
# its new numbers within a minute instead of after the one-hour cache expiry.
CACHE_TTL = 3600
VERSION_TTL = 60
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://agriprix-api.onrender.com")


@st.cache_data(ttl=VERSION_TTL, show_spinner=False)
def data_version() -> str:
    """Identifier of the published data: active run id and data date ("none" if unknown)."""
    try:
        run = _get("/api/v1/runs/active")
    except ApiError:
        return "none"
    return f"{run.get('training_run_id')}:{run.get('data_until')}"


def _versioned(func: Callable[..., Any]) -> Callable[..., Any]:
    """Cache func for CACHE_TTL with the data version as part of the key."""

    def cached(version: str, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    # st.cache_data keys on the function's qualified name: one distinct name per function.
    cached.__qualname__ = f"{func.__qualname__}__versioned"
    cached.__name__ = cached.__qualname__
    store = st.cache_data(ttl=CACHE_TTL, show_spinner=False)(cached)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return store(data_version(), *args, **kwargs)

    wrapper.clear = store.clear  # type: ignore[attr-defined]
    return wrapper


@_versioned
def countries() -> list[dict]:
    return _get("/api/v1/countries")


@_versioned
def commodities(country: str) -> list[dict]:
    return _get("/api/v1/commodities", {"country": country})


@_versioned
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


@_versioned
def markets(country: str) -> list[dict]:
    """Markets of a country with the coordinates published by WFP (None when absent)."""
    return _get("/api/v1/markets", {"country": country})


@_versioned
def history(series_id: int) -> dict:
    return _get(f"/api/v1/series/{series_id}/history")


@_versioned
def forecasts(series_id: int | None = None, country: str | None = None,
              commodity_group: str | None = None, horizon: int | None = None) -> dict:  # fmt: skip
    return _get(
        "/api/v1/forecasts",
        {"series_id": series_id, "country": country, "commodity_group": commodity_group,
         "horizon": horizon, "limit": 1000},
    )  # fmt: skip


@_versioned
def anomalies(country: str | None = None, commodity_group: str | None = None,
              series_id: int | None = None, since: str | None = None, limit: int = 1000) -> dict:  # fmt: skip
    return _get(
        "/api/v1/anomalies",
        {"country": country, "commodity_group": commodity_group, "series_id": series_id,
         "since": since, "limit": limit},
    )  # fmt: skip


@_versioned
def model_metrics(
    window: str, country: str | None = None, commodity_group: str | None = None
) -> dict:
    return _get(
        "/api/v1/models/metrics",
        {"window": window, "country": country, "commodity_group": commodity_group},
    )


@_versioned
def active_run() -> dict:
    return _get("/api/v1/runs/active")


def health() -> dict:
    try:
        return _get("/api/v1/health")
    except ApiError as exc:
        return {"status": "unreachable", "error": str(exc)}
