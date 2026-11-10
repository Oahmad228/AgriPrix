"""Database helpers: engines, schema migrations and fast bulk loading (COPY)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, event, text

from src.config import get_settings

logger = logging.getLogger("agriprix.etl.db")

MIGRATIONS_DIR = Path(__file__).parent / "sql"


def make_writer_engine(schema: str | None = None) -> Engine:
    """Return an engine using the read-write ETL role.

    When ``schema`` is given, every connection uses it as search_path. Integration
    tests rely on this to work in an isolated, throw-away schema.
    """
    engine = create_engine(get_settings().writer_database_url, pool_pre_ping=True)
    if schema is not None:

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_connection, _record) -> None:  # pragma: no cover - driver hook
            with dbapi_connection.cursor() as cur:
                cur.execute(f'SET search_path TO "{schema}"')
            dbapi_connection.commit()

    return engine


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("V*__*.sql"))


def apply_migrations(conn: Connection) -> list[str]:
    """Apply pending versioned SQL migrations in order; return applied versions.

    A migration whose file content changed after being applied is a hard error:
    applied migrations are immutable, changes go into a new V00N file.
    """
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version VARCHAR(20) PRIMARY KEY,"
            " checksum CHAR(64) NOT NULL,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
    )
    applied = dict(conn.execute(text("SELECT version, checksum FROM schema_migrations")).all())
    newly_applied: list[str] = []
    for path in _migration_files():
        version = path.name.split("__")[0]
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        if version in applied:
            if applied[version] != checksum:
                raise RuntimeError(
                    f"Migration {path.name} was modified after being applied; "
                    "create a new migration file instead."
                )
            continue
        logger.info("Applying migration %s", path.name)
        conn.exec_driver_sql(sql)
        conn.execute(
            text("INSERT INTO schema_migrations (version, checksum) VALUES (:v, :c)"),
            {"v": version, "c": checksum},
        )
        newly_applied.append(version)
    return newly_applied


def copy_rows(
    conn: Connection, table: str, columns: Sequence[str], rows: Iterable[Sequence[object]]
) -> int:
    """Bulk-insert rows with PostgreSQL COPY (much faster than INSERT for 300k+ rows)."""
    raw = conn.connection.driver_connection
    count = 0
    column_list = ", ".join(columns)
    with raw.cursor() as cur, cur.copy(f"COPY {table} ({column_list}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count
