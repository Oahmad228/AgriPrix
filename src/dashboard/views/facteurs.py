"""Facteurs: the outside information the research track will add (none is shown yet)."""

from __future__ import annotations

import streamlit as st
from src.dashboard.common import FACTORS, GITHUB, factor_card, footer


def render() -> None:
    st.title("Ce qui pèse sur les prix")
    st.markdown(
        '<p class="ap-lead">Quatre familles d\'informations publiques peuvent expliquer un '
        "retournement de prix : la pluie, la récolte, le carburant et les décisions "
        "commerciales. Aucune n'est encore dans l'entrepôt de données : chaque bloc reste "
        "« En préparation » tant que la donnée n'est pas chargée, datée et vérifiée. Aucun "
        "chiffre n'est affiché d'ici là.</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, factor in enumerate(FACTORS):
        with cols[i % 2], st.container(border=True, key=f"card_factor_{i}"):
            st.markdown(factor_card(*factor), unsafe_allow_html=True)
    st.markdown(
        "<p class=\"ap-note\">Règle : un facteur n'entre dans une prévision qu'avec la date à "
        "laquelle il était connu (pas de regard vers le futur). Le protocole de recherche qui "
        "mesurera leur apport est publié avant tout calcul : "
        f'<a href="{GITHUB}/blob/research/regime-shift/docs/research/01-protocole.md">protocole</a>.</p>',
        unsafe_allow_html=True,
    )
    footer()


render()
