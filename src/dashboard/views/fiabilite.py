"""Fiabilité: what the forecasts are worth, how an alert is decided, which version is served."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from src.dashboard import charts, client
from src.dashboard.common import (
    GAIN_INTRO,
    GITHUB,
    MODEL_FR,
    WINDOWS,
    current_theme,
    footer,
    gain_summary,
    month,
)


def render() -> None:
    run = client.active_run()
    st.title("Fiabilité des prévisions")
    st.markdown("### Ce que valent les prévisions")
    window = st.radio("Période évaluée", list(WINDOWS), format_func=WINDOWS.get, horizontal=True)
    metrics = client.model_metrics(window)["items"]
    st.markdown(f'<p class="ap-lead">{GAIN_INTRO}</p>', unsafe_allow_html=True)
    st.plotly_chart(charts.gain_figure(metrics, theme=current_theme()), width="stretch",
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
        f"{month(run['data_until'])}, {run['ml_eligible_series']} séries prévues, "
        f"{run['anomalies']} alertes historiques, code <code>{run['git_sha']}</code>. "
        f'Code source et rapports : <a href="{GITHUB}">{GITHUB}</a>.</p>',
        unsafe_allow_html=True,
    )
    footer()


render()
