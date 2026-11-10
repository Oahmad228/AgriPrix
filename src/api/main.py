"""FastAPI service entry point for AgriPrix Observatory (Phase 3 foundation)."""

import logging

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src import __version__
from src.config import get_settings

settings = get_settings()
logger = logging.getLogger("agriprix.api")

app = FastAPI(
    title="AgriPrix Observatory API",
    description=(
        "Public REST API for West Africa (UEMOA) and Morocco food price monitoring, "
        "anomaly detection, and 1, 3, and 6-month conformal forecasting."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def check_database_readonly_connection() -> tuple[bool, str]:
    """Verify connectivity to agriprix_dw using the read-only SQL role."""
    try:
        engine = create_engine(settings.readonly_database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            role_name = conn.execute(text("SELECT current_user")).scalar_one()
        engine.dispose()
        return True, f"connected as {role_name}"
    except SQLAlchemyError:
        # Never expose driver error text (hosts, role names) on a public endpoint.
        logger.exception("Read-only warehouse connection failed")
        return False, "database unreachable"


@app.get(
    "/api/v1/health",
    tags=["System"],
    responses={503: {"description": "Database unreachable (service degraded)"}},
)
def get_health(response: Response) -> dict[str, object]:
    """Return service health and read-only database connectivity.

    Responds HTTP 503 when the warehouse is unreachable so that Docker healthchecks,
    CI and the reverse proxy never report a broken service as healthy.
    """
    db_ok, db_detail = check_database_readonly_connection()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "agriprix-api",
        "version": __version__,
        "environment": settings.app_env,
        "database": {
            "name": settings.dw_db,
            "connected": db_ok,
            "detail": db_detail,
        },
        "feature_flags": {
            "enable_currency_conversion": settings.enable_currency_conversion,
        },
    }
