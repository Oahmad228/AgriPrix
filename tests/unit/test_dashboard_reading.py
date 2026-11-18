"""Plain-French readings and the market map: every word comes from an API number."""

import pandas as pd
import pytest
from src.dashboard import charts, maps, reading


@pytest.mark.parametrize(
    ("coverage", "word", "symbol"),
    [(0.80, "correcte", "●"), (0.70, "correcte", "●"), (0.6999, "moyenne", "◐"),
     (0.50, "moyenne", "◐"), (0.24, "faible", "○"), (0.0, "faible", "○")],
)  # fmt: skip
def test_reliability_thresholds(coverage: float, word: str, symbol: str) -> None:
    level = reading.reliability(coverage)
    assert (level.word, level.symbol) == (word, symbol)
    assert level.label == f"{symbol} Fiabilité {word}"
    assert f"{round(100 * coverage)} fois sur 100" in level.detail


def test_no_badge_without_a_measured_coverage() -> None:
    assert reading.reliability(None) is None


def test_bias_sentence_only_from_ten_percent_either_way() -> None:
    assert reading.bias_sentence(None, 6) is None
    assert reading.bias_sentence(-9.9, 6) is None
    over = reading.bias_sentence(-21.4, 6)
    assert "surestimé le prix de 21 %" in over and "à 6 mois" in over
    assert "n'est pas corrigée" in over
    assert "sous-estimé le prix de 12 %" in reading.bias_sentence(12.0, 3)


def test_situation_and_forecast_sentences() -> None:
    assert "Aucun relevé" in reading.situation_sentence(None, "XOF/kg", "—", None)
    calm = reading.situation_sentence(1250.0, "XOF/kg", "sept. 2026", None)
    assert "1 250 XOF/kg en sept. 2026" in calm and "plage habituelle" in calm
    alert = {"deviation_pct": -24.6, "observed_value": 220.0, "month_label": "juil. 2026"}
    low = reading.situation_sentence(227.0, "XOF/kg", "sept. 2026", alert)
    assert low == (
        "Dernier prix relevé : 227 XOF/kg en sept. 2026. En juil. 2026, il était "
        "25 % sous son niveau habituel pour la saison (220 XOF/kg)."
    )
    same = reading.situation_sentence(220.0, "XOF/kg", "juil. 2026", alert)
    assert same.startswith("Le prix est 25 % sous son niveau habituel pour la saison (220")
    forecast = {"horizon_months": 6, "yhat": 202.4, "lower_80": 140.0, "upper_80": 290.0}
    text = reading.forecast_sentence(forecast, "XOF/kg", "mars 2027")
    assert "Dans 6 mois (mars 2027)" in text and "entre 140 et 290 XOF/kg" in text
    assert reading.fr_number(-1234.5, 1) == "−1 234,5"


def _point(sid: int, lat: float, lon: float, state: str) -> dict:
    return {"series_id": sid, "latitude": lat, "longitude": lon, "state": state,
            "label": f"m{sid}", "hover": f"<b>m{sid}</b>"}  # fmt: skip


def test_market_map_uses_osm_tiles_borders_and_states() -> None:
    points = [_point(1, 12.37, -1.53, "NORMAL"), _point(2, 13.58, -2.42, "DOWN"),
              _point(3, 14.03, -0.03, "UP")]  # fmt: skip
    fig = maps.market_map(points, "BFA")
    assert fig.layout.map.style == "open-street-map"
    # Colour AND word in the legend (the symbol is in the word, the hover and the alert list).
    names = [t.name for t in fig.data]
    assert names == ["▲ Hausse anormale", "▼ Baisse anormale", "● Prix dans la normale"]
    colours = {t.name: t.marker.color for t in fig.data}
    assert colours["▲ Hausse anormale"] == maps.ALERT_UP != colours["▼ Baisse anormale"]
    # A click gives back the series id.
    assert fig.data[0].customdata[0][0] == 3
    # Country outline + Burkina Faso regions, drawn under the markets.
    layers = fig.layout.map.layers
    assert len(layers) == 2 and all(layer.below == "traces" for layer in layers)
    centre = fig.layout.map.center
    assert 12 < centre.lat < 14.1 and -2.5 < centre.lon < 0
    assert 3 <= fig.layout.map.zoom <= 9


def test_map_without_border_file_still_renders() -> None:
    fig = maps.market_map([_point(1, 33.6, -7.6, "NORMAL")], "MAR")
    assert not fig.layout.map.layers
    assert fig.layout.map.zoom == 7.64  # one market: extent floored at 1 degree


def test_date_axis_labels_every_year_or_quarter() -> None:
    short = charts._date_ticks(pd.Timestamp("2025-09-01"), pd.Timestamp("2026-12-01"))
    assert short["ticktext"][:2] == ["oct.<br>2025", "janv.<br>2026"]  # French, every quarter
    assert len(short["tickvals"]) == 5  # oct. 2025 to oct. 2026
    five = charts._date_ticks(pd.Timestamp("2021-09-01"), pd.Timestamp("2027-03-01"))
    assert five == {"dtick": "M12", "tick0": "2021-01-01", "tickformat": "%Y"}
    assert (
        charts._date_ticks(pd.Timestamp("2000-01-01"), pd.Timestamp("2027-01-01"))["dtick"] == "M48"
    )
