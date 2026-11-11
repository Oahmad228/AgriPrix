# Surface brief: AgriPrix dashboard (src/dashboard/)

Scope: the public Streamlit dashboard. Visitor mode: **Operate** (a coordinator checks the price situation; an evaluator checks the method).

Audience and job: NGO coordinators and cooperative managers want to know, for a country and a staple, where prices are abnormal now and what to expect in 1, 3 and 6 months; recruiters and analysts want to verify the quality of those numbers (PRODUCT.md). Constraints: Streamlit stack, data only from the FastAPI service, plain French, local currency, WFP/FAO attribution, known limits shown next to the numbers.

Decisions taken with Ahmad on 2026-11-11: first screen = current situation and alerts, a separate "Méthode & qualité" tab for evaluators; Streamlit kept; plain French; direction "Calendrier des saisons"; Public Sans self-hosted.

## Direction contract

THESIS: Prices in the Sahel are read against the farming calendar. Every time view carries the lean season (June–September) as a band, and every alert says whether it falls inside it; the screen refuses the category default of seasonless line charts under a row of KPI tiles.

OWN-WORLD: White working surface, ink #1E2B24; shell rail in rainy-season green #24453A with white text; lean-season band in millet straw #E9C46A at low opacity; observed prices as a solid ink line, forecasts as dashed blue #2A6F97 with a pale band for the 80 % interval; upward alerts red #B3261E with ▲, downward alerts slate #4A5568 with ▼. Public Sans throughout, tabular numerals in tables.

STORY: The visitor picks a country and a staple, sees this month's alerts in plain French (market, deviation from the expected level, inside or outside the lean season), opens a market to see its price history across seasons with the forecast fan, then can check in "Méthode & qualité" how good the forecasts and alerts really are.

FIRST VIEWPORT: Left: green filter rail (country, staple, market, data date, sources). Main, top: "Alertes du dernier mois disponible" for the selection, one line per market with deviation and season tag. Main, below: the selected market's price chart over the last five years with straw lean-season bands, alert markers, and the 1/3/6-month forecast with its interval, followed by a small forecast table.

FORM: Standard Streamlit shell (sidebar filters, tabs, dataframes) carrying the season band as signature move; first of three derived directions. seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
