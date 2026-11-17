#!/bin/sh
# One-time setup of the managed warehouse on Neon (ADR-013): the same least-privilege
# design as docker/postgres/01-init.sh (writer role, read-only role, isolated database),
# minus MLflow, which stays local. Tables are then created by the ETL migrations.
#
# Run from the repository root, with the values in .env.neon (never committed):
#   docker run --rm --env-file .env.neon -v "$PWD/deploy/neon:/s:ro" postgres:16-alpine sh /s/init.sh
set -eu
: "${NEON_HOST:?missing}" "${NEON_OWNER_USER:?missing}" "${NEON_OWNER_PASSWORD:?missing}"
: "${DW_WRITER_USER:?missing}" "${DW_WRITER_PASSWORD:?missing}"
: "${DW_READONLY_USER:?missing}" "${DW_READONLY_PASSWORD:?missing}"
export PGHOST="$NEON_HOST" PGSSLMODE=require

PGUSER="$NEON_OWNER_USER" PGPASSWORD="$NEON_OWNER_PASSWORD" psql -v ON_ERROR_STOP=1 -d neondb \
    -v writer="$DW_WRITER_USER" -v writer_pw="$DW_WRITER_PASSWORD" \
    -v reader="$DW_READONLY_USER" -v reader_pw="$DW_READONLY_PASSWORD" \
    -v owner="$NEON_OWNER_USER" <<'SQL'
CREATE ROLE :"writer" WITH LOGIN PASSWORD :'writer_pw';
CREATE ROLE :"reader" WITH LOGIN PASSWORD :'reader_pw';
GRANT :"writer" TO :"owner";
CREATE DATABASE agriprix_dw OWNER :"writer";
REVOKE ALL ON DATABASE agriprix_dw FROM PUBLIC;
GRANT CONNECT ON DATABASE agriprix_dw TO :"writer";
GRANT CONNECT ON DATABASE agriprix_dw TO :"reader";
SQL

# Inside the warehouse, as the writer (owner of the database and of schema public).
PGUSER="$DW_WRITER_USER" PGPASSWORD="$DW_WRITER_PASSWORD" psql -v ON_ERROR_STOP=1 -d agriprix_dw \
    -v reader="$DW_READONLY_USER" <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"reader";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :"reader";
SQL
echo "Neon warehouse ready: database agriprix_dw, roles $DW_WRITER_USER and $DW_READONLY_USER."
