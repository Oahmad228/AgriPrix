"""Streamlit dashboard entry point (communicates strictly via FastAPI HTTP)."""

import os

import httpx
import streamlit as st


def fetch_api_health(api_base_url: str) -> dict[str, object]:
    """Query the FastAPI health endpoint over HTTP."""
    try:
        response = httpx.get(f"{api_base_url}/api/v1/health", timeout=5.0)
        response.raise_for_status()
        return dict(response.json())
    except httpx.HTTPError as exc:
        return {"status": "unreachable", "error": str(exc)}


def main() -> None:
    """Render the AgriPrix Observatory Streamlit UI."""
    st.set_page_config(
        page_title="AgriPrix Observatory",
        page_icon="🌾",
        layout="wide",
    )
    st.title("🌾 AgriPrix Observatory")
    st.subheader(
        "Suivi, détection d'anomalies et prévision conforme (1, 3, 6 mois) "
        "des prix alimentaires — Afrique de l'Ouest (UEMOA) & Maroc"
    )

    api_base_url = os.getenv("API_BASE_URL", "http://api:8000")
    health = fetch_api_health(api_base_url)

    col1, col2, col3 = st.columns(3)
    col1.metric("Statut API FastAPI", str(health.get("status", "unknown")).upper())
    db_info = health.get("database", {})
    db_status = (
        "CONNECTÉ (RO)" if isinstance(db_info, dict) and db_info.get("connected") else "EN ATTENTE"
    )
    col2.metric("Entrepôt PostgreSQL (agriprix_dw)", db_status)
    col3.metric("Périmètre Cible ML", "738 séries (19 groupes)")

    st.info(
        "Socle technique Phase 3 opérationnel (`docker compose up`). "
        "Le chargement de l'entrepôt en étoile s'effectue au Sprint 1 (`make etl`)."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
