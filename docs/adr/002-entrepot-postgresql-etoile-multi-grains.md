# ADR-002 : Entrepôt PostgreSQL en schéma en étoile multi-grains, clés étrangères composites et cloisonnement des bases (`agriprix_dw` vs `mlflow_db`)

- **Statut** : Accepté (Révisé en fin de Phase 2)
- **Date** : 2026-04-19
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `EF-02`, `EF-05`, `EF-06`, `ENF-02`, `ENF-04`, `ENF-07`

---

## 1. Contexte et Problème

Nos deux sources officielles présentent des grains temporels, spatiaux et d'unités hétérogènes :
1. **WFP / HDX (5 pays UEMOA : `SEN`, `MLI`, `BFA`, `NER`, `CIV`)** : **324 040 observations** à l'échelle **infra-nationale (`MARKET`)**, à fréquence **mensuelle (`MONTHLY`)**, exprimées dans 9 unités brutes (dont 5 unités métriques `KG`, `100 KG`, `500 G`, `70 G`, `L` et 4 unités locales/non-pondérales `Pile`, `Head`, `Day`, `Unit`), avec `source_flag` valant `'actual'` (`98,75 %`) ou `'aggregate'` (`1,25 %`).
2. **FAOSTAT (Maroc : `MAR`)** :
   - **Domaine `CP`** : **942 observations** nationales (`NATIONAL`), mensuelles (`MONTHLY`), dont l'IPC alimentaire (`Item 23013`, `value_type = 'INDEX'`, base `2015 = 100`, `source_flag = 'official_faostat'`).
   - **Domaine `PP`** : **8 942 observations** nationales (`NATIONAL`), **annuelles (`ANNUAL`)**, en `MAD/tonne`, `USD/tonne` ou indice.

**Problèmes d'intégrité à verrouiller au niveau SQL** :
1. Comment empêcher physiquement qu'une observation associe une série `MONTHLY` à une période `ANNUAL` (et inversement) sans dupliquer `reference_year` et `reference_month` dans la table de faits ?
2. Comment éliminer toute redondance ou incohérence pays entre un marché et une série ?
3. Comment gérer proprement la normalisation des unités métriques sans inventer de poids pour les unités locales (`Pile`, `Head`), et départager d'éventuelles collisions ?
4. Comment versionner les prévisions, anomalies, quantiles conformes et métriques sans doublons, et isoler le serveur MLflow de l'entrepôt métier ?

---

## 2. Décision et Architecture du Schéma (`agriprix_dw` & `mlflow_db`)

Nous retenons un **schéma en étoile multi-grains sous `postgres:16-alpine`** ([`docs/diagrams/06-modele-donnees.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/06-modele-donnees.md)) structuré par les 7 règles d'ingénierie suivantes :

1. **Suppression de `reference_year/month` dans `fact_price_observation` et Clés Étrangères Composites de fréquence** :
   - `reference_year` et `reference_month` (`NULL` si `ANNUAL`) ne résident que dans `dim_calendar` (`calendar_id = YYYYMM` si mensuel, `YYYY00` si annuel).
   - `fact_price_observation` contient `(series_id, calendar_id, frequency, ...)` et deux **FK composites** :
     - `(series_id, frequency) REFERENCES dim_series_catalog (series_id, frequency)`
     - `(calendar_id, frequency) REFERENCES dim_calendar (calendar_id, frequency)`
   - L'unicité est garantie par **`UNIQUE (series_id, calendar_id, source_flag)`** sur des colonnes 100 % `NOT NULL`.
2. **Suppression de la redondance pays par FK composite Marché/Pays et retrait de `is_lean_season` du calendrier** :
   - `dim_series_catalog` référence `dim_market` via la **FK composite `(market_code, country_iso3) REFERENCES dim_market (market_code, country_iso3)`**.
   - Les mois de soudure (`lean_season_months`) sont portés par `dim_country` (car propres au Sahel) et retirés de `dim_calendar`.
3. **Remplacement de `price_flag` par `source_flag` + `is_observed`** :
   - `source_flag` stocke la provenance exacte (`'actual'`, `'official_faostat'`, `'aggregate'`).
   - `is_observed BOOLEAN NOT NULL` vaut `TRUE` pour `'actual'` et `'official_faostat'`, et `FALSE` pour `'aggregate'` (vérifié par contrainte `CHECK`), évitant d'exclure par erreur l'IPC Maroc lors du filtrage ML.
4. **Table `ref_unit_conversion` et Règle déterministe de collision** :
   - Seules les unités métriques (`KG`, `100 KG`, `500 G`, `70 G`, `TONNE`, `L`) ont `is_metric_convertible = TRUE` et sont converties en `KG` ou `L`. Les unités locales/non-pondérales (`Pile`, `Head`, `Day`, `Unit`) ont `is_metric_convertible = FALSE` et gardent `canonical_unit = raw_unit`.
   - En cas de collision après normalisation vers une même unité canonique sur un même `(series_id, calendar_id, source_flag)`, priorité est donnée au relevé déjà exprimé dans l'unité canonique native (`raw_unit == canonical_unit`), et la ligne écartée est journalisée dans `audit_rejected_rows`.
5. **Versionnement des sorties analytiques via `training_run` et `fact_conformal_quantiles`** :
   - La table `training_run (run_id, run_timestamp, max_data_date, git_sha, mlflow_parent_run_id, is_production_active)` versionne chaque exécution de `make train`.
   - `fact_forecast`, `fact_anomaly`, `fact_model_metrics_by_series` et la nouvelle table `fact_conformal_quantiles` possèdent toutes une FK `run_id` et une contrainte `UNIQUE` composite incluant `run_id`.
   - Les tables `etl_run_audit` et `audit_rejected_rows` tracent chaque exécution ETL et chaque ligne mise en quarantaine.
6. **Séparation stricte des bases et des rôles SQL au sein du conteneur `db`** :
   - **Base `agriprix_dw`** : accessible en écriture uniquement par `agriprix_etl_writer` (`job-runner`) et en lecture seule (`SELECT`) par `agriprix_api_readonly` (`api` FastAPI et `Metabase`).
   - **Base `mlflow_db`** : base dédiée au backend du serveur `mlflow` via le rôle exclusif `mlflow_user` (qui n'a aucun droit sur `agriprix_dw`).
   - Persistance sur **volumes nommés Docker** (`pgdata`, `mlflow_artifacts`) pour éviter la lenteur NTFS/WSL2 sous Windows.
