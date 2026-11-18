"""Home "Ce mois-ci": where are prices abnormal this month? The answer before the filters."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from src.dashboard import charts, client, maps, reading
from src.dashboard.common import (
    FACTORS,
    GROUP_FR,
    MARKET,
    View,
    covered_countries,
    current_theme,
    filter_bar,
    footer,
    latest_alerts,
    link,
    market_points,
    month,
    param,
    pct,
    price,
    share,
    tag,
    view_url,
)


def header(countries: list[dict]):
    run = client.active_run()
    wanted = (param("pays") or "BFA").upper()
    shown = [c for c in countries if wanted in ("TOUS", c["country_iso3"])] or countries
    latest = max(c["max_observed_date"] for c in shown)
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    with left:
        st.title("Où les prix sont‑ils anormaux ce mois‑ci ?")  # no-break hyphen and space
        st.markdown(
            f'<p class="ap-sub">Données jusqu\'à {month(latest)} · mise à jour mensuelle · '
            f"{run['ml_eligible_series']} séries prévues dans {len(countries)} pays</p>",
            unsafe_allow_html=True,
        )
    return right


def share_button(where, view: View) -> None:
    with where, st.popover("Partager cette vue", icon=":material/ios_share:"):
        st.markdown("Adresse de cette vue (pays, produit, horizon) :")
        st.code(view_url(view), language=None)


def map_block(view: View, selected: list[dict], names: dict[str, str], alerts: dict) -> None:
    points, missing = [], []
    for country in selected:
        country_alerts = {k: a for k, a in alerts.items() if a["country"] is country}
        p, m = market_points(country, view.group, country_alerts)
        points += p
        missing += m
    product = GROUP_FR.get(view.group, view.group).lower()
    where = names[view.country] if view.country else "pays suivis"
    with st.container(border=True, key="map_card"):
        st.markdown(f"#### Carte des marchés · {product}, {where}")
        key = f"map_{view.country}_{view.group}"
        event = st.plotly_chart(
            maps.market_map(points, view.country, names, height=470, theme=current_theme()),
            key=key, on_select="rerun", selection_mode="points", width="stretch",
            config=maps.CONFIG,
        )  # fmt: skip
        hit = maps.clicked(event.selection.points if event and event.selection else [])
        # A selection persists across reruns: act only when it changes.
        if hit != st.session_state.get(f"{key}_done"):
            st.session_state[f"{key}_done"] = hit
            if hit and hit[0] == "country" and hit[1] != view.country:
                st.query_params["pays"] = hit[1]
                st.query_params.pop("marche", None)
                st.rerun()
            if hit and hit[0] == "market":
                iso3 = next(p["country"] for p in points if p["series_id"] == hit[1])
                params = View(iso3, view.group, int(hit[1]), view.horizon, view.period).params()
                st.switch_page(MARKET, query_params=params)
        note = (
            f"Survoler un marché montre son prix ; cliquer ouvre sa fiche ; cliquer un pays le "
            f"choisit. {len(points)} marchés placés aux coordonnées publiées par le WFP."
        )
        if missing:
            note += (f" {len(missing)} marché(s) sans coordonnées publiées ne sont pas sur la "
                     f"carte : {', '.join(sorted(missing))}.")  # fmt: skip
        if any(c["country_iso3"] == "CIV" for c in selected):
            note += " Côte d'Ivoire : consultation seule, pas de prévision (valeurs agrégées WFP)."
        if any(c["country_iso3"] == "MAR" for c in selected):
            note += " Maroc : pas de marchés, un indice national FAOSTAT des prix alimentaires."
        st.markdown(f'<p class="ap-note">{note}<br>{maps.attribution(current_theme())}.</p>',
                    unsafe_allow_html=True)  # fmt: skip


def alerts_block(view: View, alerts: dict) -> None:
    ordered = sorted(alerts.values(), key=lambda a: abs(a["deviation_pct"]), reverse=True)
    with st.container(border=True, key="alerts_card"):
        st.markdown(f"#### {len(ordered)} alerte{'s' if len(ordered) > 1 else ''} ce trimestre")
        st.markdown(
            '<p class="ap-note">Un prix est en alerte quand il s\'éloigne nettement de son niveau '
            "habituel pour la saison.</p>",
            unsafe_allow_html=True,
        )
        if not ordered:
            st.markdown('<p class="ap-note">Aucune alerte sur les trois derniers mois : les prix '
                        "relevés restent dans leur plage habituelle.</p>", unsafe_allow_html=True)  # fmt: skip
        for a in ordered[:12]:
            country = a["country"]
            info = next((s for s in client.series(country["country_iso3"], view.group)
                         if s["series_id"] == a["series_id"]), None)  # fmt: skip
            unit = charts.unit_label(info["unit_measure"], info["currency_code"]) if info else ""
            period = pd.Timestamp(a["period"]).date()
            up = a["direction"] == "UP"
            symbol, css, word = ("▲", "up", "Hausse") if up else ("▼", "down", "Baisse")
            season = (" · " + tag("en période de soudure")
                      if charts.in_lean_season(period, country["lean_season_months"]) else "")  # fmt: skip
            gravity = "forte" if a["severity"] == "CRITICAL" else "modérée"
            where = "" if view.country else f" ({country['country_name_fr']})"
            with st.container(key=f"alert_{a['series_id']}"):
                st.markdown(
                    f'<div class="ap-alert"><p class="ap-alert-head"><span>{a["market_name"]}{where}'
                    f'</span><span class="{css}" aria-label="{word}">{symbol} {pct(a["deviation_pct"])}'
                    f"</span></p><p>{price(a['observed_value'], unit)}, alors qu'environ "
                    f"{reading.fr_number(a['expected_value'])} étaient attendus pour la saison.</p>"
                    f'<p class="ap-note">{a["month_label"]}{season} · {word} anormale, '
                    f"gravité {gravity}</p></div>",
                    unsafe_allow_html=True,
                )
                target = View(country["country_iso3"], view.group, a["series_id"],
                              view.horizon, view.period)  # fmt: skip
                st.markdown(link("marches", "Voir la fiche du marché →", target),
                            unsafe_allow_html=True)  # fmt: skip
        if len(ordered) > 12:
            st.markdown(f'<p class="ap-note">… et {len(ordered) - 12} autres alertes.</p>',
                        unsafe_allow_html=True)  # fmt: skip


def factors_block() -> None:
    st.subheader("Ce qui pèse sur les prix")
    st.markdown(
        '<p class="ap-sub">Chaque facteur est daté à sa publication : la prévision n\'utilise que '
        "ce qui était connu au moment de prévoir.</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for col, (label, source) in zip(cols, FACTORS, strict=True):
        with col, st.container(border=True):
            st.markdown(
                f'<p class="ap-factor-label">{label}</p><p class="ap-factor-value">[à intégrer]</p>'
                f'<p class="ap-factor-source">{source}</p>',
                unsafe_allow_html=True,
            )


def variations_block(view: View, selected: list[dict]) -> None:
    items = []
    for country in selected:
        body = client.forecasts(country=country["country_iso3"], commodity_group=view.group,
                                horizon=3)  # fmt: skip
        items += [{**f, "country": country} for f in body["items"] if f["last_value"]]
    if not items:
        return
    for f in items:
        f["change"] = (f["yhat"] / f["last_value"] - 1) * 100
    items.sort(key=lambda f: abs(f["change"]), reverse=True)
    product = GROUP_FR.get(view.group, view.group).lower()
    target = month(items[0]["target_period"])
    left, right = st.columns([3, 2], vertical_alignment="bottom")
    with left:
        st.subheader("Plus fortes variations attendues dans 3 mois")
        where = items[0]["country"]["country_name_fr"] if view.country else "pays suivis"
        st.markdown(f'<p class="ap-sub">{product.capitalize()}, {where}, prévision pour '
                    f"{target}.</p>", unsafe_allow_html=True)  # fmt: skip
    rel = reading.reliability(items[0]["test_picp_80"]) if view.country else None
    if rel:
        with right:
            st.markdown(
                f'<p style="text-align:right"><span class="ap-badge">{rel.symbol} Fiabilité à 3 '
                f"mois : <b>{rel.word}</b> ({rel.detail.replace('la fourchette a été', 'fourchette')})"
                "</span></p>",
                unsafe_allow_html=True,
            )
    top = items[:5]
    biggest = max(abs(f["change"]) for f in top) or 1
    rows = []
    for f in top:
        unit = charts.unit_label(f["unit_measure"], f["currency_code"])
        params = View(f["country"]["country_iso3"], view.group, f["series_id"], 3, view.period)
        href = "marches?" + "&".join(f"{k}={v}" for k, v in params.params().items())
        width = 100 * abs(f["change"]) / biggest
        rows.append(
            f'<tr><td><a href="{href}" target="_self"><b>{f["market_name"]}</b></a></td>'
            f"<td>{price(f['last_value'], unit)}</td><td>{price(f['yhat'], unit)}</td>"
            f'<td><div class="ap-bar"><span class="track"><span class="fill" style="width:{width:.0f}%">'
            f"</span></span><span>{pct(f['change'], 1)}</span></div></td></tr>"
        )
    st.markdown(
        '<table class="ap-var"><thead><tr><th>Marché</th><th>Dernier prix</th><th>Prévision</th>'
        f"<th>Variation attendue</th></tr></thead><tbody>{''.join(rows)}</tbody></table>",
        unsafe_allow_html=True,
    )
    with st.expander(f"Toutes les prévisions à 3 mois ({len(items)} marchés)"):
        frame = pd.DataFrame(
            [
                {
                    "Marché": f["market_name"], "Pays": f["country"]["country_name_fr"],
                    "Dernier prix": f["last_value"], "Prévision": f["yhat"],
                    "Basse (80 %)": f["lower_80"], "Haute (80 %)": f["upper_80"],
                    "Variation attendue": f["change"],
                    "Fiabilité": (r.label if (r := reading.reliability(f["test_picp_80"])) else "—"),
                }
                for f in items
            ]
        )  # fmt: skip
        money = st.column_config.NumberColumn(format="%.0f")
        st.dataframe(
            frame, hide_index=True, width="stretch",
            column_config={c: money for c in ("Dernier prix", "Prévision", "Basse (80 %)", "Haute (80 %)")}
            | {"Variation attendue": st.column_config.NumberColumn(format="%+.1f %%")},
        )  # fmt: skip


def render() -> None:
    right = header(covered_countries())
    view, countries, selected = filter_bar(with_market=False)
    share_button(right, view)
    names = {c["country_iso3"]: c["country_name_fr"] for c in countries}
    alerts: dict[int, dict] = {}
    for country in selected:
        alerts.update(latest_alerts(country, view.group))
    left, side = st.columns([2, 1], gap="medium")
    with left:
        map_block(view, selected, names, alerts)
    with side:
        alerts_block(view, alerts)
    factors_block()
    variations_block(view, selected)
    share(view)
    footer()


render()
