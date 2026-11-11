# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Streamlit dashboard (Python), confirmed by Ahmad on 2026-11-11 (ADR-005). It reads data only through the AgriPrix FastAPI service (no SQL access). Visual control is limited to the Streamlit theme, self-hosted fonts, light CSS and Plotly charts.

## Users

- **NGO / food-security coordinators** (persona Fatou, docs/00-cadrage.md): want to see which markets and staples are under abnormal price pressure now, and what prices to expect in 1, 3 and 6 months, to plan aid and budgets.
- **Cooperative managers and traders** (persona Moussa): follow the price of a staple on their market against what is normal for the season.
- **Market analysts / economists** (persona Youssef): check how reliable the forecasts and alerts are before using them.
- **Recruiters and interviewers** evaluating Ahmad's data-science work: need to see real data, honest validation and engineering rigour within a minute.

Primary order on the public demo (Ahmad, 2026-11-11): the current price situation and alerts first, as a real user would come for; a dedicated "Méthode & qualité" area shows the rigour to a recruiter.

## Product Purpose

Monitor staple food prices in West Africa (Senegal, Mali, Burkina Faso, Niger, Côte d'Ivoire; WFP data) and Morocco (FAOSTAT food CPI), flag abnormal price moves against trend and season, and forecast prices 1, 3 and 6 months ahead with 80 % intervals. Success: a coordinator understands in seconds where prices are abnormal and what to expect, and an evaluator can verify how good the numbers are.

## Positioning

Market-level alerts that account for each market's own trend and lean-season pattern, explained in plain French, together with forecasts whose quality is published honestly, including where they do not beat the simple "last known price" benchmark (docs/results/forecast-report.md).

## Operating Context

- Data refreshed monthly from HDX (WFP) and FAOSTAT; prices are monthly, so the dashboard is consulted periodically, not watched live.
- Values stay in local currency (XOF per kg, MAD index); nothing is converted.
- The Sahel lean season (June–September) drives seasonal price peaks (docs/eda/EDA.md: peak in August in the 4 Sahel countries).

## Capabilities and Constraints

- API routes available: countries, commodities, markets, series, series history, forecasts (champion model, 80 % interval, test coverage), anomalies (French explanation), model metrics vs persistence, active run.
- 782 series eligible for forecasts (data of 2026-11-10); Côte d'Ivoire has no forecast (aggregated WFP values 2020–2026); Morocco is a national index, not market prices.
- Known limits that must be shown, not hidden: on the final test window the forecasts do not beat persistence, and the 6-month interval under-covers (52 %); the COVID-2020 shock is detected only at the threshold.

## Brand Commitments

- Interface language: plain French; technical terms explained in one sentence (Ahmad, 2026-11-11).
- Attribution required: "Source : World Food Programme (WFP) via HDX, CC BY-IGO 3.0" and "Source : FAOSTAT, FAO, CC BY 4.0"; no suggestion that WFP or FAO endorse the forecasts.
- No logo or visual identity exists yet.

## Evidence on Hand

Real data from the warehouse (343 079 observations), generated reports in docs/results/ and docs/eda/. No testimonials, users, partners or adoption figures exist: none may be invented.

## Product Principles

1. Truth before polish: every number on screen comes from the API, with its date and source.
2. Say what is uncertain: intervals, coverage and known failures are displayed next to the forecast.
3. Explain in plain French what an alert means and why it fired.
4. A coordinator's question ("is the price abnormal here, now?") is answerable without reading the method.

## Accessibility & Inclusion

Users may read on modest laptops or phones with variable connectivity: legible type, contrast AA (4.5:1), information never carried by colour alone, light pages.
