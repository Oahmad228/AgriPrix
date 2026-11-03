-- =============================================================================
-- AgriPrix Observatory — PostgreSQL 16 Initialization Script
-- Creates two isolated databases (agriprix_dw and mlflow_db) and three
-- least-privilege roles (agriprix_etl_writer, agriprix_api_readonly, mlflow_user).
-- =============================================================================

-- 1. Create dedicated roles
CREATE ROLE agriprix_etl_writer WITH LOGIN PASSWORD 'agriprix_writer_local_dev';
CREATE ROLE agriprix_api_readonly WITH LOGIN PASSWORD 'agriprix_readonly_local_dev';
CREATE ROLE mlflow_user WITH LOGIN PASSWORD 'agriprix_mlflow_local_dev';

-- 2. Create isolated databases
CREATE DATABASE agriprix_dw OWNER agriprix_etl_writer;
CREATE DATABASE mlflow_db OWNER mlflow_user;

-- 3. Enforce strict database-level isolation
REVOKE ALL ON DATABASE agriprix_dw FROM PUBLIC;
GRANT CONNECT ON DATABASE agriprix_dw TO agriprix_etl_writer;
GRANT CONNECT ON DATABASE agriprix_dw TO agriprix_api_readonly;

REVOKE ALL ON DATABASE mlflow_db FROM PUBLIC;
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE mlflow_db TO mlflow_user;

-- 4. Configure schema privileges inside agriprix_dw
\connect agriprix_dw

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO agriprix_etl_writer;
GRANT USAGE ON SCHEMA public TO agriprix_api_readonly;

-- Ensure any table or sequence created by agriprix_etl_writer is automatically
-- readable (SELECT ONLY) by agriprix_api_readonly
ALTER DEFAULT PRIVILEGES FOR ROLE agriprix_etl_writer IN SCHEMA public
    GRANT SELECT ON TABLES TO agriprix_api_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE agriprix_etl_writer IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agriprix_etl_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE agriprix_etl_writer IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO agriprix_etl_writer;

-- 5. Configure schema privileges inside mlflow_db
\connect mlflow_db

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO mlflow_user;
ALTER DEFAULT PRIVILEGES FOR ROLE mlflow_user IN SCHEMA public
    GRANT ALL ON TABLES TO mlflow_user;
ALTER DEFAULT PRIVILEGES FOR ROLE mlflow_user IN SCHEMA public
    GRANT ALL ON SEQUENCES TO mlflow_user;
