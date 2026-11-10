-- =============================================================================
-- V002 - Forecasting layer (Sprint 2): training runs, metrics, conformal quantiles,
-- champion models and forecasts. Every analytical row belongs to a training_run so
-- that the API can serve the active run while older runs stay auditable.
-- =============================================================================

CREATE TABLE training_run (
    run_id                SERIAL       PRIMARY KEY,
    run_timestamp         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at           TIMESTAMPTZ,
    status                VARCHAR(20)  NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    etl_run_id            INTEGER      REFERENCES etl_run_audit (etl_run_id),
    max_data_date         DATE,
    git_sha               VARCHAR(40),
    mlflow_parent_run_id  VARCHAR(64),
    is_production_active  BOOLEAN      NOT NULL DEFAULT FALSE,
    error_message         TEXT
);
-- At most one run is served by the API at any time.
CREATE UNIQUE INDEX uq_training_run_single_active ON training_run (is_production_active)
    WHERE is_production_active;

CREATE TABLE fact_model_metrics_by_series (
    metric_id             BIGSERIAL     PRIMARY KEY,
    run_id                INTEGER       NOT NULL REFERENCES training_run (run_id),
    series_id             INTEGER       NOT NULL REFERENCES dim_series_catalog (series_id),
    model_name            VARCHAR(50)   NOT NULL,
    horizon_months        SMALLINT      NOT NULL CHECK (horizon_months IN (1, 3, 6)),
    eval_window           VARCHAR(30)   NOT NULL,
    n_eval_points         INTEGER       NOT NULL CHECK (n_eval_points > 0),
    mae                   NUMERIC(14, 4) NOT NULL,
    rmse                  NUMERIC(14, 4) NOT NULL,
    mape                  NUMERIC(10, 4),
    mase                  NUMERIC(10, 4),
    rel_mae               NUMERIC(10, 4),
    picp_80               NUMERIC(6, 4) CHECK (picp_80 BETWEEN 0 AND 1),
    mlflow_group_run_id   VARCHAR(64),
    CONSTRAINT uq_metrics_run_series_model_h_win
        UNIQUE (run_id, series_id, model_name, horizon_months, eval_window)
);

CREATE TABLE fact_conformal_quantiles (
    quantile_id              SERIAL        PRIMARY KEY,
    run_id                   INTEGER       NOT NULL REFERENCES training_run (run_id),
    country_iso3             VARCHAR(3)    NOT NULL REFERENCES dim_country (country_iso3),
    commodity_group          VARCHAR(50)   NOT NULL,
    model_name               VARCHAR(50)   NOT NULL,
    horizon_months           SMALLINT      NOT NULL CHECK (horizon_months IN (1, 3, 6)),
    eval_window              VARCHAR(30)   NOT NULL,
    calibration_window       VARCHAR(30)   NOT NULL,
    n_calibration_residuals  INTEGER       NOT NULL CHECK (n_calibration_residuals > 0),
    q_rel_10                 NUMERIC(10, 6) NOT NULL,
    q_rel_90                 NUMERIC(10, 6) NOT NULL,
    CONSTRAINT chk_quantile_order CHECK (q_rel_10 <= q_rel_90),
    CONSTRAINT uq_quantiles_run_group_model_h_win
        UNIQUE (run_id, country_iso3, commodity_group, model_name, horizon_months, eval_window)
);

CREATE TABLE fact_champion_model (
    run_id                 INTEGER      NOT NULL REFERENCES training_run (run_id),
    country_iso3           VARCHAR(3)   NOT NULL REFERENCES dim_country (country_iso3),
    commodity_group        VARCHAR(50)  NOT NULL,
    horizon_months         SMALLINT     NOT NULL CHECK (horizon_months IN (1, 3, 6)),
    champion_model_name    VARCHAR(50)  NOT NULL,
    median_rel_mae_val     NUMERIC(10, 4),
    median_mase_val        NUMERIC(10, 4),
    selection_rule         VARCHAR(200) NOT NULL,
    PRIMARY KEY (run_id, country_iso3, commodity_group, horizon_months)
);

CREATE TABLE fact_forecast (
    forecast_id            BIGSERIAL     PRIMARY KEY,
    run_id                 INTEGER       NOT NULL REFERENCES training_run (run_id),
    series_id              INTEGER       NOT NULL REFERENCES dim_series_catalog (series_id),
    origin_calendar_id     INTEGER       NOT NULL REFERENCES dim_calendar (calendar_id),
    target_calendar_id     INTEGER       NOT NULL REFERENCES dim_calendar (calendar_id),
    horizon_months         SMALLINT      NOT NULL CHECK (horizon_months IN (1, 3, 6)),
    yhat_point             NUMERIC(14, 4) NOT NULL CHECK (yhat_point > 0),
    yhat_lower_80          NUMERIC(14, 4) NOT NULL CHECK (yhat_lower_80 >= 0),
    yhat_upper_80          NUMERIC(14, 4) NOT NULL,
    champion_model_name    VARCHAR(50)   NOT NULL,
    mlflow_group_run_id    VARCHAR(64),
    -- The point forecast may fall outside the interval when calibration errors are all of
    -- one sign (biased model): the interval reflects observed errors, it is not forced
    -- to contain the point.
    CONSTRAINT chk_forecast_interval CHECK (yhat_lower_80 <= yhat_upper_80),
    CONSTRAINT chk_forecast_target_after_origin CHECK (target_calendar_id > origin_calendar_id),
    CONSTRAINT uq_forecast_run_series_origin_h
        UNIQUE (run_id, series_id, origin_calendar_id, horizon_months)
);

CREATE INDEX ix_forecast_series ON fact_forecast (series_id, run_id);
CREATE INDEX ix_metrics_run_window ON fact_model_metrics_by_series (run_id, eval_window, model_name);
