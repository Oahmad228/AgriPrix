"""Dashboard: season-band chart, plain-French texts, API errors and a full page render."""

from datetime import date
from pathlib import Path

import httpx
import pytest
from src.dashboard import charts, client
from src.dashboard.app import commodity_fr, gain_summary, number_format
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "src" / "dashboard" / "app.py")


def _history(months: int = 72) -> list[dict]:
    out = []
    for k in range(months):
        year, month = 2020 + k // 12, k % 12 + 1
        out.append({"period": f"{year}-{month:02d}-01", "value": 200.0 + k, "raw_value": 200.0 + k,
                    "raw_unit": "KG", "source_flag": "actual", "is_observed": True})  # fmt: skip
    return out


FORECASTS = [
    {"series_id": 1, "horizon_months": h, "origin_period": "2025-12-01",
     "target_period": f"2026-{h:02d}-01", "yhat": 280.0 + h, "lower_80": 250.0, "upper_80": 300.0 + h,
     "unit_measure": "KG", "currency_code": "XOF", "market_name": "Djibo", "commodity_name_en": "Millet",
     "country_iso3": "BFA", "model": "LightGBM_Global", "test_picp_80": 0.76, "last_value": 271.0}
    for h in (1, 3, 6)
]  # fmt: skip
ALERT = {"series_id": 1, "period": "2025-08-01", "observed_value": 300.0, "expected_value": 240.0,
         "deviation_pct": 25.0, "z_score_robust": 3.1, "yoy_change_pct": 30.0, "direction": "UP",
         "severity": "WARNING", "market_name": "Djibo", "commodity_name_en": "Millet",
         "country_iso3": "BFA", "explanation_fr": "Alerte modérée : …"}  # fmt: skip


def test_price_chart_uses_a_date_axis_and_draws_every_lean_season() -> None:
    fig = charts.price_figure(_history(), [ALERT], FORECASTS, "KG", "XOF", "06,07,08,09", years=5)
    assert fig.layout.xaxis.type == "date"  # regression: numeric axis hid every price
    bands = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(bands) == 6  # lean seasons 2020..2025 inside the 5-year window + forecast
    names = {t.name for t in fig.data}
    assert {"Prix relevé", "Prévision (1, 3 et 6 mois)", "Intervalle à 80 %",
            "Alerte : hausse anormale", "Période de soudure"} <= names  # fmt: skip
    alert_trace = next(t for t in fig.data if t.name == "Alerte : hausse anormale")
    assert alert_trace.marker.symbol == "triangle-up"  # shape, not only colour


def test_no_bands_where_no_lean_season_is_defined() -> None:
    fig = charts.price_figure(_history(), [], [], "INDEX_2015_100", "NONE", None)
    assert not [s for s in fig.layout.shapes if s.type == "rect"]
    assert fig.layout.yaxis.title.text == "indice (base 2015 = 100)"


def test_french_formatting_helpers() -> None:
    assert charts.fmt_value(1464.2, "KG", "XOF") == "1 464 XOF/kg"
    assert charts.fmt_value(104.25, "INDEX_2015_100", "NONE") == "104,2"
    assert charts.month_label(date(2022, 8, 1)) == "août 2022"
    assert charts.in_lean_season(date(2022, 8, 1), "06,07,08,09")
    assert not charts.in_lean_season(date(2022, 11, 1), "06,07,08,09")
    assert commodity_fr("Maize (white)") == "Maïs blanc"
    assert commodity_fr("Unknown item") == "Unknown item"
    assert (number_format("XOF"), number_format("NONE")) == ("%.0f", "%.1f")


def _metric(model: str, h: int, gain: float) -> dict:
    return {"model_name": model, "horizon_months": h, "gain_vs_naive_pct": gain}


def test_gain_summary_follows_the_numbers_of_the_selected_period() -> None:
    worse = [_metric("LightGBM_Global", h, -10.0) for h in (1, 3, 6)]
    text = gain_summary(worse, "TEST_W3_25_26")
    assert text.count("fait moins bien") == 3 and "10 % d'erreur en plus" in text
    assert "n'a servi qu'à évaluer" in text
    better = [_metric("Ridge_Seasonal", 3, 7.6), _metric("LightGBM_Global", 3, 9.9)]
    text = gain_summary(better, "VAL_W1_2022")
    assert "LightGBM (global)) fait mieux" in text and "10 % d'erreur en moins" in text
    assert "a servi à choisir" in text


@pytest.mark.parametrize(
    ("status", "message"),
    [(503, "pas encore calculées"), (429, "Trop de demandes"), (500, "code 500")],
)
def test_api_errors_become_plain_messages(monkeypatch, status: int, message: str) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(status, json={}))
    with pytest.raises(client.ApiError, match=message):
        client._get("/api/v1/countries")


def test_unreachable_api(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", boom)
    with pytest.raises(client.ApiError, match="ne répond pas"):
        client._get("/api/v1/countries")
    assert client.health()["status"] == "unreachable"


SERIES = {"series_id": 1, "market_name": "Djibo", "commodity_name_en": "Millet", "unit_measure": "KG",
          "currency_code": "XOF", "is_ml_eligible": True, "ineligibility_reason": None}  # fmt: skip
FAKE_API = {
    "countries": lambda: [{"country_iso3": "BFA", "country_name_fr": "Burkina Faso",
                           "ml_eligible_series": 1, "max_observed_date": "2025-12-01",
                           "lean_season_months": "06,07,08,09"}],
    "commodities": lambda country: [{"commodity_group": "Millet"}],
    "series": lambda country, group=None, frequency="MONTHLY": [SERIES],
    "history": lambda sid: {"observations": _history()},
    "forecasts": lambda **kw: {"items": FORECASTS, "data_until": "2025-12-01"},
    "anomalies": lambda **kw: {"items": [ALERT], "total": 1},
    "model_metrics": lambda window, **kw: {"items": [
        {"model_name": m, "horizon_months": h, "series": 1, "mape_pct": 9.0, "gain_vs_naive_pct": g,
         "picp_80": 0.8, "is_champion_share": 0.5}
        for m, g in (("Naive", 0.0), ("LightGBM_Global", 4.0)) for h in (1, 3, 6)]},
    "active_run": lambda: {"training_run_id": 6, "data_until": "2025-12-01", "ml_eligible_series": 782,
                           "anomalies": 22890, "git_sha": "abc1234"},
}  # fmt: skip


def test_full_page_renders_alerts_chart_and_method(monkeypatch) -> None:
    for name, fake in FAKE_API.items():
        monkeypatch.setattr(client, name, fake)
    page = AppTest.from_file(APP, default_timeout=30).run()
    assert not page.exception
    text = " ".join(m.value for m in page.markdown)
    assert "Alertes des trois derniers mois — mil, Burkina Faso" in text
    assert "Mil à Djibo" in text
    assert "Campagne d'entraînement n° 6" in text
    assert len(page.get("plotly_chart")) == 2  # price chart + model comparison
    assert [t.label for t in page.tabs] == [
        "Situation",
        "Prévisions par marché",
        "Méthode & qualité",
    ]


def test_page_shows_a_clear_message_when_the_api_is_down(monkeypatch) -> None:
    def down():
        raise client.ApiError("Le service de données ne répond pas pour le moment.")

    monkeypatch.setattr(client, "countries", down)
    page = AppTest.from_file(APP, default_timeout=30).run()
    assert not page.exception
    assert "ne répond pas" in page.error[0].value
