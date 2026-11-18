"""Interval methods comparison: calibrate on one window, measure on the next (ADR-004 §3)."""

import numpy as np
import pandas as pd
from src.ml.intervals_report import compare, render


def _rows(window: str, actual: list[float], prediction: float) -> pd.DataFrame:
    rows = []
    for horizon in (1, 3, 6):
        for value in actual:
            rows.append(
                {"eval_window": window, "country_iso3": "BFA", "commodity_group": "Maize",
                 "model_name": "Naive", "horizon_months": horizon, "actual_value": value,
                 "prediction": prediction}
            )  # fmt: skip
    return pd.DataFrame(rows)


def test_compare_uses_the_previous_window_for_calibration() -> None:
    # Calibration windows: the model always over-estimated (falling market).
    calib = [70.0, 75.0, 80.0, 85.0, 90.0, 92.0, 95.0, 97.0, 98.0]
    predictions = pd.concat(
        [
            _rows("CAL_W0_2021", calib, 100.0),
            _rows("VAL_W1_2022", [100.0, 110.0], 100.0),
            _rows("VAL_W2_24_25", calib, 100.0),
            _rows("TEST_W3_25_26", [100.0, 110.0], 100.0),
        ],
        ignore_index=True,
    )
    champions = pd.DataFrame(
        {"country_iso3": "BFA", "commodity_group": "Maize", "horizon_months": [1, 3, 6],
         "champion_model_name": "Naive"}
    )  # fmt: skip
    table = compare(predictions, champions)
    assert len(table) == 6  # 2 windows x 3 horizons
    row = table.iloc[0]
    # v1 interval lies entirely below the forecast: every forecast is outside it.
    assert row["prévisions hors de leur fourchette v1 (%)"] == 100.0
    assert row["biais médian de calibration (%)"] < 0
    assert row["couverture log-sym. (%)"] >= row["couverture v1 (%)"]
    assert "Comparaison des deux méthodes" in render(table, "test")
    assert np.isfinite(table["largeur médiane log-sym. (%)"]).all()
