"""Robust anomaly detector and catalog validation on synthetic data (runs in CI)."""

import numpy as np
import pandas as pd
import pytest
from src.anomaly.catalog import CATALOG, MIN_SHARE_OF_MARKETS, WARNING_Z
from src.anomaly.detector import alerts, robust_scores
from src.anomaly.validation import clopper_pearson, render, validate
from src.api.explain import explain_anomaly

START = 2000 * 12  # January 2000 as absolute month index


def seasonal_prices(n_series: int, months: int, seed: int = 0, noise: float = 0.03) -> pd.DataFrame:
    """Lean-season pattern (+8 % in August) + mild trend + log-normal noise."""
    rng = np.random.default_rng(seed)
    index = range(START, START + months)
    month = np.array([i % 12 for i in index])
    season = 0.08 * np.cos(2 * np.pi * (month - 7) / 12)
    data = {
        sid: 200 * np.exp(season + 0.002 * np.arange(months) + rng.normal(0, noise, months))
        for sid in range(1, n_series + 1)
    }
    return pd.DataFrame(data, index=index)


def test_seasonal_peak_is_not_an_anomaly() -> None:
    prices = seasonal_prices(5, 120)
    z = robust_scores(prices)["z"]
    august = z[[i % 12 == 7 for i in z.index]]
    assert (august.abs() < WARNING_Z).mean().mean() > 0.9


def test_injected_shock_is_critical_and_explained() -> None:
    prices = seasonal_prices(3, 120)
    shock_month = START + 100
    prices.loc[shock_month, 2] *= 1.6
    found = alerts(robust_scores(prices))
    hit = found[(found["series_id"] == 2) & (found["month_idx"] == shock_month)]
    assert len(hit) == 1
    row = hit.iloc[0]
    assert (row["direction"], row["severity"]) == ("UP", "CRITICAL")
    assert row["observed_value"] / row["expected_value"] == pytest.approx(1.6, rel=0.1)


def test_false_alarm_rate_on_quiet_series_is_low() -> None:
    z = robust_scores(seasonal_prices(30, 150, seed=3))["z"]
    rate = float((z.abs() >= WARNING_Z).sum().sum() / z.notna().sum().sum())
    assert rate < 0.05


def test_missing_months_are_not_scored() -> None:
    prices = seasonal_prices(1, 96)
    prices.loc[START + 50, 1] = np.nan
    z = robust_scores(prices)["z"]
    assert np.isnan(z.loc[START + 50, 1])


def test_catalog_is_well_formed() -> None:
    assert [e.code for e in CATALOG] == [f"SHOCK-0{i}" for i in range(1, 6)]
    for episode in CATALOG:
        assert episode.start <= episode.end
        assert episode.couples and episode.source.startswith("https://")


def test_clopper_pearson_matches_known_values() -> None:
    low, high = clopper_pearson(4, 4)
    assert (round(low, 3), high) == (0.398, 1.0)  # value quoted in ADR-003
    low, high = clopper_pearson(0, 5)
    assert low == 0.0 and high == pytest.approx(0.522, abs=1e-3)


def test_validation_counts_episode_as_detected_with_enough_markets() -> None:
    """Build a market panel for SHOCK-05 (Niger 2023-24) and check the 25 % rule."""
    episode = next(e for e in CATALOG if e.code == "SHOCK-05")
    n = 8
    prices = seasonal_prices(n, 12 * 30, seed=5)  # 2000..2029
    shock = episode.start[0] * 12 + episode.start[1] - 1 + 2
    hit = int(np.ceil(MIN_SHARE_OF_MARKETS * n))
    for sid in range(1, hit + 1):
        prices.loc[shock, sid] *= 1.5
    meta = pd.DataFrame(
        {
            "country_iso3": "NER",
            "commodity_group": "Rice",
            "market_code": [f"NER_{i}" for i in range(n)],
        },
        index=pd.Index(range(1, n + 1), name="series_id"),
    )
    result = validate(robust_scores(prices)["z"], meta)
    row = result.couples[
        (result.couples["episode"] == "SHOCK-05") & (result.couples["group"] == "Rice")
    ]
    assert bool(row["detected"].iloc[0])
    assert result.episodes.loc["SHOCK-05", "detected"]
    report = render(result, "test")
    assert "SHOCK-05" in report and "Rappel" in report


def test_explanation_for_a_price_drop_and_an_index() -> None:
    from datetime import date

    text = explain_anomaly(
        commodity="Consumer Prices, Food Indices (2015 = 100)",
        market="Maroc (national)",
        country="MAR",
        period=date(2022, 4, 1),
        observed=90.0,
        expected=100.0,
        currency="NONE",
        unit="INDEX_2015_100",
        severity="WARNING",
    )
    assert text.startswith("Alerte modérée : en avril 2022")
    assert "10 % en dessous" in text and "points" in text
