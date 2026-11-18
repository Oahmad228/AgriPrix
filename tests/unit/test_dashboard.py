"""Dashboard: season-band chart, plain-French texts, API errors and a full page render."""

from datetime import date
from pathlib import Path

import httpx
import pytest
from src.dashboard import charts, client, maps
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
     "country_iso3": "BFA", "model": "LightGBM_Global", "test_picp_80": 0.76, "last_value": 271.0,
     "recent_bias_pct": -14.0, "interval_method": "log_symmetric"}
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
    assert "(LightGBM)) fait mieux" in text and "10 % d'erreur en moins" in text
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


SERIES = {"series_id": 1, "country_iso3": "BFA", "market_code": "BFA_1", "market_name": "Djibo",
          "commodity_name_en": "Millet", "commodity_group": "Millet", "unit_measure": "KG",
          "currency_code": "XOF", "is_ml_eligible": True, "ineligibility_reason": None,
          "granularity_level": "MARKET", "last_obs_date": "2025-12-01", "last_value": 271.0}  # fmt: skip
NO_GPS = {**SERIES, "series_id": 2, "market_code": "BFA_2", "market_name": "Sans-GPS",
          "is_ml_eligible": False, "ineligibility_reason": "SHORT_CONTINUOUS_SEGMENT"}  # fmt: skip
NEAR = {
    **SERIES,
    "series_id": 3,
    "market_code": "BFA_3",
    "market_name": "Titao",
    "last_value": 250.0,
}
COUNTRY = {"country_iso3": "BFA", "country_name_fr": "Burkina Faso", "ml_eligible_series": 1,
           "max_observed_date": "2025-12-01", "lean_season_months": "06,07,08,09"}  # fmt: skip
FAKE_API = {
    "countries": lambda: [COUNTRY, {**COUNTRY, "country_iso3": "MLI", "country_name_fr": "Mali"}],
    "commodities": lambda country: [{"commodity_group": "Millet"}],
    "series": lambda country, group=None, frequency="MONTHLY": [SERIES, NO_GPS, NEAR],
    "markets": lambda country: [
        {"market_code": "BFA_1", "market_name": "Djibo", "latitude": 14.1, "longitude": -1.6},
        {"market_code": "BFA_2", "market_name": "Sans-GPS", "latitude": None, "longitude": None},
        {"market_code": "BFA_3", "market_name": "Titao", "latitude": 13.77, "longitude": -2.07},
    ],
    "history": lambda sid: {"observations": _history()},
    "forecasts": lambda **kw: {"items": [] if kw.get("series_id") == 2 else FORECASTS,
                               "data_until": "2025-12-01"},
    "anomalies": lambda **kw: {"items": [ALERT], "total": 1},
    "model_metrics": lambda window, **kw: {"items": [
        {"model_name": m, "horizon_months": h, "series": 1, "mape_pct": 9.0, "gain_vs_naive_pct": g,
         "picp_80": 0.8, "is_champion_share": 0.5}
        for m, g in (("Naive", 0.0), ("LightGBM_Global", 4.0)) for h in (1, 3, 6)]},
    "active_run": lambda: {"training_run_id": 6, "data_until": "2025-12-01", "ml_eligible_series": 782,
                           "anomalies": 22890, "git_sha": "abc1234"},
}  # fmt: skip


def _page(monkeypatch, page: str | None = None, **params) -> AppTest:
    """Run the app (home page), or one page file directly (AppTest cannot switch pages
    declared with st.navigation)."""
    for name, fake in FAKE_API.items():
        monkeypatch.setattr(client, name, fake)
    script = str(Path(APP).parent / page) if page else APP
    app = AppTest.from_file(script, default_timeout=30)
    for key, value in params.items():
        app.query_params[key] = value
    return app.run()


def _text(page: AppTest) -> str:
    return " ".join(m.value for m in page.markdown) + " ".join(t.value for t in page.title)


def _param(page: AppTest, key: str) -> str:
    value = page.query_params[key]
    return value[0] if isinstance(value, list) else value  # AppTest keeps a list per key


def test_home_answers_before_any_click(monkeypatch) -> None:
    page = _page(monkeypatch)
    assert not page.exception
    text = _text(page)
    assert "anormaux ce mois" in text  # title uses no-break hyphens
    assert "1 marché(s) sans coordonnées publiées ne sont pas sur la carte : Sans-GPS." in text
    assert "© contributeurs OpenStreetMap" in text
    # Alert block: market, symbol and deviation, sentence with the expected level.
    assert "300 XOF/kg, alors qu'environ 240 étaient attendus pour la saison." in text
    assert "▲ +25 %" in text and "en période de soudure" in text
    assert text.count("En préparation") >= 4 and "[à" not in text  # no value invented, no brackets
    assert "Plus fortes variations attendues dans 3 mois" in " ".join(
        h.value for h in page.subheader
    )
    assert "sans validation du WFP ni de la FAO" in text
    assert len(page.get("plotly_chart")) == 1  # the map
    assert (_param(page, "pays"), _param(page, "produit")) == ("BFA", "mil")


def test_market_sheet_sentence_badge_bias_and_neighbours(monkeypatch) -> None:
    page = _page(monkeypatch, "views/marche.py", pays="BFA", produit="mil", marche="1")
    assert not page.exception
    text = _text(page)
    assert "Mil à Djibo" in text
    assert "En août 2025, il était <b>25 % au-dessus de son niveau habituel</b>" in text
    assert "● Fiabilité correcte" in text
    assert "surestimé le prix de 14 %" in text  # |bias| >= 10 %: shown, never corrected
    assert "Titao" in text and "Sans-GPS" not in text.split("Marchés voisins")[-1]
    assert len(page.get("plotly_chart")) == 1
    assert _param(page, "marche") == "1"


def test_url_restores_the_view(monkeypatch) -> None:
    page = _page(monkeypatch, "views/marche.py", pays="BFA", produit="mil", marche="2",
                 h="6", periode="1an")  # fmt: skip
    assert not page.exception
    text = _text(page)
    assert "Mil à Sans-GPS" in text
    assert "moins de 60 mois de relevés continus" in text
    assert (_param(page, "h"), _param(page, "periode")) == ("6", "1an")


def test_country_switch_from_the_url_and_the_map(monkeypatch) -> None:
    page = _page(monkeypatch, pays="MLI", produit="mil")
    assert not page.exception
    assert "Carte des marchés · mil, Mali" in _text(page)
    assert _param(page, "pays") == "MLI"
    assert maps.clicked([{"location": "MLI", "curve_number": 0}]) == ("country", "MLI")
    assert maps.clicked([{"customdata": [7]}]) == ("market", 7)
    assert maps.clicked([]) is None
    # A marker sits on its country's area: the click opens the market, not the country.
    assert maps.clicked([{"location": "BFA"}, {"customdata": [7]}]) == ("market", 7)


def test_reliability_page_names_the_served_version(monkeypatch) -> None:
    page = _page(monkeypatch, "views/fiabilite.py")
    assert not page.exception
    assert "Campagne d'entraînement n° 6" in _text(page)


def test_page_shows_a_clear_message_when_the_api_is_down(monkeypatch) -> None:
    def down():
        raise client.ApiError("Le service de données ne répond pas pour le moment.")

    monkeypatch.setattr(client, "countries", down)
    page = AppTest.from_file(APP, default_timeout=30).run()
    assert not page.exception
    assert "ne répond pas" in page.error[0].value


def test_cached_answers_are_keyed_on_the_published_run(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(client, "_get", lambda path, params=None: calls.append(path) or [path])
    client.data_version.clear()
    versions = iter(["7:2026-09-01", "7:2026-09-01", "8:2026-10-01"])
    monkeypatch.setattr(client, "data_version", lambda: next(versions))
    client.countries.clear()
    client.countries()
    client.countries()  # same run: served from the cache
    assert calls == ["/api/v1/countries"]
    client.countries()  # new run published: fetched again at once
    assert calls == ["/api/v1/countries", "/api/v1/countries"]


def test_dark_mode_chosen_in_the_url_is_kept(monkeypatch) -> None:
    page = _page(monkeypatch, theme="sombre")
    assert not page.exception
    assert _param(page, "theme") == "sombre"  # survives the URL rewrite of the view
    assert [b.label for b in page.button if b.key == "theme_btn"] == ["Mode clair"]
    styles = " ".join(m.value for m in page.markdown)
    assert "#18231E" in styles and "prefers-color-scheme" not in styles  # dark palette (SPEC)
    page.button(key="theme_btn").click().run()
    assert _param(page, "theme") == "clair"


def test_system_mode_by_default(monkeypatch) -> None:
    page = _page(monkeypatch)
    assert "theme" not in page.query_params
    assert [b.label for b in page.button if b.key == "theme_btn"] == ["Mode sombre"]
    styles = " ".join(m.value for m in page.markdown)
    assert "#F6F4EE" in styles and "#18231E" not in styles  # outside a browser: light


@pytest.mark.parametrize(
    ("url", "cookie", "streamlit_kind", "expected"),
    [
        # 1. The URL wins over everything, including a contrary cookie or Streamlit memory.
        ("sombre", "light", "light", "dark"),
        ("clair", "dark", "dark", "light"),
        # 2. Without URL: the cookie (last button choice, else the system, set by the script).
        (None, "dark", "light", "dark"),
        (None, "light", "dark", "light"),
        # 3. First visit, no cookie yet: Streamlit's guess (the script reloads if it is wrong).
        (None, None, "dark", "dark"),
        (None, None, None, "light"),
        ("nonsense", "garbage", None, "light"),
    ],
)
def test_one_theme_decision(url, cookie, streamlit_kind, expected) -> None:
    from src.dashboard.common import decide_theme

    assert decide_theme(url, cookie, streamlit_kind) == expected


def test_theme_script_targets_the_app_document() -> None:
    from src.dashboard.common import THEME_COOKIE, theme_script

    script = theme_script("dark")
    assert "window.parent" not in script  # Streamlit Cloud runs the app in an iframe
    assert '"System"' not in script.split("wantedSt")[1].split(";")[0]  # never "System"
    assert THEME_COOKIE in script and 'const server = "dark"' in script
    assert "recent.length < 2" in script  # no reload loop


def test_loading_message_is_removed_once_the_page_is_drawn(monkeypatch) -> None:
    from src.dashboard.app import LOADING_HTML

    assert "Chargement des données" in LOADING_HTML and 'role="status"' in LOADING_HTML
    page = _page(monkeypatch)
    assert not page.exception
    assert "Chargement des données" not in " ".join(m.value for m in page.markdown)


def test_chart_legend_sits_in_a_reserved_bottom_margin() -> None:
    fig = charts.price_figure(_history(), [ALERT], FORECASTS, "KG", "XOF", "06,07,08,09")
    assert fig.layout.legend.yref == "container" and fig.layout.legend.yanchor == "bottom"
    assert fig.layout.margin.b >= 120  # room for the legend wrapped on a phone
