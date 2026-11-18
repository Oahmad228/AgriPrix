"""AgriPrix Observatory dashboard (Streamlit) — reads everything from the public API.

Run: streamlit run app.py (from src/dashboard, see docker-compose.yml).
Pages live in ./views; shared state and blocks in common.py; colours in tokens.py.
Design: DESIGN.md and docs/design/maquette-v2/export/SPEC.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import streamlit as st

# Streamlit Community Cloud runs this file without installing the project: make the
# repository root importable so that "src.dashboard" resolves (no effect in Docker).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.dashboard.client import ApiError  # noqa: E402
from src.dashboard.common import (  # noqa: E402, F401  (re-exported for the tests)
    CSS,
    MAP_SCRIPT,
    commodity_fr,
    css,
    current_theme,
    forced_theme,
    gain_summary,
    number_format,
    restore_params,
    theme_script,
)

HERE = Path(__file__).parent
BRAND = HERE / "static" / "brand"


def fetch_api_health(api_base_url: str) -> dict[str, object]:
    """Query the FastAPI health endpoint over HTTP (kept for the smoke tests)."""
    try:
        response = httpx.get(f"{api_base_url}/api/v1/health", timeout=5.0)
        response.raise_for_status()
        return dict(response.json())
    except httpx.HTTPError as exc:
        return {"status": "unreachable", "error": str(exc)}


def pages() -> list:
    return [
        st.Page(str(HERE / "views/home.py"), title="Ce mois-ci", url_path="", default=True),
        st.Page(str(HERE / "views/marche.py"), title="Marchés", url_path="marches"),
        st.Page(str(HERE / "views/facteurs.py"), title="Facteurs", url_path="facteurs"),
        st.Page(str(HERE / "views/fiabilite.py"), title="Fiabilité", url_path="fiabilite"),
        st.Page(str(HERE / "views/donnees.py"), title="Données & API", url_path="donnees"),
    ]


LOADING_HTML = (
    '<div class="ap-loading" role="status" aria-live="polite"><b>Chargement des données…</b> '
    "Après une période sans visite, le service se réveille : cela peut prendre jusqu'à une "
    "minute.</div>"
)


def theme_button(theme: str) -> None:
    """Light/dark switch: a real button (44 px), pinned in the header band by CSS.

    It writes the choice in the URL (?theme=sombre|clair); THEME_SCRIPT applies it."""
    with st.container(key="theme_toggle"):
        dark = theme == "dark"
        label = "Mode clair" if dark else "Mode sombre"
        icon = ":material/light_mode:" if dark else ":material/dark_mode:"
        if st.button(label, icon=icon, help="Changer le thème de couleur", key="theme_btn"):
            st.query_params["theme"] = "clair" if dark else "sombre"
            st.rerun()


def main() -> None:
    """Render the AgriPrix Observatory dashboard."""
    theme = current_theme()
    # Light mode: the logo as given (transparent); dark mode: its version with a white eye.
    suffix = "-sombre" if theme == "dark" else ""
    st.set_page_config(page_title="AgriPrix Observatory",
                       page_icon=str(BRAND / f"favicon-32{suffix}.png"), layout="wide")  # fmt: skip
    st.logo(str(BRAND / f"agriprix-lockup{suffix}.png"), size="large")
    st.markdown(css(theme), unsafe_allow_html=True)
    st.html(theme_script(theme) + MAP_SCRIPT, unsafe_allow_javascript=True)
    page = st.navigation(pages(), position="top")
    restore_params()
    theme_button(theme)
    # Shown at once, before the first API call: after a quiet period the free API host
    # sleeps and takes up to about a minute to answer, which used to leave a blank page.
    loading = st.empty()
    loading.markdown(LOADING_HTML, unsafe_allow_html=True)
    try:
        page.run()
    except ApiError as exc:
        st.error(f"{exc} Les données s'afficheront dès que le service sera de nouveau disponible.")
    finally:
        loading.empty()


if __name__ == "__main__":  # pragma: no cover
    main()
