"""Phase 3 foundation smoke tests verifying configuration, API health, DB isolation, and CLIs."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.api.db import check_database_readonly_connection
from src.api.main import app
from src.config import Settings, get_settings
from src.dashboard.app import fetch_api_health
from src.etl.cli import run_etl_status
from src.ml.cli import run_ml_status


def test_settings_urls_and_cors() -> None:
    """Verify database connection URLs and CORS parsing from Settings."""
    cfg = Settings(
        postgres_host="db",
        postgres_port=5432,
        dw_db="agriprix_dw",
        dw_writer_user="writer_u",
        dw_writer_password="pw1",
        dw_readonly_user="ro_u",
        dw_readonly_password="pw2",
        cors_origins="http://localhost:8501, http://dashboard:8501",
    )
    assert "writer_u:pw1@db:5432/agriprix_dw" in cfg.writer_database_url
    assert "ro_u:pw2@db:5432/agriprix_dw" in cfg.readonly_database_url
    assert cfg.cors_origin_list == ["http://localhost:8501", "http://dashboard:8501"]
    assert get_settings().dw_db == "agriprix_dw"


def test_api_health_endpoint() -> None:
    """Verify /api/v1/health returns HTTP 200 when the warehouse is reachable."""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "agriprix-api"
    assert payload["database"]["connected"] is True
    assert "feature_flags" in payload


def test_api_health_returns_503_when_database_is_down() -> None:
    """Verify /api/v1/health reports 503 'degraded' without leaking driver errors."""
    client = TestClient(app)
    with patch(
        "src.api.main.check_database_readonly_connection",
        return_value=(False, "database unreachable"),
    ):
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"]["connected"] is False
    assert payload["database"]["detail"] == "database unreachable"


def test_readonly_connection_hides_driver_error_text() -> None:
    """Verify a failed connection returns a generic message (no host or role names)."""
    with patch("src.api.db.get_engine", side_effect=SQLAlchemyError("secret-host role-x")):
        ok, detail = check_database_readonly_connection()
    assert ok is False
    assert detail == "database unreachable"


def test_database_roles_and_isolation() -> None:
    """Verify the read-only role reaches agriprix_dw but is denied on mlflow_db.

    Tests run inside Docker Compose with the db service up: an unreachable
    database is a failure, never a silent pass.
    """
    ok, detail = check_database_readonly_connection()
    assert ok, f"warehouse must be reachable from the test container: {detail}"
    assert "agriprix_api_readonly" in detail

    cfg = get_settings()
    forbidden_url = (
        f"postgresql+psycopg://{cfg.dw_readonly_user}:{cfg.dw_readonly_password}"
        f"@{cfg.postgres_host}:{cfg.postgres_port}/mlflow_db"
    )
    engine = create_engine(forbidden_url)
    try:
        with pytest.raises(SQLAlchemyError, match="permission denied"), engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def test_etl_and_ml_cli_entrypoints() -> None:
    """Verify ETL and ML CLI status functions return valid metadata."""
    etl_res = run_etl_status()
    assert etl_res["pipeline"] == "etl"
    assert etl_res["status"] == "ready"

    ml_res = run_ml_status()
    assert ml_res["pipeline"] == "ml_training"
    assert ml_res["status"] == "ready"


def test_dashboard_fetch_api_health_unreachable() -> None:
    """Verify dashboard gracefully handles an unreachable API URL."""
    res = fetch_api_health("http://127.0.0.1:59999")
    assert res["status"] == "unreachable"
    assert "error" in res
