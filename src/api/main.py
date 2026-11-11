"""FastAPI service entry point for AgriPrix Observatory.

Security posture of the public API (ENF-04/05/06):
- connects to the warehouse with a read-only role, inside READ ONLY transactions;
- exposes GET routes only; nothing can write or trigger a training run;
- rate-limited per client (HTTP 429 beyond the quota);
- CORS restricted to configured origins;
- unexpected errors return a generic message; details go to the server logs only.
"""

import logging

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src import __version__
from src.api.db import check_database_readonly_connection
from src.api.limits import current_request, limiter
from src.api.routes import router
from src.config import get_settings

settings = get_settings()
logger = logging.getLogger("agriprix.api")

DESCRIPTION = """
Public read-only API of AgriPrix Observatory: food prices of West Africa (UEMOA, WFP data,
licence CC BY-IGO 3.0) and Morocco (FAOSTAT, CC BY 4.0), price alerts and 1/3/6-month
forecasts with 80 % intervals.

Forecasts and alerts are computed by AgriPrix Observatory, not by WFP or FAO. Every value is
expressed in local currency (XOF, MAD) or as an index; nothing is converted.
"""

app = FastAPI(
    title="AgriPrix Observatory API",
    description=DESCRIPTION,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router)


@app.middleware("http")
async def remember_request(request: Request, call_next):
    """Expose the current request to the rate limiter's exemption rule."""
    token = current_request.set(request)
    try:
        return await call_next(request)
    finally:
        current_request.reset(token)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
