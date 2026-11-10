"""Read-only database access for the API (role agriprix_api_readonly, never the writer)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_settings

logger = logging.getLogger("agriprix.api")


@lru_cache
def get_engine() -> Engine:
    """One pooled engine per process, connected with the read-only role."""
    return create_engine(
        get_settings().readonly_database_url, pool_pre_ping=True, pool_size=5, max_overflow=5
    )


def get_connection() -> Iterator[Connection]:
    """FastAPI dependency: one connection per request, in a read-only transaction."""
    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        yield conn


def check_database_readonly_connection() -> tuple[bool, str]:
    """Verify connectivity to agriprix_dw using the read-only SQL role."""
    try:
        with get_engine().connect() as conn:
            role_name = conn.execute(text("SELECT current_user")).scalar_one()
        return True, f"connected as {role_name}"
    except SQLAlchemyError:
        # Never expose driver error text (hosts, role names) on a public endpoint.
        logger.exception("Read-only warehouse connection failed")
        return False, "database unreachable"
