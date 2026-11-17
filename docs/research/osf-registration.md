# OSF registration text (ready to paste)

> How to use: on osf.io, create a project "AgriPrix — Sahel cereal price reversals", then **Registrations → New registration → "OSF Preregistration"** template (or "Open-Ended Registration" if you prefer one free-text field). Paste each section below into the matching field. Attach `docs/research/01-protocole.md` (French, the binding version) and the PDF export of this file.

---

**Title.** Do information available at forecast time (rainfall, harvest estimates, trade measures) improve price forecasts and prediction intervals during cereal price reversals in the Sahel? A pre-registered case study.

**Authors.** Ouedraogo Amine Ahmad (independent; MSc student). AI assistance: Claude Code (Anthropic), see "Other".

**Binding protocol.** `docs/research/01-protocole.md`, version 1.0, Git tag `protocol-v1`, commit `ce2b4f9787ef98a65eb67012926ff0c339680985`, public repository https://github.com/Oahmad228/AgriPrix (permalink: https://github.com/Oahmad228/AgriPrix/blob/protocol-v1/docs/research/01-protocole.md). Frozen reference system: tag `v1.0-baseline` (commit `beec094`). If this text and the protocol differ, the protocol prevails.

## Study information

**Research questions.**
1. Why do global machine-learning models trained on prices alone lose against the persistence forecast (last observed price) during price reversals?
2. Does information published at forecast time (CHIRPS rainfall, FAO-GIEWS harvest estimates, trade measures) reduce this loss and improve 80 % prediction interval coverage?

**Hypotheses.**
- **H1.** The loss of LightGBM against persistence is concentrated at origins where a 12-month rise (> +10 %) is followed by a fall (< −5 %). H1b: the symmetric case (fall then rise).
- **H2.** LightGBM trained on prices extrapolates the past 12-month momentum: the slope of its predicted h-month log-return on the past 12-month log change is positive and larger than the realized slope at reversals.
- **H3.** Adaptive conformal inference (Gibbs & Candès, 2021) or time-weighted conformal prediction (Barber et al., 2023) brings 6-month coverage closer to the 80 % target than the current split-conformal method, with mean width at most 1.25 times larger.
- **H4.** Adding external factors to LightGBM reduces its scaled error at reversals.

## Design plan

**Study type.** Observational forecasting study on public secondary data; no intervention, no human participants.

**Design.** Rolling-origin evaluation with monthly refitting (origins 2020-12 to 2026-07), direct forecasts at h = 1, 3, 6 months. Three evaluation sets by target month:
- DEV, 2021-01 to 2025-08: development evidence, since these years shaped the reference system;
- W3, 2025-09 to 2026-08: a posteriori only, already inspected;
- W4, targets from 2026-11 published by 2027-02-15: confirmatory, computed once with code frozen by a Git tag set before computation.

**Blinding / data status.** Price data up to 2026-10 already exist and were partly inspected (W3 results were published before this registration; the choice of harvest and trade factors was motivated by the W3 decline). **No analysis of the factor data and no result of this study had been computed at registration time.** W4 target data did not exist at registration.

## Sampling plan

**Existing data.** Registration prior to analysis of the factor data; price data partly observed, see above.

**Data.**
- 782 monthly retail price series (WFP via HDX, CC BY-IGO 3.0) in 19 country × commodity groups (Senegal, Mali, Burkina Faso, Niger; Morocco food CPI from FAOSTAT for the price-only part). The factor study uses the 18 WFP groups.
- CHIRPS v3 monthly rainfall (public domain), 25 km disc around each market.
- FAO-GIEWS country briefs (CC BY 4.0), one row per brief with its reference date.
- A manually validated table of export bans, border closures and sanctions with the publication date of each source.

**Sample size.** All eligible series and origins; no stopping rule. Few reversal episodes (mainly 2022 and 2025-26): this is a case study, not a general law.

## Variables

**Measured variables.**
- Scaled absolute error (MASE, primary), MAPE, relative gain against persistence.
- For 80 % intervals: coverage (PICP), mean relative width, Winkler interval score, pinball loss at 0.1 / 0.9, and an approximate CRPS (mean pinball over quantiles 0.1–0.9).

**Indices.**
- Regime at origin from r(t) = ln P(t) − ln P(t−12): rise > ln 1.10, fall < ln 0.90, calm otherwise; sensitivity at 5 % and 15 %.
- Reversal subsets use the realized change and serve diagnosis only.

**Publication-date rule.** A forecast at origin t uses only information published by the end of month t. Rainfall of month m is usable from t = m + 1 (sensitivity m + 2). Climatologies use past years only.

## Analysis plan

**Models.** Naive, SeasonalNaive, Ridge and LightGBM with the frozen v1.0-baseline hyperparameters (seed 42); ETS and ARIMA (AICc over a small fixed grid; dropped if a 20-series pilot projects more than 3 hours); LightGBM + factors; ARIMAX with regressors frozen at their origin value; ablation without each factor group.

**Statistical tests.**
- Scaled losses are averaged per origin month.
- Diebold-Mariano tests on loss differentials with HAC variance (h − 1 lags) and the Harvey-Leybourne-Newbold correction.
- Moving-block bootstrap (6-month blocks, 2 000 resamples, seed 42) for 95 % intervals.
- Holm correction within each hypothesis family (3 horizons).

**Inference criteria.**
- H1 / H1b / H4: at least 2 of 3 horizons significant after Holm, plus the descriptive conditions in the protocol (§10).
- H2: both bootstrap intervals exclude 0.
- H3: closer to 80 % and width ≤ 1.25×.
- H4 final confirmation additionally requires W4 to point in the same direction.

**Data exclusion.** Origins whose regime is undefined (month t−12 unobserved) are excluded and counted. Markets without coordinates have missing rainfall features. No outlier removal beyond the existing ETL quality rules.

**Missing data.** Missing months remain missing (no interpolation). LightGBM handles them natively; ARIMA uses the Kalman filter; ETS is fitted on the latest gap-free segment (at least 24 months).

**Exploratory analysis.** Lagged correlations and event studies of the factors around the 2022 and 2025-26 reversals (`02-analyse-facteurs.md`) are exploratory and are reported as such.

## Other

**Deviations.** Any change after this registration is logged in §12 of the protocol with its date, reason and whether results had been seen.

**Use of AI tools.** The study is conducted by the author with Claude Code (Anthropic) assisting in drafting this protocol, writing code and proposing extractions of harvest figures and events. The author takes every methodological decision, validates every row of the factor tables and writes the introduction and discussion of the report. Literature references proposed by the assistant are checked by the author.
