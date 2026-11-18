"""AgriPrix Observatory dashboard (Streamlit) — reads everything from the public API.

Run: streamlit run app.py (from src/dashboard, see docker-compose.yml).
Design contract: .impeccable/surfaces/dashboard.md ("Calendrier des saisons").
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

# Streamlit Community Cloud runs this file without installing the project: make the
# repository root importable so that "src.dashboard" resolves (no effect in Docker).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.dashboard import charts, client, maps, reading  # noqa: E402
from src.dashboard.client import ApiError  # noqa: E402

PERIODS = {"1an": ("1 an", 1), "5ans": ("5 ans", 5), "tout": ("Tout", None)}

GROUP_FR = {
    "Rice": "Riz", "Millet": "Mil", "Sorghum": "Sorgho", "Maize": "Maïs", "Beans": "Niébé",
    "CPI_Food": "Indice des prix alimentaires",
}  # fmt: skip
COMMODITY_FR = {
    "Rice": "Riz", "Rice (imported)": "Riz importé", "Rice (local)": "Riz local",
    "Rice (paddy)": "Riz paddy", "Rice (denikassia, imported)": "Riz importé (Denikassia)",
    "Rice (ordinary, first quality)": "Riz ordinaire (1re qualité)",
    "Rice (ordinary, second quality)": "Riz ordinaire (2e qualité)",
    "Millet": "Mil", "Sorghum": "Sorgho", "Sorghum (white)": "Sorgho blanc",
    "Sorghum (local)": "Sorgho local", "Sorghum (imported)": "Sorgho importé",
    "Maize": "Maïs", "Maize (white)": "Maïs blanc", "Maize (local)": "Maïs local",
    "Maize (imported)": "Maïs importé", "Beans (niebe)": "Niébé", "Beans (haricot)": "Haricot",
    "Consumer Prices, Food Indices (2015 = 100)": "Indice des prix alimentaires (base 2015 = 100)",
}  # fmt: skip


def commodity_fr(name: str) -> str:
    return COMMODITY_FR.get(name, name)


def number_format(currency: str) -> str:
    """Prices in XOF/MAD are whole numbers; indices keep one decimal."""
    return "%.1f" if currency == "NONE" else "%.0f"


REASON_FR = {
    "STALE_LAST_OBSERVATION": "la série n'a plus de relevé récent",
    "SHORT_CONTINUOUS_SEGMENT": "moins de 60 mois de relevés continus",
    "NOT_RETAIL_PRICE": "ce n'est pas un prix de détail",
    "NO_OBSERVED_VALUE": "elle ne contient que des valeurs agrégées ou estimées",
    "NOT_IN_FOOD_BASKET": "le produit n'est pas dans le panier suivi",
    "ANNUAL_FREQUENCY": "c'est une série annuelle",
}
MODEL_FR = {
    "Naive": "Dernier prix connu (persistance)",
    "SeasonalNaive": "Même mois l'an passé (saisonnier naïf)",
    "Ridge_Seasonal": "Tendance et saison par marché (régression Ridge)",
    "LightGBM_Global": "Modèle appris sur tous les marchés (LightGBM)",
}  # fmt: skip
WINDOWS = {
    "TEST_W3_25_26": "Test final : sept. 2025 → août 2026",
    "VAL_W1_2022": "Choc de 2022 : janv. → déc. 2022",
    "VAL_W2_24_25": "Validation : juil. 2024 → juin 2025",
}
GITHUB = "https://github.com/Oahmad228/AgriPrix"
CSS = """
<style>
  [data-testid="stDataFrame"], [data-testid="stTable"] { font-variant-numeric: tabular-nums; }
  ::selection { background: #E9C46A; color: #1E2B24; }
  :focus-visible { outline: 2px solid #2A6F97 !important; outline-offset: 2px; }
  .ap-season { display: inline-block; padding: 0 .45rem; border-radius: .25rem;
               background: rgba(233, 196, 106, .45); font-size: .85rem; }
  .ap-note { color: #4E5A53; font-size: .92rem; max-width: 75ch; }
  section[data-testid="stSidebar"] .ap-note { color: #D8E3DD; }
  .ap-lead { font-size: 1.08rem; line-height: 1.55; max-width: 70ch; margin: .2rem 0 .6rem; }
  .ap-badge { display: inline-block; padding: .1rem .55rem; border: 1px solid #D6DDD8;
              border-radius: .25rem; font-size: .9rem; white-space: nowrap; }
  .ap-bias { color: #4E5A53; font-size: .92rem; max-width: 75ch; }
  /* Alert rows are buttons: whole row clickable, 44 px touch target, left-aligned text. */
  .st-key-alerts button { width: 100%; min-height: 44px; justify-content: flex-start;
                           text-align: left; font-variant-numeric: tabular-nums; }
  .st-key-alerts button p { text-align: left; }
</style>
"""


def fetch_api_health(api_base_url: str) -> dict[str, object]:
    """Query the FastAPI health endpoint over HTTP (kept for the smoke tests)."""
    try:
        response = httpx.get(f"{api_base_url}/api/v1/health", timeout=5.0)
        response.raise_for_status()
        return dict(response.json())
    except httpx.HTTPError as exc:
        return {"status": "unreachable", "error": str(exc)}


def _month(value: str | date | None) -> str:
    if not value:
        return "—"
    period = pd.Timestamp(value).date()
    return charts.month_label(period)


def _pct(value: float) -> str:
    return f"{value:+.0f} %".replace("-", "−")


def recent_since(country: dict) -> str:
    latest = pd.Timestamp(country["max_observed_date"])
    return (latest - pd.DateOffset(months=2)).date().isoformat()


def latest_alerts(country: dict, group: str) -> dict[int, dict]:
    """Most recent alert of each series over the last three months (strongest if tied)."""
    items = client.anomalies(
        country=country["country_iso3"], commodity_group=group, since=recent_since(country)
    )["items"]
    ordered = sorted(items, key=lambda a: (a["period"], abs(a["deviation_pct"])), reverse=True)
    best: dict[int, dict] = {}
    for a in ordered:
        best.setdefault(a["series_id"], {**a, "month_label": _month(a["period"])})
    return best


def default_focus(country: dict, group: str) -> int | None:
    """Open the sheet on the market of the strongest recent alert, if any."""
    alerts = latest_alerts(country, group)
    if not alerts:
        return None
    return max(alerts.values(), key=lambda a: abs(a["deviation_pct"]))["series_id"]


def _param(name: str) -> str | None:
    value = st.query_params.get(name)
    return value if value else None


def _index(options: list, wanted: object, fallback: object = None) -> int:
    for candidate in (wanted, fallback):
        if candidate in options:
            return options.index(candidate)
    return 0


def focus(series_id: int) -> None:
    """Open a market sheet: the URL is the single source of truth for the selected market."""
    if _param("marche") != str(series_id):
        st.query_params["marche"] = str(series_id)
        st.rerun()


def share_state(country: str, group: str, series_id: int | None, horizon: int, period: str) -> None:
    """Every view has its own URL: country, staple, market, horizon and period."""
    wanted = {"pays": country, "produit": group, "horizon": str(horizon), "periode": period}
    if series_id is not None:
        wanted["marche"] = str(series_id)
    if {k: st.query_params.get(k) for k in wanted} != wanted:
        st.query_params.update(wanted)


def sidebar() -> tuple[dict, str, dict | None]:
    """Filter rail: country, staple, market. Returns (country, group, selected series)."""
    st.sidebar.markdown("## AgriPrix")
    st.sidebar.markdown(
        '<p class="ap-note">Prix des denrées de base, alertes et prévisions à 1, 3 et 6 mois.</p>',
        unsafe_allow_html=True,
    )
    countries = [
        c for c in client.countries() if c["ml_eligible_series"] or c["country_iso3"] == "CIV"
    ]
    names = {c["country_iso3"]: c["country_name_fr"] for c in countries}
    codes = list(names)
    country_code = st.sidebar.selectbox(
        "Pays", codes, index=_index(codes, _param("pays"), "BFA"), format_func=names.get
    )
    country = next(c for c in countries if c["country_iso3"] == country_code)

    groups = sorted({c["commodity_group"] for c in client.commodities(country_code)},
                    key=lambda g: GROUP_FR.get(g, g))  # fmt: skip
    group = st.sidebar.selectbox(
        "Produit", groups, index=_index(groups, _param("produit")),
        format_func=lambda g: GROUP_FR.get(g, g),
    )  # fmt: skip

    candidates = client.series(country_code, group)
    selected = None
    if candidates:
        several = len({c["commodity_name_en"] for c in candidates}) > 1
        labels = {
            s["series_id"]: f"{s['market_name']} — {commodity_fr(s['commodity_name_en'])}"
            if several else s["market_name"]
            for s in candidates
        }  # fmt: skip
        ids = sorted(labels, key=lambda i: labels[i])
        raw = _param("marche")
        wanted = int(raw) if raw and raw.isdigit() else None
        if wanted not in ids:
            wanted = default_focus(country, group)
        series_id = st.sidebar.selectbox(
            "Marché", ids, index=_index(ids, wanted), format_func=labels.get
        )
        selected = next(s for s in candidates if s["series_id"] == series_id)

    st.sidebar.markdown(
        f'<p class="ap-note">Données jusqu\'à <b>{_month(country["max_observed_date"])}</b>. '
        "Mise à jour mensuelle.</p>"
        '<p class="ap-note">Sources : World Food Programme (WFP) via HDX, licence CC BY-IGO 3.0 ; '
        "FAOSTAT, FAO, licence CC BY 4.0. Alertes et prévisions calculées par AgriPrix "
        "Observatory, sans validation du WFP ni de la FAO.</p>",
        unsafe_allow_html=True,
    )
    return country, group, selected


def _price(value: float, unit: str) -> str:
    return f"{reading.fr_number(value)} {unit}"


def _hover(s: dict, unit: str, alert: dict | None, fc: dict | None) -> str:
    words = maps.STATES[alert["direction"] if alert else "NORMAL"][0]
    lines = [f"<b>{s['market_name']}</b> — {commodity_fr(s['commodity_name_en']).lower()}"]
    if s.get("last_value") is not None:
        lines.append(
            f"Dernier prix : {_price(s['last_value'], unit)} ({_month(s['last_obs_date'])})"
        )
    else:
        lines.append("Pas de relevé de terrain récent")
    if alert:
        lines.append(
            f"{words} : {_pct(alert['deviation_pct'])} par rapport au niveau habituel "
            f"({alert['month_label']})"
        )
    else:
        lines.append(f"{words} (aucune alerte ces trois derniers mois)")
    if fc:
        lines.append(
            f"Dans 3 mois ({_month(fc['target_period'])}) : environ {_price(fc['yhat'], unit)}, "
            f"entre {reading.fr_number(fc['lower_80'])} et {reading.fr_number(fc['upper_80'])}"
        )
        rel = reading.reliability(fc["test_picp_80"])
        if rel:
            lines.append(f"{rel.label} ({rel.detail})")
    else:
        lines.append("Pas de prévision pour ce marché")
    lines.append("<i>Cliquer pour ouvrir la fiche</i>")
    return "<br>".join(lines)


def market_points(
    country: dict, group: str, alerts: dict[int, dict]
) -> tuple[list[dict], list[str]]:
    """One point per market at its WFP coordinates; returns (points, markets without them)."""
    iso3 = country["country_iso3"]
    coords = {m["market_code"]: m for m in client.markets(iso3)}
    forecasts = {
        f["series_id"]: f
        for f in client.forecasts(country=iso3, commodity_group=group, horizon=3)["items"]
    }
    by_market: dict[str, list[dict]] = {}
    for s in client.series(iso3, group):
        if s["granularity_level"] == "MARKET":
            by_market.setdefault(s["market_code"], []).append(s)

    points, missing = [], []
    for code, series in by_market.items():
        place = coords.get(code)
        if not place or place["latitude"] is None or place["longitude"] is None:
            missing.append(series[0]["market_name"])
            continue
        # Representative series: the alerting one, else the most recent forecast one.
        alerting = [s for s in series if s["series_id"] in alerts]
        if alerting:
            s = max(alerting, key=lambda x: abs(alerts[x["series_id"]]["deviation_pct"]))
        else:
            s = max(series, key=lambda x: (x["series_id"] in forecasts, x["last_obs_date"] or ""))
        unit = charts.unit_label(s["unit_measure"], s["currency_code"])
        alert = alerts.get(s["series_id"])
        state = alert["direction"] if alert else "NORMAL"
        label = s["market_name"]
        if alert:
            word = "hausse" if state == "UP" else "baisse"
            label = f"{s['market_name']} : {word} {_pct(alert['deviation_pct'])}"
        points.append(
            {
                "series_id": s["series_id"], "latitude": place["latitude"],
                "longitude": place["longitude"], "state": state, "label": label,
                "hover": _hover(s, unit, alert, forecasts.get(s["series_id"])),
            }
        )  # fmt: skip
    return points, sorted(missing)


def map_block(country: dict, group: str, alerts: dict[int, dict]) -> None:
    points, missing = market_points(country, group, alerts)
    if not points:
        st.markdown('<p class="ap-note">Aucun marché localisé pour ce produit.</p>',
                    unsafe_allow_html=True)  # fmt: skip
        return
    key = f"map_{country['country_iso3']}_{group}"
    event = st.plotly_chart(
        maps.market_map(points, country["country_iso3"], height=440),
        key=key, on_select="rerun", selection_mode="points", width="stretch",
        config={"displayModeBar": False, "scrollZoom": True, "locale": "fr"},
    )  # fmt: skip
    chosen = None
    for point in event.selection.points if event and event.selection else []:
        data = point.get("customdata")
        if data:
            chosen = int(data[0] if isinstance(data, list) else data)
            break
    # A selection persists across reruns: act only when it changes.
    if chosen != st.session_state.get(f"{key}_done"):
        st.session_state[f"{key}_done"] = chosen
        if chosen is not None:
            focus(chosen)
    note = f"{len(points)} marchés placés aux coordonnées publiées par le WFP."
    if missing:
        note += (
            f" {len(missing)} marché(s) sans coordonnées publiées ne sont pas sur la carte : "
            + ", ".join(missing)
            + "."
        )
    st.markdown(f'<p class="ap-note">{note}<br>{maps.ATTRIBUTION}.</p>', unsafe_allow_html=True)


def alerts_list(country: dict, group: str, alerts: dict[int, dict]) -> None:
    latest = pd.Timestamp(country["max_observed_date"])
    since = recent_since(country)
    st.markdown("#### Alertes récentes")
    if not alerts:
        st.markdown(
            f'<p class="ap-note">Aucune alerte entre {_month(since)} et {_month(latest)} : '
            "les prix relevés restent dans leur plage habituelle pour la saison.</p>",
            unsafe_allow_html=True,
        )
        return
    lean = country["lean_season_months"]
    ordered = sorted(alerts.values(), key=lambda a: abs(a["deviation_pct"]), reverse=True)
    st.markdown(
        f'<p class="ap-note">{len(ordered)} marché(s) en alerte entre {_month(since)} et '
        f"{_month(latest)}. Une alerte signale un prix éloigné de son niveau habituel pour la "
        "saison. Touchez une ligne pour ouvrir la fiche du marché.</p>",
        unsafe_allow_html=True,
    )
    with st.container(key="alerts"):
        for a in ordered:
            period = pd.Timestamp(a["period"]).date()
            word = "▲ Hausse" if a["direction"] == "UP" else "▼ Baisse"
            strength = "forte" if a["severity"] == "CRITICAL" else "modérée"
            season = " · soudure" if charts.in_lean_season(period, lean) else ""
            text = (
                f"{word} {_pct(a['deviation_pct'])} · {a['market_name']} · "
                f"{a['month_label']}{season} · alerte {strength}"
            )
            if st.button(text, key=f"alert_{a['series_id']}", width="stretch"):
                focus(a["series_id"])


def situation_tab(country: dict, group: str, selected: dict | None, horizon: int) -> str:
    alerts = latest_alerts(country, group)
    st.markdown(
        f"### {GROUP_FR.get(group, group)}, {country['country_name_fr']} : "
        "où les prix s'écartent-ils de la normale ?"
    )
    left, right = st.columns([3, 2], gap="medium")
    with left:
        map_block(country, group, alerts)
    with right:
        alerts_list(country, group, alerts)
    return market_view(country, selected, alerts, horizon)


def _last_observed(observations: list[dict]) -> tuple[float | None, str]:
    measured = [o for o in observations if o["is_observed"]]
    if not measured:
        return None, "—"
    last = max(measured, key=lambda o: o["period"])
    return last["value"], _month(last["period"])


def _reading(selected: dict, hist: dict, alert: dict | None, chosen: dict | None,
             unit_text: str, horizon: int) -> None:  # fmt: skip
    """Summary sentence, reliability badge in words, bias sentence (a sentence before a number)."""
    value, month = _last_observed(hist["observations"])
    lead = reading.situation_sentence(value, unit_text, month, alert)
    if chosen:
        lead += " " + reading.forecast_sentence(chosen, unit_text, _month(chosen["target_period"]))
    st.markdown(f'<p class="ap-lead">{lead}</p>', unsafe_allow_html=True)
    if not chosen:
        return
    rel = reading.reliability(chosen["test_picp_80"])
    if rel:
        st.markdown(
            f'<p><span class="ap-badge">{rel.label}</span> '
            f'<span class="ap-note">{rel.detail} à {horizon} mois (cible : 80).</span></p>',
            unsafe_allow_html=True,
        )
    bias = reading.bias_sentence(chosen.get("recent_bias_pct"), horizon)
    if bias:
        st.markdown(f'<p class="ap-bias">{bias}</p>', unsafe_allow_html=True)


def _forecast_table(forecast_items: list[dict], unit: str, currency: str) -> None:
    table = pd.DataFrame(
        {
            "Horizon": [f"{f['horizon_months']} mois" for f in forecast_items],
            "Mois visé": [_month(f["target_period"]) for f in forecast_items],
            "Prévision": [charts.fmt_value(f["yhat"], unit, currency) for f in forecast_items],
            "Fourchette à 80 %": [
                f"{charts.fmt_value(f['lower_80'], unit, currency)} – "
                f"{charts.fmt_value(f['upper_80'], unit, currency)}"
                for f in forecast_items
            ],
            "Fiabilité": [
                r.label if (r := reading.reliability(f["test_picp_80"])) else "—"
                for f in forecast_items
            ],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.markdown(
        '<p class="ap-note">La fourchette devrait contenir le vrai prix 8 fois sur 10. '
        "La fiabilité dit ce qu'il en a été sur la période de test pour ce groupe de marchés : "
        "correcte à partir de 70 fois sur 100, moyenne de 50 à 69, faible en dessous. "
        "Voir l'onglet « Méthode & qualité ».</p>",
        unsafe_allow_html=True,
    )


def market_view(country: dict, selected: dict | None, alerts: dict[int, dict], horizon: int) -> str:
    """Market sheet: the reading in words first, then the chart and the forecast table.

    Returns the period key chosen for the chart (for the shareable URL).
    """
    period_keys = list(PERIODS)
    period = _param("periode") if _param("periode") in PERIODS else "5ans"
    if selected is None:
        st.info("Aucune série de prix de détail pour ce produit dans ce pays.")
        return period
    with st.container(border=True):
        commodity = commodity_fr(selected["commodity_name_en"])
        st.markdown(f"### {commodity} à {selected['market_name']}")
        hist = client.history(selected["series_id"])
        if not hist["observations"]:
            st.info("Cette série ne contient encore aucun relevé.")
            return period
        unit, currency = selected["unit_measure"], selected["currency_code"]
        forecast_items = []
        if selected["is_ml_eligible"]:
            forecast_items = client.forecasts(series_id=selected["series_id"])["items"]
        chosen = next((f for f in forecast_items if f["horizon_months"] == horizon), None)
        _reading(selected, hist, alerts.get(selected["series_id"]), chosen,
                 charts.unit_label(unit, currency), horizon)  # fmt: skip
        if not forecast_items:
            reason = REASON_FR.get(
                selected.get("ineligibility_reason") or "", "données insuffisantes"
            )
            st.markdown(f'<p class="ap-note">Pas de prévision pour cette série : {reason}.</p>',
                        unsafe_allow_html=True)  # fmt: skip

        period = st.radio(
            "Période affichée", period_keys, index=period_keys.index(period),
            format_func=lambda k: PERIODS[k][0], horizontal=True, key="period_radio",
        )  # fmt: skip
        fig = charts.price_figure(
            hist["observations"], client.anomalies(series_id=selected["series_id"])["items"],
            forecast_items, unit, currency, country["lean_season_months"],
            years=PERIODS[period][1],
        )  # fmt: skip
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "fr"})
        if forecast_items:
            _forecast_table(forecast_items, unit, currency)
    return period


def forecasts_tab(country: dict, group: str, horizon: int) -> None:
    st.radio("Horizon", [1, 3, 6], index=[1, 3, 6].index(horizon), horizontal=True,
             format_func=lambda h: f"{h} mois", key="horizon_radio")  # fmt: skip
    body = client.forecasts(country=country["country_iso3"], commodity_group=group, horizon=horizon)
    if not body["items"]:
        st.markdown(
            '<p class="ap-note">Aucune prévision pour ce produit dans ce pays : les séries '
            "disponibles ne remplissent pas les conditions (relevés récents, 60 mois continus).</p>",
            unsafe_allow_html=True,
        )
        return
    rows = []
    for f in body["items"]:
        last = f["last_value"]
        rel = reading.reliability(f["test_picp_80"])
        rows.append(
            {
                "Marché": f["market_name"],
                "Produit": commodity_fr(f["commodity_name_en"]),
                "Dernier prix": last,
                "Mois visé": _month(f["target_period"]),
                "Prévision": f["yhat"],
                "Basse (80 %)": f["lower_80"],
                "Haute (80 %)": f["upper_80"],
                "Variation attendue": None if not last else (f["yhat"] / last - 1) * 100,
                "Fiabilité": rel.label if rel else "—",
            }
        )
    frame = pd.DataFrame(rows).sort_values("Variation attendue", ascending=False)
    unit = charts.unit_label(body["items"][0]["unit_measure"], body["items"][0]["currency_code"])
    st.markdown(
        f'<p class="ap-note">{len(frame)} marché(s), prix en {unit}. « Dernier prix » : le relevé '
        "le plus récent de chaque marché, point de départ de sa prévision. "
        "Tri : plus forte hausse attendue d'abord.</p>",
        unsafe_allow_html=True,
    )
    money = st.column_config.NumberColumn(format=number_format(body["items"][0]["currency_code"]))
    st.dataframe(
        frame, hide_index=True, width="stretch",
        column_config={c: money for c in ("Dernier prix", "Prévision", "Basse (80 %)", "Haute (80 %)")}
        | {"Variation attendue": st.column_config.NumberColumn(format="%+.1f %%")},
    )  # fmt: skip


def gain_summary(metrics: list[dict], window: str) -> str:
    """Plain-French reading of the chart, computed from the selected period's numbers."""
    learned = [m for m in metrics if m["model_name"] in ("LightGBM_Global", "Ridge_Seasonal")]
    parts = []
    for horizon in (1, 3, 6):
        best = max((m for m in learned if m["horizon_months"] == horizon),
                   key=lambda m: m["gain_vs_naive_pct"], default=None)  # fmt: skip
        if best is None:
            continue
        verb = "fait mieux" if best["gain_vs_naive_pct"] > 0 else "fait moins bien"
        parts.append(
            f"à {horizon} mois, le meilleur modèle appris ({MODEL_FR[best['model_name']]}) {verb} "
            f"que le dernier prix connu ({abs(best['gain_vs_naive_pct']):.0f} % d'erreur en moins)"
            if best["gain_vs_naive_pct"] > 0
            else f"à {horizon} mois, le meilleur modèle appris ({MODEL_FR[best['model_name']]}) {verb} "
            f"que le dernier prix connu ({abs(best['gain_vs_naive_pct']):.0f} % d'erreur en plus)"
        )
    role = (
        "Cette période n'a servi qu'à évaluer les modèles, choisis sur 2022 et 2024-2025."
        if window.startswith("TEST")
        else "Cette période a servi à choisir les modèles."
    )
    return role + " Sur cette période, " + " ; ".join(parts) + "."


GAIN_INTRO = (
    "Chaque barre compare l'erreur d'un modèle à celle de la règle la plus simple, "
    "« le prix restera le dernier prix connu » : au-dessus de zéro, le modèle fait mieux."
)


def method_tab() -> None:
    run = client.active_run()
    st.markdown("### Ce que valent les prévisions")
    window = st.radio("Période évaluée", list(WINDOWS), format_func=WINDOWS.get, horizontal=True)
    metrics = client.model_metrics(window)["items"]
    st.markdown(f'<p class="ap-lead">{GAIN_INTRO}</p>', unsafe_allow_html=True)
    st.plotly_chart(charts.gain_figure(metrics), width="stretch",
                    config={"displayModeBar": False})  # fmt: skip
    st.markdown(f'<p class="ap-note">{gain_summary(metrics, window)}</p>', unsafe_allow_html=True)
    coverage = pd.DataFrame(
        [
            {
                "Modèle": MODEL_FR.get(m["model_name"], m["model_name"]),
                "Horizon": f"{m['horizon_months']} mois",
                "Séries": m["series"],
                "Erreur moyenne (%)": round(m["mape_pct"], 1),
                "Écart vs dernier prix connu (%)": round(m["gain_vs_naive_pct"], 1),
                "Couverture de la fourchette à 80 % (%)": None
                if m["picp_80"] is None
                else round(100 * m["picp_80"], 1),
                "Retenu dans (% des groupes)": round(100 * m["is_champion_share"]),
            }
            for m in metrics
        ]
    )
    st.dataframe(coverage, hide_index=True, width="stretch")

    st.markdown("### Comment une alerte est décidée")
    st.markdown(
        '<p class="ap-note">Pour chaque marché, le niveau attendu d\'un mois combine la médiane des '
        "douze mois précédents et l'effet habituel de ce mois de l'année. L'écart est rapporté à la "
        "variabilité habituelle du marché ; au-delà de 2,5 fois cette variabilité, c'est une alerte "
        "modérée, au-delà de 3,5 fois une alerte forte. Validé sur cinq crises documentées "
        "(2008, 2012, 2020, 2022, 2023-2024) avec des critères publiés avant le calcul : "
        f'<a href="{GITHUB}/blob/main/docs/results/anomaly-validation.md">rapport de validation</a>.</p>',
        unsafe_allow_html=True,
    )
    st.markdown("### Version servie")
    st.markdown(
        f"<p class=\"ap-note\">Campagne d'entraînement n° {run['training_run_id']}, données jusqu'à "
        f"{_month(run['data_until'])}, {run['ml_eligible_series']} séries prévues, "
        f"{run['anomalies']} alertes historiques, code <code>{run['git_sha']}</code>. "
        f'Code source et rapports : <a href="{GITHUB}">{GITHUB}</a>.</p>',
        unsafe_allow_html=True,
    )


def main() -> None:
    """Render the AgriPrix Observatory dashboard."""
    st.set_page_config(page_title="AgriPrix Observatory", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        country, group, selected = sidebar()
        # The horizon radio lives in the second tab but the sheet of the first tab uses it:
        # read its value (or the URL's) before any tab renders.
        raw = _param("horizon")
        horizon = st.session_state.get("horizon_radio", int(raw) if raw in ("1", "3", "6") else 3)
        situation, by_market, method = st.tabs(
            ["Situation", "Prévisions par marché", "Méthode & qualité"]
        )
        with situation:
            period = situation_tab(country, group, selected, horizon)
        with by_market:
            forecasts_tab(country, group, horizon)
        with method:
            method_tab()
        share_state(
            country["country_iso3"], group, selected["series_id"] if selected else None,
            horizon, period,
        )  # fmt: skip
    except ApiError as exc:
        st.error(f"{exc} Les données s'afficheront dès que le service sera de nouveau disponible.")


if __name__ == "__main__":  # pragma: no cover
    main()
