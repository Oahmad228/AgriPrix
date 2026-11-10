-- =============================================================================
-- V004 - Pre-computed final-test (W3) quality of each champion, so that the API serves
-- it with a primary-key join instead of aggregating thousands of metric rows per request.
-- =============================================================================

ALTER TABLE fact_champion_model
    ADD COLUMN test_picp_80 NUMERIC(6, 4) CHECK (test_picp_80 BETWEEN 0 AND 1),
    ADD COLUMN test_mape    NUMERIC(10, 4);
