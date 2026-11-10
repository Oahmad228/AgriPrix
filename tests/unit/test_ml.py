"""Forecasting building blocks: no leakage, metrics, conformal intervals, champion rule."""

import math

import numpy as np
import pandas as pd
import pytest
from src.ml.data import Panel, calendar_id_of, month_index
from src.ml.evaluation import apply_interval, conformal_quantiles, select_champion, series_metrics
from src.ml.features import NUMERIC_FEATURES, build_supervised, seasonal_scale
from src.ml.models import MODEL_NAMES, make_model
from src.ml.train import _train_rows
from src.ml.windows import TEST_W3, VAL_W1


def make_panel(n_series: int = 3, months: int = 72, seed: int = 0, drop=()) -> Panel:
    rng = np.random.default_rng(seed)
    start = month_index(2019, 1)
    rows = []
    for sid in range(1, n_series + 1):
        level = 200 + 50 * sid
        for k in range(months):
            if (sid, k) in drop:
                continue
            seasonal = 1 + 0.1 * math.sin(2 * math.pi * (k % 12) / 12)
            rows.append(
                (sid, start + k, level * seasonal * (1 + 0.003 * k) * rng.lognormal(0, 0.02))
            )
    values = pd.DataFrame(rows, columns=["series_id", "month_idx", "value"])
    series = pd.DataFrame(
        {
            "series_id": range(1, n_series + 1),
            "country_iso3": "SEN",
            "commodity_group": "Millet",
            "commodity_code": ["WFP_73"] * n_series,
            "lean_season_months": "06,07,08,09",
        }
    )
    return Panel(series, values)


def test_calendar_conversion() -> None:
    assert calendar_id_of(month_index(2025, 9)) == 202509
    assert calendar_id_of(month_index(2025, 12) + 1) == 202601


def test_target_is_log_return_and_seasonal_naive_uses_last_year() -> None:
    panel = make_panel(n_series=1)
    data = build_supervised(panel, [1], horizon=3, lean_season="06,07,08,09")
    prices = panel.values.set_index("month_idx")["value"]
    row = data[data["month_idx"] == month_index(2021, 5)].iloc[0]
    assert row["target"] == pytest.approx(
        math.log(prices[month_index(2021, 8)] / prices[row.month_idx])
    )
    assert row["snaive_value"] == pytest.approx(prices[month_index(2020, 8)])
    assert row["target_in_lean_season"] == 1.0  # target month = August


def test_features_never_use_future_prices() -> None:
    panel = make_panel(n_series=2)
    origin = month_index(2021, 6)
    before = build_supervised(panel, [1, 2], 6, None)
    shocked = Panel(panel.series, panel.values.copy())
    future = shocked.values["month_idx"] > origin
    shocked.values.loc[future, "value"] *= 10  # rewrite the whole future
    after = build_supervised(shocked, [1, 2], 6, None)
    at_origin = lambda d: d[d["month_idx"] == origin].set_index("series_id")[NUMERIC_FEATURES]  # noqa: E731
    pd.testing.assert_frame_equal(at_origin(before), at_origin(after))


def test_missing_months_stay_missing() -> None:
    panel = make_panel(n_series=1, drop={(1, 30)})
    data = build_supervised(panel, [1], 1, None)
    missing_month = month_index(2019, 1) + 30
    assert missing_month not in set(data["month_idx"])  # no invented origin
    nxt = data[data["month_idx"] == missing_month + 1].iloc[0]
    assert np.isnan(nxt["lag_1"])  # lag on a missing month is NaN, not interpolated


def test_training_rows_exclude_targets_after_cutoff() -> None:
    panel = make_panel()
    data = build_supervised(panel, [1, 2, 3], 6, None)
    train = _train_rows(data, VAL_W1.cutoff)
    assert train["target_month_idx"].max() <= VAL_W1.cutoff
    assert (train["month_idx"] + 6 == train["target_month_idx"]).all()


def test_mase_scale_uses_only_in_sample_months() -> None:
    panel = make_panel(n_series=1)
    early = seasonal_scale(panel, [1], month_index(2021, 12))
    panel.values.loc[panel.values["month_idx"] > month_index(2021, 12), "value"] *= 3
    assert seasonal_scale(panel, [1], month_index(2021, 12)).equals(early)


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_models_fit_and_predict_positive_prices(name: str) -> None:
    panel = make_panel()
    data = build_supervised(panel, [1, 2, 3], 3, None)
    train = _train_rows(data, month_index(2022, 12))
    evaluate = data[
        data["target_month_idx"].isin(range(month_index(2023, 1), month_index(2023, 7)))
    ]
    predictions = make_model(name).fit(train).predict(evaluate)
    assert len(predictions) == len(evaluate)
    assert (predictions > 0).all()
    mape = np.mean(np.abs(predictions - evaluate["actual_value"]) / evaluate["actual_value"])
    assert mape < 0.2  # sanity on a smooth synthetic series


def test_series_metrics_definitions() -> None:
    group = pd.DataFrame(
        {
            "actual_value": [100.0, 200.0],
            "prediction": [110.0, 180.0],
            "snaive_value": [80.0, 240.0],
            "lower_80": [90.0, 150.0],
            "upper_80": [120.0, 190.0],
        }
    )
    m = series_metrics(group, scale=10.0)
    assert m["mae"] == 15.0
    assert m["rmse"] == pytest.approx(math.sqrt((100 + 400) / 2))
    assert m["mape"] == pytest.approx(10.0)
    assert m["mase"] == 1.5
    assert m["rel_mae"] == pytest.approx(15 / 30)
    assert m["picp_80"] == 0.5  # 200 is above the upper bound 190


def test_conformal_finite_sample_ranks() -> None:
    errors = np.arange(1, 20) / 100  # n = 19 -> ranks 2 and 18
    low, high = conformal_quantiles(errors)
    assert (low, high) == (0.02, 0.18)
    assert conformal_quantiles(np.array([0.05])) == (0.05, 0.05)
    with pytest.raises(ValueError):
        conformal_quantiles(np.array([]))


def test_conformal_coverage_on_exchangeable_errors() -> None:
    rng = np.random.default_rng(1)
    calib, test = rng.normal(0, 0.1, 2000), rng.normal(0, 0.1, 20000)
    low, high = conformal_quantiles(calib)
    coverage = np.mean((test >= low) & (test <= high))
    assert 0.78 <= coverage <= 0.84


def test_interval_lower_bound_never_negative() -> None:
    lower, upper = apply_interval(np.array([100.0]), -1.5, 0.2)
    assert lower[0] == 0.0
    assert upper[0] == pytest.approx(120.0)


def _metrics(mase: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([{"model_name": m, "rel_mae": 1.0, "mase": v} for m, v in mase.items()] * 3)


def test_champion_is_lowest_median_mase_baselines_included() -> None:
    mase = {"Naive": 1.0, "SeasonalNaive": 1.2, "Ridge_Seasonal": 0.95, "LightGBM_Global": 0.97}
    assert select_champion(_metrics(mase))[0] == "Ridge_Seasonal"


def test_persistence_wins_when_learned_models_do_not_beat_it() -> None:
    mase = {"Naive": 0.8, "SeasonalNaive": 1.2, "Ridge_Seasonal": 0.9, "LightGBM_Global": 0.85}
    name, _, median_mase, rule = select_champion(_metrics(mase))
    assert (name, median_mase) == ("Naive", 0.8)
    assert "baselines" not in rule or "ADR-010" in rule


def test_windows_never_overlap_test_with_selection() -> None:
    assert max(VAL_W1.eval_months) < min(TEST_W3.eval_months)


def test_ridge_never_extrapolates_beyond_training_returns() -> None:
    panel = make_panel()
    data = build_supervised(panel, [1, 2, 3], 1, None)
    train = _train_rows(data, month_index(2022, 12))
    model = make_model("Ridge_Seasonal").fit(train)
    extreme = data.tail(1).copy()
    extreme[NUMERIC_FEATURES[:5]] = 50.0  # lags 50 log-points away: never seen in training
    price = model.predict(extreme)[0]
    ratio = math.log(price / extreme["anchor_value"].iloc[0])
    assert train["target"].min() - 1e-9 <= ratio <= train["target"].max() + 1e-9
