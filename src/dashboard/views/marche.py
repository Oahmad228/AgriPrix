"""Market sheet: a sentence before a number, then the chart, the horizons and the context."""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st
from src.dashboard import charts, client, reading
from src.dashboard.common import (
    GROUP_FR,
    PERIODS,
    REASON_FR,
    View,
    commodity_fr,
    filter_bar,
    footer,
    latest_alerts,
    link,
    month,
    nearest_markets,
    price,
    share,
    view_url,
)

HORIZONS = {1: "1 mois", 3: "3 mois", 6: "6 mois"}


def _last_observed(observations: list[dict]) -> tuple[float | None, str]:
    measured = [o for o in observations if o["is_observed"]]
    if not measured:
        return None, "—"
    last = max(measured, key=lambda o: o["period"])
    return last["value"], month(last["period"])


def _emphasis(sentence: str) -> str:
    """Bold the deviation and the forecast level, as in the mockup."""
    sentence = re.sub(r"(\d+ % (?:sous|au-dessus de) son niveau habituel)", r"<b>\1</b>", sentence)
    return re.sub(r"(autour de [\d  ]+ [^,]+?)(,)", r"<b>\1</b>\2", sentence, count=1)


def heading(view: View, country: dict, selected: dict, hist: dict, chosen: dict | None) -> None:
    unit = charts.unit_label(selected["unit_measure"], selected["currency_code"])
    home = "/?" + "&".join(f"{k}={v}" for k, v in View(view.country, view.group, None,
                                                         view.horizon, view.period).params().items())  # fmt: skip
    st.markdown(
        f'<p class="ap-crumbs"><a href="{home}" target="_self">{country["country_name_fr"]}</a> › '
        f'<a href="{home}" target="_self">{GROUP_FR.get(view.group, view.group)}</a> › '
        f"{selected['market_name']}</p>",
        unsafe_allow_html=True,
    )
    title, actions = st.columns([3, 2], vertical_alignment="bottom")
    with title:
        st.title(f"{commodity_fr(selected['commodity_name_en'])} à {selected['market_name']}")
    with actions, st.container(horizontal=True, horizontal_alignment="right"):
        csv = pd.DataFrame(hist["observations"]).to_csv(index=False).encode("utf-8")
        st.download_button("Télécharger (CSV)", csv, file_name=f"agriprix-serie-{selected['series_id']}.csv",
                           mime="text/csv", icon=":material/download:")  # fmt: skip
        with st.popover("Copier le lien", icon=":material/link:"):
            st.code(view_url(view, "marches"), language=None)
    value, last_month = _last_observed(hist["observations"])
    alert = latest_alerts(country, view.group).get(selected["series_id"])
    lead = reading.situation_sentence(value, unit, last_month, alert)
    if chosen:
        lead += " " + reading.forecast_sentence(chosen, unit, month(chosen["target_period"]))
    st.markdown(f'<p class="ap-lead">{_emphasis(lead)}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="ap-note">Dernier relevé : {last_month} · source WFP via HDX</p>',
                unsafe_allow_html=True)  # fmt: skip


def side_panel(chosen: dict | None, forecasts: list[dict], selected: dict, horizon: int) -> None:
    unit = charts.unit_label(selected["unit_measure"], selected["currency_code"])
    if not chosen:
        reason = REASON_FR.get(selected.get("ineligibility_reason") or "", "données insuffisantes")
        if not forecasts:
            st.markdown(f'<p class="ap-note">Pas de prévision pour cette série : {reason}.</p>',
                        unsafe_allow_html=True)  # fmt: skip
        return
    st.markdown(
        f'<p class="ap-note">Prévision pour {month(chosen["target_period"])}</p>'
        f'<p><span class="ap-big ap-num">{reading.fr_number(chosen["yhat"])}</span> {unit}</p>'
        f"<p>Fourchette probable : <b>{reading.fr_number(chosen['lower_80'])} à "
        f"{reading.fr_number(chosen['upper_80'])} {unit}</b></p>",
        unsafe_allow_html=True,
    )
    rel = reading.reliability(chosen["test_picp_80"])
    if rel:
        st.markdown(f'<div class="ap-panel"><b>{rel.label}</b> · {rel.detail} à {horizon} mois '
                    "(cible : 80).</div>", unsafe_allow_html=True)  # fmt: skip
    bias = reading.bias_sentence(chosen.get("recent_bias_pct"), horizon)
    if bias:
        st.markdown(f'<p class="ap-bias">{bias}</p>', unsafe_allow_html=True)
    with st.popover("Comment lire cette prévision ?"):
        st.markdown(
            "La ligne en pointillé est la prévision ; la zone claire autour est la fourchette "
            "à 80 % : elle devrait contenir le vrai prix 8 fois sur 10. La fiabilité dit ce "
            "qu'il en a été pendant la période de test pour ce groupe de marchés : **correcte** "
            "à partir de 70 fois sur 100, **moyenne** de 50 à 69, **faible** en dessous. Le "
            "biais signale un modèle qui s'est trompé dans le même sens ces derniers mois ; la "
            "prévision affichée n'est jamais corrigée en douce."
        )


def price_block(
    view: View, country: dict, selected: dict, hist: dict, forecasts: list[dict]
) -> tuple[int, str]:
    with st.container(border=True, key="price_card"):
        head, h_col, p_col = st.columns([2, 2, 2], vertical_alignment="center")
        head.markdown("#### Prix et prévision")
        horizon = view.horizon if not forecasts else h_col.segmented_control(
            "Horizon", list(HORIZONS), default=view.horizon, required=True,
            format_func=HORIZONS.get, label_visibility="collapsed",
        ) or view.horizon  # fmt: skip
        period = p_col.segmented_control(
            "Période", list(PERIODS), default=view.period, required=True,
            format_func=lambda k: PERIODS[k][0], label_visibility="collapsed",
        ) or view.period  # fmt: skip
        chosen = next((f for f in forecasts if f["horizon_months"] == horizon), None)
        chart, side = st.columns([3, 1], gap="medium")
        with chart:
            fig = charts.price_figure(
                hist["observations"], client.anomalies(series_id=selected["series_id"])["items"],
                forecasts, selected["unit_measure"], selected["currency_code"],
                country["lean_season_months"], years=PERIODS[period][1],
            )  # fmt: skip
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown('<p class="ap-note">Bandes ocre : période de soudure (juin-septembre). '
                        "Survol : prix, date et écart à la normale.</p>", unsafe_allow_html=True)  # fmt: skip
        with side:
            side_panel(chosen, forecasts, selected, horizon)
        if forecasts:
            unit, currency = selected["unit_measure"], selected["currency_code"]
            table = pd.DataFrame(
                {
                    "Horizon": [f"{f['horizon_months']} mois" for f in forecasts],
                    "Mois visé": [month(f["target_period"]) for f in forecasts],
                    "Prévision": [charts.fmt_value(f["yhat"], unit, currency) for f in forecasts],
                    "Fourchette à 80 %": [
                        f"{charts.fmt_value(f['lower_80'], unit, currency)} – "
                        f"{charts.fmt_value(f['upper_80'], unit, currency)}"
                        for f in forecasts
                    ],
                    "Fiabilité": [
                        r.label if (r := reading.reliability(f["test_picp_80"])) else "—"
                        for f in forecasts
                    ],
                }
            )
            st.dataframe(table, hide_index=True, width="stretch")
    return horizon, period


def context_blocks(country: dict, selected: dict) -> None:
    why, events = st.columns(2, gap="large")
    with why:
        st.subheader("Pourquoi cette prévision ?")
        st.markdown('<p class="ap-sub">Les facteurs qui pèsent le plus, connus au moment de '
                    "prévoir.</p>", unsafe_allow_html=True)  # fmt: skip
        rows = (("Tendance des 12 derniers mois", "[contribution à calculer]"),
                ("Saison (après la récolte, avant la soudure)", "[contribution à calculer]"),
                ("Pluie de la saison vs normale", "[à intégrer : CHIRPS]"),
                ("Estimation de récolte", "[à intégrer : CILSS]"))  # fmt: skip
        st.dataframe(pd.DataFrame(rows, columns=["Facteur", "Contribution"]), hide_index=True,
                     width="stretch")  # fmt: skip
    with events:
        st.subheader("Ce qui s'est passé")
        st.markdown('<p class="ap-sub">Événements sourcés ; les alertes sont aussi sur le '
                    "graphique.</p>", unsafe_allow_html=True)  # fmt: skip
        history = sorted(client.anomalies(series_id=selected["series_id"])["items"],
                         key=lambda a: a["period"], reverse=True)[:3]  # fmt: skip
        unit = charts.unit_label(selected["unit_measure"], selected["currency_code"])
        html = "".join(
            f'<p class="ap-event"><small>{month(a["period"])}</small><br>Alerte AgriPrix : prix '
            f"{abs(a['deviation_pct']):.0f} % {'au-dessus du' if a['deviation_pct'] > 0 else 'sous le'}"
            f" niveau habituel de la saison ({price(a['observed_value'], unit)}).<br>"
            "<small>Source : AgriPrix</small></p>"
            for a in history
        )
        html += ('<p class="ap-event"><small>[date]</small><br>[Événements GIEWS et PREGEC : à '
                 "intégrer]<br><small>Source : FAO, CILSS</small></p>")  # fmt: skip
        st.markdown(html, unsafe_allow_html=True)


def neighbours_block(view: View, selected: dict) -> None:
    near = nearest_markets(selected)
    if not near:
        return
    st.subheader("Marchés voisins")
    st.markdown('<p class="ap-sub">Même produit, dernier relevé : pour voir si le mouvement est '
                "local ou général.</p>", unsafe_allow_html=True)  # fmt: skip
    cols = st.columns(len(near))
    for col, s in zip(cols, near, strict=True):
        unit = charts.unit_label(s["unit_measure"], s["currency_code"])
        with col, st.container(border=True):
            st.markdown(
                f"**{s['market_name']}**<br>{price(s['last_value'], unit)}<br>"
                f'<span class="ap-note">{month(s["last_obs_date"])} · à {s["km"]:.0f} km</span>',
                unsafe_allow_html=True,
            )
            target = View(view.country, view.group, s["series_id"], view.horizon, view.period)
            st.markdown(link("marches", "Voir la fiche →", target), unsafe_allow_html=True)


def render() -> None:
    view, _countries, selected_countries = filter_bar(with_market=True)
    if not view.series_id or not selected_countries:
        st.info("Aucune série de prix pour ce produit dans ce pays.")
        share(view)
        footer()
        return
    country = selected_countries[0]
    selected = next(s for s in client.series(country["country_iso3"], view.group)
                    if s["series_id"] == view.series_id)  # fmt: skip
    hist = client.history(selected["series_id"])
    if not hist["observations"]:
        st.info("Cette série ne contient encore aucun relevé.")
        share(view)
        return
    forecasts = (
        client.forecasts(series_id=selected["series_id"])["items"]
        if selected["is_ml_eligible"]
        else []
    )
    # The heading sentence uses the URL's horizon; the horizon control renders below it, so a
    # change is written to the URL and the page reruns once to keep both in step.
    chosen = next((f for f in forecasts if f["horizon_months"] == view.horizon), None)
    heading(view, country, selected, hist, chosen)
    horizon, period = price_block(view, country, selected, hist, forecasts)
    if horizon != view.horizon:
        share(View(view.country, view.group, view.series_id, horizon, period))
        st.rerun()
    context_blocks(country, selected)
    neighbours_block(view, selected)
    share(View(view.country, view.group, view.series_id, horizon, period))
    footer()


render()
