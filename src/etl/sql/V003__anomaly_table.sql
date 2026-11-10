-- =============================================================================
-- V003 - Anomaly detection results (Sprint 3), versioned by training_run.
-- Only alerts are stored (|z| >= 2.5); the sign of z gives the direction.
-- =============================================================================

CREATE TABLE fact_anomaly (
    anomaly_id        BIGSERIAL      PRIMARY KEY,
    run_id            INTEGER        NOT NULL REFERENCES training_run (run_id),
    series_id         INTEGER        NOT NULL REFERENCES dim_series_catalog (series_id),
    calendar_id       INTEGER        NOT NULL REFERENCES dim_calendar (calendar_id),
    observed_value    NUMERIC(14, 4) NOT NULL CHECK (observed_value > 0),
    expected_value    NUMERIC(14, 4) NOT NULL CHECK (expected_value > 0),
    log_residual      NUMERIC(10, 4) NOT NULL,
    z_score_robust    NUMERIC(8, 3)  NOT NULL,
    yoy_change_pct    NUMERIC(8, 2),
    direction         VARCHAR(4)     NOT NULL CHECK (direction IN ('UP', 'DOWN')),
    severity          VARCHAR(15)    NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),
    CONSTRAINT chk_anomaly_direction CHECK (
        (direction = 'UP' AND z_score_robust > 0) OR (direction = 'DOWN' AND z_score_robust < 0)
    ),
    CONSTRAINT chk_anomaly_severity CHECK (
        (severity = 'WARNING' AND ABS(z_score_robust) >= 2.5 AND ABS(z_score_robust) < 3.5)
        OR (severity = 'CRITICAL' AND ABS(z_score_robust) >= 3.5)
    ),
    CONSTRAINT uq_anomaly_run_series_cal UNIQUE (run_id, series_id, calendar_id)
);

CREATE INDEX ix_anomaly_run_calendar ON fact_anomaly (run_id, calendar_id);
CREATE INDEX ix_anomaly_series ON fact_anomaly (series_id, run_id);
