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
    commodity_fr,
    gain_summary,
    number_format,
    restore_params,
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


def main() -> None:
    """Render the AgriPrix Observatory dashboard."""
    st.set_page_config(
        page_title="AgriPrix Observatory", page_icon=str(BRAND / "favicon-32.png"), layout="wide"
    )
    st.logo(str(BRAND / "agriprix-lockup.png"), size="large")
    st.markdown(CSS, unsafe_allow_html=True)
    page = st.navigation(pages(), position="top")
    restore_params()
    try:
        page.run()
    except ApiError as exc:
        st.error(f"{exc} Les données s'afficheront dès que le service sera de nouveau disponible.")


if __name__ == "__main__":  # pragma: no cover
    main()
