#!/bin/sh
# =============================================================================
# AgriPrix Observatory - PostgreSQL 16 initialization (runs once, on an empty volume).
# Creates two isolated databases (agriprix_dw, mlflow_db) and three least-privilege roles.
# Passwords come from the environment (.env), never from this file (CLAUDE.md, ENF-06).
# =============================================================================
set -eu

: "${DW_WRITER_USER:?missing}" "${DW_WRITER_PASSWORD:?missing}"
: "${DW_READONLY_USER:?missing}" "${DW_READONLY_PASSWORD:?missing}"
: "${MLFLOW_DB_USER:?missing}" "${MLFLOW_DB_PASSWORD:?missing}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v writer="$DW_WRITER_USER" -v writer_pw="$DW_WRITER_PASSWORD" \
    -v reader="$DW_READONLY_USER" -v reader_pw="$DW_READONLY_PASSWORD" \
    -v mlflow="$MLFLOW_DB_USER" -v mlflow_pw="$MLFLOW_DB_PASSWORD" <<'SQL'
-- 1. Dedicated roles (psql variables: :"name" quotes an identifier, :'name' a literal)
CREATE ROLE :"writer" WITH LOGIN PASSWORD :'writer_pw';
CREATE ROLE :"reader" WITH LOGIN PASSWORD :'reader_pw';
CREATE ROLE :"mlflow" WITH LOGIN PASSWORD :'mlflow_pw';

-- 2. Isolated databases
CREATE DATABASE agriprix_dw OWNER :"writer";
CREATE DATABASE mlflow_db OWNER :"mlflow";

-- 3. Database-level isolation
REVOKE ALL ON DATABASE agriprix_dw FROM PUBLIC;
GRANT CONNECT ON DATABASE agriprix_dw TO :"writer";
GRANT CONNECT ON DATABASE agriprix_dw TO :"reader";
REVOKE ALL ON DATABASE mlflow_db FROM PUBLIC;
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE mlflow_db TO :"mlflow";

-- 4. Schema privileges inside agriprix_dw
\connect agriprix_dw
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO :"writer";
GRANT USAGE ON SCHEMA public TO :"reader";
-- Every table the writer creates is readable (SELECT only) by the read-only role.
ALTER DEFAULT PRIVILEGES FOR ROLE :"writer" IN SCHEMA public GRANT SELECT ON TABLES TO :"reader";
ALTER DEFAULT PRIVILEGES FOR ROLE :"writer" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"writer";
ALTER DEFAULT PRIVILEGES FOR ROLE :"writer" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"writer";

-- 5. Schema privileges inside mlflow_db
\connect mlflow_db
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO :"mlflow";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mlflow" IN SCHEMA public GRANT ALL ON TABLES TO :"mlflow";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mlflow" IN SCHEMA public GRANT ALL ON SEQUENCES TO :"mlflow";
SQL
