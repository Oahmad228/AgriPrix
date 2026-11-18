-- =============================================================================
-- V005 - Log-symmetric conformal intervals (ADR-004 section 3).
-- Rows written before this migration used signed relative errors ("signed_relative",
-- v1.0-baseline). New rows record their method and the median recent log error, shown to
-- visitors as a bias sentence; the forecast itself is never corrected.
-- =============================================================================

ALTER TABLE fact_conformal_quantiles
    ADD COLUMN interval_method  VARCHAR(30) NOT NULL DEFAULT 'signed_relative',
    ADD COLUMN median_log_error NUMERIC(10, 6);
