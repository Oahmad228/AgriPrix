"""FastAPI service entry point for AgriPrix Observatory (Phase 3 foundation)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src import __version__
from src.config import get_settings

settings = get_settings()

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
    except SQLAlchemyError as exc:
        return False, str(exc)


@app.get("/api/v1/health", tags=["System"])
def get_health() -> dict[str, object]:
    """Return service health status and read-only database connectivity."""
    db_ok, db_detail = check_database_readonly_connection()
    return {
        "status": "ok",
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
