"""Shared labels, view state (the URL) and data blocks of the dashboard pages."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from src.dashboard import charts, client, maps, reading
from src.dashboard import tokens as tk

GITHUB = "https://github.com/Oahmad228/AgriPrix"
HOME, MARKET = "views/home.py", "views/marche.py"
ALL = "ALL"
COUNTRY_ORDER = ["BFA", "MLI", "NER", "SEN", "CIV", "MAR"]  # mockup order
PERIODS = {"1an": ("1 an", 1), "5ans": ("5 ans", 5), "tout": ("Tout", None)}

GROUP_FR = {
    "Rice": "Riz", "Millet": "Mil", "Sorghum": "Sorgho", "Maize": "Maïs", "Beans": "Niébé",
    "CPI_Food": "Indice des prix alimentaires",
}  # fmt: skip
GROUP_SLUG = {"Maize": "mais", "Millet": "mil", "Rice": "riz", "Sorghum": "sorgho",
              "Beans": "niebe", "CPI_Food": "indice"}  # fmt: skip
SLUG_GROUP = {v: k for k, v in GROUP_SLUG.items()}
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
SOURCES_HTML = (
    "Source : World Food Programme (WFP) via HDX, CC BY-IGO 3.0 · FAOSTAT, FAO, CC BY 4.0. "
    "Alertes et prévisions calculées par AgriPrix, sans validation du WFP ni de la FAO."
)
# Outside factors: not in the warehouse yet, so no value is shown (never an invented one).
# (title, what the block will show once the data is loaded and checked, source)
FACTORS = (
    ("Pluie de la saison vs normale",
     "Cumul de pluie de la saison comparé aux années passées, par région.",
     "CHIRPS, Climate Hazards Center"),
    ("Récolte céréalière estimée",
     "Production estimée de la campagne en cours, comparée à la moyenne.",
     "CILSS (PREGEC), FAO (GIEWS)"),
    ("Prix du carburant",
     "Prix du carburant à la pompe et son évolution sur un an.",
     "WFP"),
    ("Décisions d'exportation",
     "Fermetures de frontière et interdictions d'exporter, datées.",
     "Rapports FEWS NET"),
)  # fmt: skip
SOON = "En préparation"


def factor_card(label: str, what: str, source: str) -> str:
    """A factor block without data: what it will show, its source, a sober status."""
    return (
        f'<p class="ap-factor-label">{label}</p>'
        f'<p><span class="ap-soon">{SOON}</span></p>'
        f'<p class="ap-factor-what">{what}</p>'
        f'<p class="ap-factor-source">Source prévue : {source}</p>'
    )


def commodity_fr(name: str) -> str:
    return COMMODITY_FR.get(name, name)


def number_format(currency: str) -> str:
    """Prices in XOF/MAD are whole numbers; indices keep one decimal."""
    return "%.1f" if currency == "NONE" else "%.0f"


def month(value: str | date | None) -> str:
    if not value:
        return "—"
    return charts.month_label(pd.Timestamp(value).date())


def pct(value: float, decimals: int = 0) -> str:
    return f"{value:+.{decimals}f} %".replace("-", "−").replace(".", ",")


def price(value: float, unit: str) -> str:
    return f"{reading.fr_number(value)} {unit}"


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


# --- View state: the URL is the source of truth ------------------------------------------


@dataclass(frozen=True)
class View:
    country: str | None  # ISO3, None = every covered country ("Tous")
    group: str
    series_id: int | None
    horizon: int
    period: str

    def params(self) -> dict[str, str]:
        out = {"pays": self.country or "tous", "produit": GROUP_SLUG.get(self.group, self.group),
               "h": str(self.horizon), "periode": self.period}  # fmt: skip
        if self.series_id is not None:
            out["marche"] = str(self.series_id)
        if forced_theme():
            out["theme"] = param("theme")
        return out


def param(name: str) -> str | None:
    value = st.query_params.get(name)
    return value if value else None


def restore_params() -> None:
    """The top navigation drops the query string: bring back the last view."""
    if not st.query_params and st.session_state.get("view_params"):
        st.query_params.from_dict(st.session_state["view_params"])


def share(view: View) -> None:
    wanted = view.params()
    st.session_state["view_params"] = wanted
    if {k: st.query_params.get(k) for k in wanted} != wanted or "horizon" in st.query_params:
        st.query_params.clear()
        st.query_params.update(wanted)


def view_url(view: View, page: str = "") -> str:
    base = (st.context.url or "").split("?")[0].rstrip("/")
    for suffix in ("/marches", "/facteurs", "/fiabilite", "/donnees"):
        base = base.removesuffix(suffix)
    return f"{base}/{page}?{urlencode(view.params())}"


def covered_countries() -> list[dict]:
    """Countries with forecast series, plus Côte d'Ivoire and Morocco (consultation only)."""
    rows = [c for c in client.countries()
            if c["ml_eligible_series"] or c["country_iso3"] in ("CIV", "MAR")]  # fmt: skip
    order = {iso: i for i, iso in enumerate(COUNTRY_ORDER)}
    return sorted(rows, key=lambda c: order.get(c["country_iso3"], 99))


def _index(options: list, wanted: object, fallback: object = None) -> int:
    for candidate in (wanted, fallback):
        if candidate in options:
            return options.index(candidate)
    return 0


def groups_for(countries: list[dict]) -> list[str]:
    found = {g["commodity_group"] for c in countries for g in client.commodities(c["country_iso3"])}
    return sorted(found, key=lambda g: (g == "CPI_Food", GROUP_FR.get(g, g)))


def filter_bar(*, with_market: bool) -> tuple[View, list[dict], list[dict]]:
    """Pills for the country, list for the staple (and the market on a market sheet).

    Returns (view, covered countries, selected countries). Widgets take their value from the
    URL, so a shared link, a map click or a pill all lead to the same state.
    """
    countries = covered_countries()
    names = {c["country_iso3"]: c["country_name_fr"] for c in countries}
    raw_country = (param("pays") or "BFA").upper()
    if with_market and raw_country == "TOUS":
        raw_country = "BFA"
    with st.container(key="filters"):
        pills_col, *cols = st.columns([3, 1, 1.4] if with_market else [4, 1], gap="medium")
        options = list(names) if with_market else [ALL, *names]
        wanted = ALL if raw_country == "TOUS" else raw_country
        choice = pills_col.pills(
            "Pays", options, default=options[_index(options, wanted, "BFA")], required=True,
            format_func=lambda c: "Tous" if c == ALL else names[c], key=None,
        )  # fmt: skip
        country = None if choice in (None, ALL) else choice
        selected = [c for c in countries if country in (None, c["country_iso3"])]
        groups = groups_for(selected)
        raw_group = param("produit") or "mais"
        wanted_group = SLUG_GROUP.get(raw_group, raw_group)
        with cols[0]:
            group = st.selectbox(
                "Produit", groups, index=_index(groups, wanted_group, "Maize"),
                format_func=lambda g: GROUP_FR.get(g, g),
            )  # fmt: skip
        series_id = None
        raw_series = param("marche")
        wanted_series = int(raw_series) if raw_series and raw_series.isdigit() else None
        if with_market and country:
            candidates = client.series(country, group)
            if candidates:
                several = len({c["commodity_name_en"] for c in candidates}) > 1
                labels = {
                    s["series_id"]: f"{s['market_name']} — {commodity_fr(s['commodity_name_en'])}"
                    if several else s["market_name"]
                    for s in candidates
                }  # fmt: skip
                ids = sorted(labels, key=lambda i: labels[i])
                if wanted_series not in ids:
                    wanted_series = default_focus(selected[0], group) or ids[0]
                with cols[1]:
                    series_id = st.selectbox("Marché", ids, index=_index(ids, wanted_series),
                                             format_func=labels.get)  # fmt: skip
        elif not with_market:
            series_id = wanted_series
    raw_h = param("h") or param("horizon")
    horizon = int(raw_h) if raw_h in ("1", "3", "6") else 3
    period = param("periode") if param("periode") in PERIODS else "5ans"
    return View(country, group, series_id, horizon, period), countries, selected


# --- Data blocks -----------------------------------------------------------------------


THEME_PARAM = {"sombre": "dark", "clair": "light"}
THEME_COOKIE = "agriprix_theme"


def forced_theme() -> str | None:
    """Mode written in the URL (?theme=sombre|clair), else None."""
    return THEME_PARAM.get(param("theme") or "")


def decide_theme(url_value: str | None, cookie: str | None, streamlit_kind: str | None) -> str:
    """The ONE theme of the page, "dark" or "light" (pure: tested in test_dashboard.py).

    Order: 1. ?theme=sombre|clair in the URL; 2. the cookie THEME_SCRIPT writes in the
    browser, which already holds the last button choice or else the system setting;
    3. Streamlit's own guess, only before the first visit's cookie exists (the script then
    reloads the page once if the guess was wrong).
    """
    if url_value in THEME_PARAM:
        return THEME_PARAM[url_value]
    if cookie in ("dark", "light"):
        return cookie
    return "dark" if streamlit_kind == "dark" else "light"


def current_theme() -> str:
    """decide_theme() for this page; read by the CSS, map, charts and logo alike."""
    try:
        cookie = st.context.cookies.get(THEME_COOKIE)
        kind = st.context.theme.type
    except Exception:  # noqa: BLE001 - outside a session (tests, scripts)
        cookie, kind = None, None
    return decide_theme(param("theme"), cookie, kind)


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
        best.setdefault(a["series_id"], {**a, "month_label": month(a["period"]),
                                         "country": country})  # fmt: skip
    return best


def default_focus(country: dict, group: str) -> int | None:
    """Open the sheet on the market of the strongest recent alert, if any."""
    alerts = latest_alerts(country, group)
    if not alerts:
        return None
    return max(alerts.values(), key=lambda a: abs(a["deviation_pct"]))["series_id"]


def _hover(s: dict, unit: str, alert: dict | None, fc: dict | None, iso3: str) -> str:
    words = maps.STATES[alert["direction"] if alert else "NORMAL"][0]
    lines = [f"<b>{s['market_name']}</b> — {commodity_fr(s['commodity_name_en']).lower()}"]
    if s.get("last_value") is not None:
        lines.append(f"Dernier prix : {price(s['last_value'], unit)} ({month(s['last_obs_date'])})")
    else:
        lines.append("Pas de relevé de terrain récent")
    if alert:
        lines.append(f"{words} : {pct(alert['deviation_pct'])} par rapport au niveau habituel "
                     f"({alert['month_label']})")  # fmt: skip
    else:
        lines.append(f"{words} (aucune alerte ces trois derniers mois)")
    if fc:
        lines.append(
            f"Dans 3 mois ({month(fc['target_period'])}) : environ {price(fc['yhat'], unit)}, "
            f"entre {reading.fr_number(fc['lower_80'])} et {reading.fr_number(fc['upper_80'])}"
        )
        rel = reading.reliability(fc["test_picp_80"])
        if rel:
            lines.append(f"{rel.label} ({rel.detail})")
    elif iso3 == "CIV":
        lines.append("Consultation seule, pas de prévision (valeurs agrégées WFP)")
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
            label = f"{s['market_name']} : {word} {pct(alert['deviation_pct'])}"
        points.append(
            {
                "series_id": s["series_id"], "country": iso3, "latitude": place["latitude"],
                "longitude": place["longitude"], "state": state, "label": label,
                "hover": _hover(s, unit, alert, forecasts.get(s["series_id"]), iso3),
            }
        )  # fmt: skip
    return points, sorted(missing)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearest_markets(series: dict, k: int = 4) -> list[dict]:
    """The k nearest markets with the same staple and WFP coordinates, with their last price."""
    iso3 = series["country_iso3"]
    coords = {m["market_code"]: m for m in client.markets(iso3)}
    here = coords.get(series["market_code"])
    if not here or here["latitude"] is None:
        return []
    out = []
    for s in client.series(iso3, series_group(series)):
        place = coords.get(s["market_code"])
        if s["market_code"] == series["market_code"] or not place or place["latitude"] is None:
            continue
        if s["commodity_name_en"] != series["commodity_name_en"] or s.get("last_value") is None:
            continue
        km = distance_km(here["latitude"], here["longitude"], place["latitude"], place["longitude"])
        out.append({**s, "km": km})
    return sorted(out, key=lambda s: s["km"])[:k]


def series_group(series: dict) -> str:
    return series.get("commodity_group") or series["commodity_name_en"].split(" (")[0]


def link(page: str, label: str, view: View) -> str:
    """A real <a> to another page with the view in its query string (same tab)."""
    return (f'<a class="ap-link" href="{page}?{urlencode(view.params())}" target="_self">'
            f"{label}</a>")  # fmt: skip


def tag(text: str) -> str:
    return f'<span class="ap-tag">{text}</span>'


def footer() -> None:
    st.markdown(
        f'<div class="ap-footer"><p>{SOURCES_HTML}</p>'
        f'<p><a href="{client.PUBLIC_API_URL}/docs">API et téléchargements</a> · '
        f'<a href="fiabilite" target="_self">Méthode et fiabilité</a> · '
        f'<a href="{GITHUB}">Code source</a></p></div>',
        unsafe_allow_html=True,
    )


def _rules(c: dict) -> str:
    """Style rules in the colours of one palette."""
    return f"""
  :root {{ --ap-ink: {c["INK"]}; --ap-muted: {c["TEXT_MUTED"]}; --ap-border: {c["BORDER"]};
           --ap-soft: {c["BG_SOFT"]}; --ap-brand: {c["BRAND"]}; --ap-select: {c["SELECT"]}; }}
  [data-testid="stDataFrame"], [data-testid="stTable"], .ap-num {{ font-variant-numeric: tabular-nums; }}
  ::selection {{ background: {c["SEASON_TAG_BG"]}; color: {c["INK"]}; }}
  :focus-visible {{ outline: 2px solid {c["FORECAST"]} !important; outline-offset: 2px; }}
  /* Header with a thin rule; less empty space between the header and the page title. */
  [data-testid="stMainBlockContainer"], .block-container {{ padding-top: 2.6rem; }}
  /* One theme source: Streamlit's own theme menu (⋮) is hidden so it cannot mix themes. */
  [data-testid="stMainMenu"] {{ display: none !important; }}
  [data-testid="stHeaderLogo"], img[data-testid="stLogo"] {{ height: 2.75rem; max-height: 2.75rem; }}
  /* Light/dark button pinned in the header band (Streamlit has no widget slot there). */
  .st-key-theme_toggle {{ position: fixed; top: .55rem; right: 1rem; z-index: 1000001;
                          width: auto; }}
  .st-key-theme_toggle button {{ min-height: 44px; border-radius: 999px; padding: 0 .9rem; }}
  header[data-testid="stHeader"] {{ background: {c["HEADER_BG"]}; border-bottom: 2px solid {c["HEADER_RULE"]}; }}
  /* Framed blocks (containers keyed "card_*") on the block background. */
  [class*="st-key-card"] {{ background: {c["BG_BLOCK"]}; }}
  /* Neighbour whose last reading is old: greyed, with the words "relevé ancien". */
  [class*="st-key-card_near_stale"] {{ background: {c["BG_SOFT"]}; color: {c["TEXT_MUTED"]}; }}
  .ap-old {{ border: 1px solid {c["BORDER"]}; border-radius: 4px; padding: 0 .35rem;
             color: {c["TEXT_MUTED"]}; font-size: .8rem; }}
  a {{ color: {c["LINK"]}; }} a:hover {{ color: {c["LINK_HOVER"]}; }}
  /* Blocks: 8 px radius, 1 px border, no shadow. */
  div[data-testid="stVerticalBlock"].st-emotion-cache-0, .stVerticalBlock[class*="border"] {{ border-radius: 8px; }}
  [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 8px; box-shadow: none; }}
  /* Filter bar on the soft background; pills fully rounded. */
  .st-key-filters {{ background: {c["BG_SOFT"]}; border-radius: 8px; padding: .75rem 1rem .25rem; }}
  .st-key-filters [data-testid="stButtonGroup"] button {{ border-radius: 999px; min-height: 40px; }}
  @media (max-width: 640px) {{
    h1 {{ font-size: 1.65rem !important; line-height: 1.2 !important; }}
    .st-key-filters [data-testid="stButtonGroup"] > div {{ flex-wrap: nowrap; overflow-x: auto;
      scrollbar-width: none; padding-bottom: .25rem; }}
    .st-key-filters [data-testid="stButtonGroup"] button {{ flex: 0 0 auto; min-height: 44px; }}
  }}
  .ap-lead {{ font-size: 1.08rem; line-height: 1.55; max-width: 72ch; margin: .2rem 0 .4rem; }}
  .ap-note {{ color: {c["TEXT_MUTED"]}; font-size: .92rem; max-width: 78ch; }}
  .ap-sub {{ color: {c["TEXT_MUTED"]}; font-size: 1rem; margin-top: -.6rem; }}
  .ap-tag {{ display: inline-block; padding: 0 .45rem; border-radius: 4px; background: {c["SEASON_TAG_BG"]};
             color: {c["SEASON_TAG_TEXT"]}; font-size: .85rem; }}
  .ap-badge {{ display: inline-block; padding: .15rem .6rem; border: 1px solid {c["BORDER"]};
               border-radius: 999px; font-size: .9rem; white-space: nowrap; background: {c["BG_BLOCK"]}; }}
  .ap-bias {{ color: {c["TEXT_MUTED"]}; font-size: .92rem; }}
  .ap-alert-head {{ display: flex; justify-content: space-between; gap: .5rem; font-weight: 600;
                    font-size: 1.02rem; margin: 0; }}
  .ap-alert-head .up {{ color: {c["ALERT_UP"]}; }} .ap-alert-head .down {{ color: {c["ALERT_DOWN"]}; }}
  .ap-alert p {{ margin: .15rem 0; }}
  .ap-factor-label {{ color: {c["TEXT_MUTED"]}; font-size: .9rem; margin: 0; }}
  .ap-factor-value {{ font-size: 1.25rem; font-weight: 650; margin: .1rem 0; }}
  .ap-soon {{ display: inline-block; border: 1px solid {c["BORDER"]}; border-radius: 999px;
              padding: 0 .55rem; color: {c["TEXT_MUTED"]}; font-size: .8rem; }}
  .ap-factor-what {{ font-size: .92rem; margin: .25rem 0; }}
  /* No link icon next to headings (Streamlit adds one on hover). */
  [data-testid="stHeaderActionElements"] {{ display: none !important; }}
  .ap-factor-source {{ color: {c["TEXT_MUTED"]}; font-size: .82rem; margin: 0; }}
  table.ap-var {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
  table.ap-var th {{ text-align: left; font-weight: 600; padding: .55rem .8rem; border-bottom: 1px solid {c["BORDER"]}; }}
  table.ap-var td {{ padding: .55rem .8rem; border-bottom: 1px solid {c["GRID"]}; }}
  .ap-bar {{ display: flex; align-items: center; gap: .6rem; }}
  .ap-bar span.track {{ flex: 1; height: 8px; background: {c["GRID"]}; border-radius: 999px; overflow: hidden; }}
  .ap-bar span.fill {{ display: block; height: 100%; background: {c["FORECAST"]}; }}
  .ap-big {{ font-size: 2.4rem; font-weight: 700; line-height: 1.1; }}
  .ap-panel {{ background: {c["BG_SOFT"]}; border-radius: 8px; padding: .6rem .8rem; margin: .4rem 0; }}
  .ap-crumbs {{ font-size: .92rem; color: {c["TEXT_MUTED"]}; }}
  .ap-event {{ border-left: 2px solid {c["BORDER"]}; padding: 0 0 .6rem .8rem; margin: 0; }}
  .ap-event small {{ color: {c["TEXT_MUTED"]}; }}
  .ap-footer {{ border-top: 1px solid {c["BORDER"]}; margin-top: 2rem; padding-top: 1rem;
                color: {c["TEXT_MUTED"]}; font-size: .9rem; }}
  a.ap-link {{ display: inline-flex; align-items: center; min-height: 44px; font-weight: 600;
               text-decoration: none; }}
  a.ap-link:hover {{ text-decoration: underline; }}
""" + _dark_only(c)


def _dark_only(c: dict) -> str:
    """Rules of the dark mockup that the light theme does not have (it keeps Streamlit's)."""
    if not c["TAB_ACTIVE_BG"]:
        return ""
    return f"""
  /* Active tab: straw with dark text; other tabs in ink. */
  a[data-testid="stTopNavLink"] span {{ color: {c["INK"]}; }}
  a[data-testid="stTopNavLink"][aria-current="page"] {{ background: {c["TAB_ACTIVE_BG"]}; border-radius: 6px; }}
  a[data-testid="stTopNavLink"][aria-current="page"] span {{ color: {c["TAB_ACTIVE_TEXT"]}; }}
  /* Selected pill: filled green, white text, lighter green edge. */
  [data-testid="stButtonGroup"] button[aria-checked="true"] {{
      background: {c["SELECT"]} !important; border-color: {c["SELECT_BORDER"]} !important; }}
  [data-testid="stButtonGroup"] button[aria-checked="true"],
  [data-testid="stButtonGroup"] button[aria-checked="true"] * {{ color: {c["SELECT_TEXT"]} !important; }}
"""


def css(theme: str | None = None) -> str:
    """Page styles in the colours of the page's theme (current_theme)."""
    return f"<style>{_rules(tk.palette(theme))}</style>"


# Streamlit keeps its theme in localStorage, one key per page path of the app document
# ("stActiveTheme-<path>-v2" = "Light" | "Dark" | "System", Streamlit 1.67). On Streamlit
# Community Cloud the app runs in an iframe at "/~/+/": the script works on its own
# document (window), never on window.parent, whose path is the outer page's.
PAGE_PATHS = ("", "marches", "facteurs", "fiabilite", "donnees")
THEME_SCRIPT = """<script>
(() => {
  const server = "__SERVER__";  // theme this page was drawn in
  const url = new URL(window.location.href);
  const fromUrl = {sombre: "dark", clair: "light"}[url.searchParams.get("theme")];
  const store = window.localStorage;
  if (fromUrl) store.setItem("agriprix-theme-choice", fromUrl);
  const chosen = fromUrl || store.getItem("agriprix-theme-choice");
  const system = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  const theme = chosen === "dark" || chosen === "light" ? chosen : system;
  // Same theme for Streamlit on every page (never "System", which could diverge).
  const pages = __PAGES__;
  const parts = window.location.pathname.split("/");
  const last = parts[parts.length - 1];
  const base = (pages.includes(last) ? parts.slice(0, -1) : parts).join("/");
  const wantedSt = JSON.stringify(theme === "dark" ? "Dark" : "Light");
  let stale = false;
  for (const page of pages) {
    const key = `stActiveTheme-${base}/${page}-v2`;
    if (page === last && store.getItem(key) !== wantedSt) stale = true;
    store.setItem(key, wantedSt);
  }
  document.cookie = `__COOKIE__=${theme}; path=/; max-age=31536000; SameSite=Lax`;
  if (stale || server !== theme) {
    // Reload once to apply it everywhere; never loop (at most 2 reloads in 20 s).
    const now = Date.now();
    const recent = JSON.parse(sessionStorage.getItem("agriprix-reloads") || "[]")
      .filter((t) => now - t < 20000);
    if (recent.length < 2) {
      sessionStorage.setItem("agriprix-reloads", JSON.stringify([...recent, now]));
      window.location.reload();
      return;
    }
  }
  if (!chosen && !window.__agriprixThemeWatch) {
    window.__agriprixThemeWatch = true;
    window.matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => window.location.reload());
  }
})();
</script>""".replace("__PAGES__", json.dumps(PAGE_PATHS)).replace("__COOKIE__", THEME_COOKIE)


def theme_script(server_theme: str) -> str:
    """THEME_SCRIPT for a page drawn in server_theme ("light" or "dark")."""
    return THEME_SCRIPT.replace("__SERVER__", server_theme)


# Map framing and labels, applied in the browser to every Plotly map of the page:
# - fit the map to layout.meta.fit with a 5 % margin at its real size (Plotly cannot: the
#   pixel width differs between a computer and a phone), again when the country or the
#   width changes, never while the visitor pans;
# - labels get a halo in the block colour and move to a free side of their point instead
#   of being written over the other markets (MapLibre variable anchors and collisions).
MAP_SCRIPT = """<script>
(() => {
  if (window.__agriprixMaps) return;
  window.__agriprixMaps = true;
  const setLayout = (map, id, key, value) => {
    if (JSON.stringify(map.getLayoutProperty(id, key)) !== JSON.stringify(value))
      map.setLayoutProperty(id, key, value);
  };
  const apply = () => {
    document.querySelectorAll(".js-plotly-plot").forEach((gd) => {
      const full = gd._fullLayout;
      const meta = (gd.layout || {}).meta || {};
      if (!full || !full.map || !full.map._subplot || !meta.fit) return;
      const map = full.map._subplot.map;
      if (!map || !map.isStyleLoaded()) return;
      const signature = JSON.stringify(meta.fit) + ":" + gd.clientWidth;
      if (gd.__agriprixFit !== signature) {
        // New country or new width: compute the camera that fills the map (5 % margin).
        gd.__agriprixFit = signature;
        gd.__agriprixMoved = false;
        const pad = Math.round(Math.min(gd.clientWidth, gd.clientHeight) * 0.05);
        const [w, s, e, n] = meta.fit;
        gd.__agriprixCamera = map.cameraForBounds([[w, s], [e, n]], {padding: pad});
        if (!gd.__agriprixWatch) {
          gd.__agriprixWatch = true;
          map.on("movestart", (event) => { if (event.originalEvent) gd.__agriprixMoved = true; });
        }
      }
      // Plotly may redraw its first view: keep the fitted one until the visitor moves the map.
      const camera = gd.__agriprixCamera;
      if (camera && !gd.__agriprixMoved && Math.abs(map.getZoom() - camera.zoom) > 0.01) {
        map.jumpTo({center: camera.center, zoom: camera.zoom});
      }
      for (const layer of map.getStyle().layers) {
        if (layer.type !== "symbol" || !layer.id.startsWith("plotly-trace-layer")) continue;
        if (map.getPaintProperty(layer.id, "text-halo-color") !== meta.halo) {
          map.setPaintProperty(layer.id, "text-halo-color", meta.halo);
          map.setPaintProperty(layer.id, "text-halo-width", 2.2);
        }
        setLayout(map, layer.id, "text-variable-anchor", ["left", "right", "top", "bottom"]);
        setLayout(map, layer.id, "text-radial-offset", 1.2);
        setLayout(map, layer.id, "text-justify", "auto");
        setLayout(map, layer.id, "text-allow-overlap", false);
      }
    });
  };
  setInterval(apply, 600);
})();
</script>"""

CSS = css("light")  # kept for imports
