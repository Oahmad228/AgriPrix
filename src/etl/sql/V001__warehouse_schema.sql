-- =============================================================================
-- V001 - AgriPrix warehouse core schema (Sprint 1: ingestion layer)
-- Star schema described in docs/diagrams/06-modele-donnees.md.
-- Objects are created in the current search_path schema (public in production,
-- a throw-away schema in integration tests).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Dimensions and reference tables
-- -----------------------------------------------------------------------------
CREATE TABLE dim_country (
    country_iso3        VARCHAR(3)   PRIMARY KEY,
    country_name_fr     VARCHAR(100) NOT NULL,
    default_currency    VARCHAR(10)  NOT NULL,
    primary_source      VARCHAR(30)  NOT NULL CHECK (primary_source IN ('WFP_HDX', 'FAOSTAT')),
    lean_season_months  VARCHAR(20),
    max_observed_date   DATE
);

CREATE TABLE dim_market (
    market_code         VARCHAR(64)  PRIMARY KEY,
    country_iso3        VARCHAR(3)   NOT NULL REFERENCES dim_country (country_iso3),
    source_market_id    INTEGER,
    market_name         VARCHAR(120) NOT NULL,
    admin1_region       VARCHAR(100),
    admin2_district     VARCHAR(100),
    latitude            NUMERIC(9, 6) CHECK (latitude BETWEEN -90 AND 90),
    longitude           NUMERIC(9, 6) CHECK (longitude BETWEEN -180 AND 180),
    granularity_level   VARCHAR(15)  NOT NULL CHECK (granularity_level IN ('MARKET', 'NATIONAL')),
    CONSTRAINT uq_market_country UNIQUE (market_code, country_iso3),
    CONSTRAINT chk_market_gps_by_grain CHECK (
        (granularity_level = 'NATIONAL' AND latitude IS NULL AND longitude IS NULL)
        OR granularity_level = 'MARKET'
    )
);

CREATE TABLE dim_commodity (
    commodity_code            VARCHAR(64)  PRIMARY KEY,
    source_commodity_id       INTEGER,
    commodity_name_en         VARCHAR(150) NOT NULL,
    commodity_name_fr         VARCHAR(150),
    commodity_group           VARCHAR(50)  NOT NULL,
    category                  VARCHAR(50),
    is_food_security_basket   BOOLEAN      NOT NULL
);

CREATE TABLE ref_unit_conversion (
    raw_unit                  VARCHAR(30)    PRIMARY KEY,
    canonical_unit            VARCHAR(30)    NOT NULL,
    multiplier_to_canonical   NUMERIC(14, 6) NOT NULL CHECK (multiplier_to_canonical > 0),
    is_metric_convertible     BOOLEAN        NOT NULL,
    CONSTRAINT chk_non_metric_identity CHECK (
        is_metric_convertible OR (canonical_unit = raw_unit AND multiplier_to_canonical = 1)
    )
);

CREATE TABLE dim_calendar (
    calendar_id         INTEGER      PRIMARY KEY,
    frequency           VARCHAR(10)  NOT NULL CHECK (frequency IN ('MONTHLY', 'ANNUAL')),
    reference_year      SMALLINT     NOT NULL CHECK (reference_year BETWEEN 1980 AND 2050),
    reference_month     SMALLINT,
    period_start_date   DATE         NOT NULL,
    wfp_reference_date  DATE,
    quarter_num         SMALLINT,
    CONSTRAINT uq_calendar_freq UNIQUE (calendar_id, frequency),
    -- Annual periods never carry an invented month (docs/02-sources-donnees.md).
    CONSTRAINT chk_calendar_frequency_month CHECK (
        (frequency = 'ANNUAL' AND reference_month IS NULL AND wfp_reference_date IS NULL
            AND quarter_num IS NULL AND calendar_id = reference_year * 100)
        OR
        (frequency = 'MONTHLY' AND reference_month BETWEEN 1 AND 12
            AND calendar_id = reference_year * 100 + reference_month)
    )
);

CREATE TABLE dim_series_catalog (
    series_id                 SERIAL       PRIMARY KEY,
    series_natural_key        VARCHAR(255) NOT NULL UNIQUE,
    market_code               VARCHAR(64)  NOT NULL,
    country_iso3              VARCHAR(3)   NOT NULL,
    commodity_code            VARCHAR(64)  NOT NULL REFERENCES dim_commodity (commodity_code),
    price_type                VARCHAR(20)  NOT NULL,
    unit_measure              VARCHAR(30)  NOT NULL,
    currency_code             VARCHAR(10)  NOT NULL,
    frequency                 VARCHAR(10)  NOT NULL CHECK (frequency IN ('MONTHLY', 'ANNUAL')),
    value_type                VARCHAR(20)  NOT NULL CHECK (value_type IN ('PRICE', 'INDEX', 'INFLATION_RATE')),
    granularity_level         VARCHAR(15)  NOT NULL CHECK (granularity_level IN ('MARKET', 'NATIONAL')),
    total_observed_count      INTEGER      NOT NULL DEFAULT 0,
    recent_continuous_months  INTEGER      NOT NULL DEFAULT 0,
    max_consecutive_missing   INTEGER,
    first_obs_date            DATE,
    last_obs_date             DATE,
    is_ml_eligible            BOOLEAN      NOT NULL DEFAULT FALSE,
    ineligibility_reason      VARCHAR(120),
    CONSTRAINT uq_series_freq UNIQUE (series_id, frequency),
    CONSTRAINT fk_series_market_country
        FOREIGN KEY (market_code, country_iso3) REFERENCES dim_market (market_code, country_iso3),
    -- DQ-06: annual series can never be eligible for monthly forecasting.
    CONSTRAINT chk_eligible_monthly CHECK (NOT is_ml_eligible OR frequency = 'MONTHLY'),
    CONSTRAINT chk_eligibility_reason CHECK (
        (is_ml_eligible AND ineligibility_reason IS NULL)
        OR (NOT is_ml_eligible AND ineligibility_reason IS NOT NULL)
    )
);

-- -----------------------------------------------------------------------------
-- ETL audit trail
-- -----------------------------------------------------------------------------
CREATE TABLE etl_run_audit (
    etl_run_id            SERIAL       PRIMARY KEY,
    started_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at           TIMESTAMPTZ,
    status                VARCHAR(20)  NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    rows_read             INTEGER,
    rows_upserted         INTEGER,
    rows_rejected         INTEGER,
    ml_eligible_series    INTEGER,
    git_sha               VARCHAR(40),
    error_message         TEXT
);

-- One row per source file used by a run: makes every published number traceable
-- to the exact file version (MD5) it was computed from.
CREATE TABLE etl_source_file (
    source_file_id        SERIAL       PRIMARY KEY,
    etl_run_id            INTEGER      NOT NULL REFERENCES etl_run_audit (etl_run_id),
    source_name           VARCHAR(60)  NOT NULL,
    url                   TEXT         NOT NULL,
    size_bytes            BIGINT       NOT NULL CHECK (size_bytes > 0),
    md5                   CHAR(32)     NOT NULL,
    remote_last_modified  VARCHAR(40),
    from_cache            BOOLEAN      NOT NULL,
    retrieved_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_per_run UNIQUE (etl_run_id, source_name)
);

CREATE TABLE audit_rejected_rows (
    rejected_id           BIGSERIAL    PRIMARY KEY,
    etl_run_id            INTEGER      NOT NULL REFERENCES etl_run_audit (etl_run_id),
    source_file           VARCHAR(60)  NOT NULL,
    line_number           INTEGER,
    reason_code           VARCHAR(50)  NOT NULL,
    raw_payload_json      TEXT         NOT NULL,
    rejected_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- Fact table
-- -----------------------------------------------------------------------------
CREATE TABLE fact_price_observation (
    observation_id   BIGSERIAL      PRIMARY KEY,
    series_id        INTEGER        NOT NULL,
    calendar_id      INTEGER        NOT NULL,
    frequency        VARCHAR(10)    NOT NULL,
    observed_value   NUMERIC(14, 4) NOT NULL,
    raw_value        NUMERIC(14, 4) NOT NULL,
    raw_unit         VARCHAR(30)    NOT NULL REFERENCES ref_unit_conversion (raw_unit),
    source_flag      VARCHAR(20)    NOT NULL,
    is_observed      BOOLEAN        NOT NULL,
    etl_run_id       INTEGER        NOT NULL REFERENCES etl_run_audit (etl_run_id),
    ingested_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT fk_obs_series_freq
        FOREIGN KEY (series_id, frequency) REFERENCES dim_series_catalog (series_id, frequency),
    CONSTRAINT fk_obs_calendar_freq
        FOREIGN KEY (calendar_id, frequency) REFERENCES dim_calendar (calendar_id, frequency),
    -- WFP: actual / aggregate. FAOSTAT quality flags: A/blank -> fao_official,
    -- X -> fao_external, B -> fao_break, E -> fao_estimated, I -> fao_imputed.
    -- Only measured values are "observed" and usable for ML (ADR-009).
    CONSTRAINT chk_obs_source_flag CHECK (
        (source_flag IN ('actual', 'fao_official', 'fao_external', 'fao_break') AND is_observed)
        OR (source_flag IN ('aggregate', 'fao_estimated', 'fao_imputed') AND NOT is_observed)
    ),
    CONSTRAINT uq_observation_series_calendar_flag UNIQUE (series_id, calendar_id, source_flag)
);

CREATE INDEX ix_obs_series_calendar ON fact_price_observation (series_id, calendar_id);
CREATE INDEX ix_series_country_commodity ON dim_series_catalog (country_iso3, commodity_code);
CREATE INDEX ix_series_eligible ON dim_series_catalog (is_ml_eligible) WHERE is_ml_eligible;
CREATE INDEX ix_rejected_run ON audit_rejected_rows (etl_run_id);
