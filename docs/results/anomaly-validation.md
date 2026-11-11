# Validation du détecteur d'anomalies sur les crises historiques

> Rapport **généré** par `python -m src.anomaly.validation` (données ETL `etl_run_id = 7`). Catalogue, seuils et critère fixés *a priori* dans `src/anomaly/catalog.py` (commit `d7bfac9`, publié avant tout calcul sur données réelles). Un épisode manqué est un résultat, jamais un motif de retoucher les seuils.

Critère : un couple (pays, produit) est détecté si, pendant l'épisode, au moins **25% de ses marchés** ont un score robuste **z ≥ +2.5** le même mois. Un épisode est détecté si au moins un de ses couples l'est.

## 1. Résultat par épisode

| episode | title | couples_evaluated | couples_detected | part max. de marchés en alerte (%) | detected |
|---|---|---|---|---|---|
| SHOCK-01 | Crise alimentaire mondiale 2007-2008 | 3 | 2 | 95.0 | OUI |
| SHOCK-02 | Crise alimentaire et pastorale sahélienne de 2012 | 6 | 6 | 100.0 | OUI |
| SHOCK-03 | Choc COVID-19 et fermetures de frontières (2020) | 16 | 1 | 25.0 | OUI |
| SHOCK-04 | Choc inflationniste mondial et guerre en Ukraine (2022) | 13 | 13 | 100.0 | OUI |
| SHOCK-05 | Crise politique et sanctions CEDEAO au Niger (2023-2024) | 3 | 2 | 91.0 | OUI |

**Rappel : 5 / 5 épisodes = 100%** (intervalle de confiance exact à 95 % : 48% – 100%). Objectif KPI-M4 ≥ 80% : **atteint**.

Avec seulement 5 épisodes, l'intervalle de confiance est très large : ce rappel ne permet pas d'affirmer une performance générale, seulement l'absence d'échec grossier.

## 2. Taux d'alerte en période calme (2015–2018)

**4.56%** des 46 803 mois-séries notés sont en alerte (|z| ≥ 2.5), objectif ≤ 5% : **atteint**. Sous une loi normale, |z| ≥ 2,5 arriverait 1,24 % du temps ; l'écart mesure les queues épaisses des prix.

| country_iso3 | taux d'alerte (%) |
|---|---|
| BFA | 1.73 |
| CIV | 12.13 |
| MAR | 0.0 |
| MLI | 4.93 |
| NER | 5.09 |
| SEN | 6.78 |

## 3. Détail par couple (pays, produit)

| episode | country | group | markets_scored | max_share_alert | best_month | max_z | detected |
|---|---|---|---|---|---|---|---|
| SHOCK-01 | SEN | Rice | 43 | 95.0 | 2008-09 | 27.33 | oui |
| SHOCK-01 | NER | Millet | 32 | 7.0 | 2008-06 | 5.4 | non |
| SHOCK-01 | NER | Sorghum | 14 | 42.0 | 2008-05 | 17.34 | oui |
| SHOCK-02 | MLI | Millet | 25 | 95.0 | 2012-04 | 15.26 | oui |
| SHOCK-02 | MLI | Sorghum | 24 | 100.0 | 2012-05 | 20.52 | oui |
| SHOCK-02 | NER | Millet | 66 | 28.0 | 2012-05 | 8.3 | oui |
| SHOCK-02 | NER | Sorghum | 57 | 28.0 | 2012-05 | 5.54 | oui |
| SHOCK-02 | BFA | Millet | 13 | 58.0 | 2012-06 | 5.34 | oui |
| SHOCK-02 | BFA | Sorghum | 11 | 45.0 | 2012-04 | 5.04 | oui |
| SHOCK-03 | SEN | Rice | 54 | 20.0 | 2020-05 | 7.71 | non |
| SHOCK-03 | SEN | Millet | 36 | 25.0 | 2020-05 | 7.38 | oui |
| SHOCK-03 | SEN | Sorghum | 17 | 7.0 | 2020-06 | 6.93 | non |
| SHOCK-03 | SEN | Maize | 45 | 11.0 | 2020-05 | 7.15 | non |
| SHOCK-03 | MLI | Rice | 144 | 6.0 | 2020-04 | 11.16 | non |
| SHOCK-03 | MLI | Millet | 88 | 9.0 | 2020-08 | 5.3 | non |
| SHOCK-03 | MLI | Sorghum | 63 | 3.0 | 2020-07 | 3.06 | non |
| SHOCK-03 | MLI | Maize | 57 | 9.0 | 2020-04 | 12.21 | non |
| SHOCK-03 | BFA | Rice | 39 | 10.0 | 2020-06 | 11.28 | non |
| SHOCK-03 | BFA | Millet | 62 | 5.0 | 2020-08 | 5.55 | non |
| SHOCK-03 | BFA | Sorghum | 59 | 3.0 | 2020-08 | 3.3 | non |
| SHOCK-03 | BFA | Maize | 54 | 2.0 | 2020-06 | 2.67 | non |
| SHOCK-03 | NER | Rice | 55 | 22.0 | 2020-07 | 10.03 | non |
| SHOCK-03 | NER | Millet | 55 | 6.0 | 2020-07 | 3.74 | non |
| SHOCK-03 | NER | Sorghum | 52 | 12.0 | 2020-07 | 5.08 | non |
| SHOCK-03 | NER | Maize | 51 | 2.0 | 2020-08 | 3.0 | non |
| SHOCK-04 | BFA | Rice | 66 | 29.0 | 2022-04 | 27.98 | oui |
| SHOCK-04 | BFA | Millet | 62 | 63.0 | 2022-04 | 13.73 | oui |
| SHOCK-04 | BFA | Sorghum | 61 | 60.0 | 2022-05 | 17.88 | oui |
| SHOCK-04 | BFA | Maize | 54 | 40.0 | 2022-05 | 7.72 | oui |
| SHOCK-04 | MLI | Rice | 147 | 51.0 | 2022-11 | 25.54 | oui |
| SHOCK-04 | MLI | Millet | 83 | 83.0 | 2022-05 | 25.54 | oui |
| SHOCK-04 | MLI | Sorghum | 64 | 92.0 | 2022-07 | 37.22 | oui |
| SHOCK-04 | MLI | Maize | 56 | 62.0 | 2022-06 | 22.09 | oui |
| SHOCK-04 | SEN | Rice | 29 | 46.0 | 2022-10 | 12.33 | oui |
| SHOCK-04 | SEN | Millet | 13 | 83.0 | 2022-10 | 7.04 | oui |
| SHOCK-04 | SEN | Sorghum | 7 | 71.0 | 2022-06 | 13.27 | oui |
| SHOCK-04 | SEN | Maize | 15 | 92.0 | 2022-07 | 18.4 | oui |
| SHOCK-04 | MAR | CPI_Food | 1 | 100.0 | 2022-04 | 4.53 | oui |
| SHOCK-05 | NER | Rice | 55 | 91.0 | 2023-11 | 23.5 | oui |
| SHOCK-05 | NER | Maize | 47 | 43.0 | 2023-09 | 8.27 | oui |
| SHOCK-05 | NER | Millet | 53 | 4.0 | 2023-11 | 3.16 | non |
