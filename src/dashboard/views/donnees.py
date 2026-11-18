"""Données & API: where the numbers come from and how to reuse them."""

from __future__ import annotations

import streamlit as st
from src.dashboard import client
from src.dashboard.common import GITHUB, footer


def render() -> None:
    st.title("Données & API")
    api = client.PUBLIC_API_URL
    st.markdown(
        f"""
<p class="ap-lead">Tous les chiffres de ce site viennent d'une API publique, en lecture seule,
documentée et sans clé.</p>

- **Documentation interactive** : <a href="{api}/docs">{api}/docs</a>
- **Exemple** : <a href="{api}/api/v1/forecasts?country=BFA&commodity_group=Maize&horizon=3">prévisions à 3 mois, maïs, Burkina Faso</a>
- **Code source et méthode** : <a href="{GITHUB}">{GITHUB}</a>

### Sources et licences
- Prix sur les marchés : World Food Programme (WFP), via HDX, licence CC BY-IGO 3.0.
- Indice des prix alimentaires du Maroc : FAOSTAT, FAO, licence CC BY 4.0.
- Fond de carte : © contributeurs OpenStreetMap (ODbL). Frontières : geoBoundaries
  (Runfola et al., 2020), licence propre à chaque pays.

<p class="ap-note">Alertes et prévisions calculées par AgriPrix Observatory, sans validation du
WFP ni de la FAO. L'API publique limite le nombre de requêtes par minute ; le service gratuit se
met en veille et peut mettre jusqu'à une minute à répondre.</p>
""",
        unsafe_allow_html=True,
    )
    footer()


render()
