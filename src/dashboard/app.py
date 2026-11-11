"""AgriPrix Observatory dashboard (Streamlit) — reads everything from the public API.

Run: streamlit run app.py (from src/dashboard, see docker-compose.yml).
Design contract: .impeccable/surfaces/dashboard.md ("Calendrier des saisons").
"""

from __future__ import annotations

from datetime import date

import httpx
import pandas as pd
import streamlit as st

from src.dashboard import charts, client
from src.dashboard.client import ApiError

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
    "Naive": "Dernier prix connu", "SeasonalNaive": "Même mois l'an passé",
    "Ridge_Seasonal": "Ridge saisonnier", "LightGBM_Global": "LightGBM (global)",
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


def default_focus(country_code: str, group: str) -> int | None:
    """Open the chart on the market of the most recent, strongest alert, if any."""
    country = next(c for c in client.countries() if c["country_iso3"] == country_code)
    items = client.anomalies(
        country=country_code, commodity_group=group, since=recent_since(country)
    )["items"]
    return items[0]["series_id"] if items else None


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
        "Pays", codes, index=codes.index("BFA") if "BFA" in codes else 0, format_func=names.get
    )
    country = next(c for c in countries if c["country_iso3"] == country_code)

    groups = sorted({c["commodity_group"] for c in client.commodities(country_code)},
                    key=lambda g: GROUP_FR.get(g, g))  # fmt: skip
    group = st.sidebar.selectbox("Produit", groups, format_func=lambda g: GROUP_FR.get(g, g))

    candidates = client.series(country_code, group)
    selected = None
    if candidates:
        labels = {
            s["series_id"]: f"{s['market_name']} — {commodity_fr(s['commodity_name_en'])}"
            if len({c['commodity_name_en'] for c in candidates}) > 1 else s["market_name"]
            for s in candidates
        }  # fmt: skip
        ids = sorted(labels, key=lambda i: labels[i])
        wanted = st.session_state.get("focus_series") or default_focus(country_code, group)
        index = ids.index(wanted) if wanted in ids else 0
        series_id = st.sidebar.selectbox("Marché", ids, index=index, format_func=labels.get)
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


def alerts_table(country: dict, group: str) -> None:
    latest = pd.Timestamp(country["max_observed_date"])
    since = recent_since(country)
    body = client.anomalies(country=country["country_iso3"], commodity_group=group, since=since)
    label = GROUP_FR.get(group, group).lower()
    st.markdown(f"### Alertes des trois derniers mois — {label}, {country['country_name_fr']}")
    if not body["items"]:
        st.markdown(
            f'<p class="ap-note">Aucune alerte entre {_month(since)} et {_month(latest)} : '
            "les prix relevés restent dans leur plage habituelle pour la saison. "
            "Choisissez un autre produit, ou consultez l'historique du marché ci-dessous.</p>",
            unsafe_allow_html=True,
        )
        return
    lean = country["lean_season_months"]
    candidates = client.series(country["country_iso3"], group)
    currency = candidates[0]["currency_code"] if candidates else "XOF"
    rows = []
    for a in body["items"]:
        period = pd.Timestamp(a["period"]).date()
        rows.append(
            {
                "series_id": a["series_id"],
                "Marché": a["market_name"],
                "Écart": a["deviation_pct"],
                "Sens": "Hausse" if a["direction"] == "UP" else "Baisse",
                "Gravité": "forte" if a["severity"] == "CRITICAL" else "modérée",
                "Mois": charts.month_label(period),
                "Soudure": "oui" if charts.in_lean_season(period, lean) else "non",
                "Produit": commodity_fr(a["commodity_name_en"]),
                "Prix relevé": a["observed_value"],
                "Niveau attendu": a["expected_value"],
            }
        )
    frame = pd.DataFrame(rows)
    st.markdown(
        f'<p class="ap-note">{body["total"]} alerte(s). Une alerte signale un prix éloigné de son niveau '
        "attendu compte tenu de la tendance de l'année écoulée et de la saison. "
        "Sélectionnez une ligne pour afficher ce marché.</p>",
        unsafe_allow_html=True,
    )
    event = st.dataframe(
        frame.drop(columns="series_id"),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Prix relevé": st.column_config.NumberColumn(format=number_format(currency)),
            "Niveau attendu": st.column_config.NumberColumn(format=number_format(currency)),
            "Écart": st.column_config.NumberColumn(format="%+.0f %%"),
        },
        height=min(38 + 35 * len(frame), 320),
    )
    picked = event.selection.rows if event and event.selection else []
    if picked:
        sid = int(frame.iloc[picked[0]]["series_id"])
        if st.session_state.get("focus_series") != sid:
            st.session_state["focus_series"] = sid
            st.rerun()


def market_view(country: dict, selected: dict | None) -> None:
    if selected is None:
        st.info("Aucune série de prix de détail pour ce produit dans ce pays.")
        return
    commodity = commodity_fr(selected["commodity_name_en"])
    st.markdown(f"### {commodity} à {selected['market_name']}")
    hist = client.history(selected["series_id"])
    if not hist["observations"]:
        st.info("Cette série ne contient encore aucun relevé.")
        return
    alerts = client.anomalies(series_id=selected["series_id"])["items"]
    forecast_items = []
    if selected["is_ml_eligible"]:
        forecast_items = client.forecasts(series_id=selected["series_id"])["items"]
    fig = charts.price_figure(
        hist["observations"], alerts, forecast_items, selected["unit_measure"],
        selected["currency_code"], country["lean_season_months"],
    )  # fmt: skip
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "fr"})

    if not forecast_items:
        reason = REASON_FR.get(selected.get("ineligibility_reason") or "", "données insuffisantes")
        st.markdown(f'<p class="ap-note">Pas de prévision pour cette série : {reason}.</p>',
                    unsafe_allow_html=True)  # fmt: skip
        return
    unit, currency = selected["unit_measure"], selected["currency_code"]
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
            "Couverture mesurée en test": [
                "—" if f["test_picp_80"] is None else f"{100 * f['test_picp_80']:.0f} %"
                for f in forecast_items
            ],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.markdown(
        '<p class="ap-note">La fourchette devrait contenir le vrai prix 8 fois sur 10. '
        "La couverture mesurée dit ce qu'il en a été sur la période de test pour ce groupe de "
        "marchés : en dessous de 80 %, la fourchette a été trop étroite. Voir l'onglet "
        "« Méthode & qualité ».</p>",
        unsafe_allow_html=True,
    )


def forecasts_tab(country: dict, group: str) -> None:
    horizon = st.radio("Horizon", [1, 3, 6], index=1, horizontal=True,
                       format_func=lambda h: f"{h} mois")  # fmt: skip
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
    return (
        "Chaque barre compare l'erreur d'un modèle à celle de la règle la plus simple : "
        "« le prix restera le dernier prix connu » ; au-dessus de zéro, le modèle fait mieux. "
        + role
        + " Sur cette période, "
        + " ; ".join(parts)
        + "."
    )


def method_tab() -> None:
    run = client.active_run()
    st.markdown("### Ce que valent les prévisions")
    window = st.radio("Période évaluée", list(WINDOWS), format_func=WINDOWS.get, horizontal=True)
    metrics = client.model_metrics(window)["items"]
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
        situation, by_market, method = st.tabs(
            ["Situation", "Prévisions par marché", "Méthode & qualité"]
        )
        with situation:
            alerts_table(country, group)
            market_view(country, selected)
        with by_market:
            forecasts_tab(country, group)
        with method:
            method_tab()
    except ApiError as exc:
        st.error(f"{exc} Les données s'afficheront dès que le service sera de nouveau disponible.")


if __name__ == "__main__":  # pragma: no cover
    main()
