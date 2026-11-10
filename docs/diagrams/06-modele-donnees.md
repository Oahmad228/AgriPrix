# Diagramme 06 — Modèle de données : MCD, MLD et Modèle Physique en Étoile (*Star Schema*)

> **Termes techniques introduits dans ce document (en une phrase simple)** :
> - **MCD / MLD / MPD (Méthode Merise)** : Les trois niveaux successifs de conception d'une base de données : Conceptuel (entités métier), Logique (tables relationnelles et clés) et Physique (types SQL exacts, contraintes et index sous PostgreSQL).
> - **Clé étrangère composite (*Composite Foreign Key*)** : Une contrainte relationnelle portant sur deux colonnes simultanément (ex. `(series_id, frequency)` ou `(market_code, country_iso3)`) qui garantit mathématiquement qu'une table enfant ne peut jamais associer un marché au mauvais pays ni une série mensuelle à une période annuelle.
> - **Table d'exécution (*Run Table* : `training_run`, `etl_run_audit`)** : Une table de métadonnées qui enregistre chaque exécution du pipeline avec son horodatage, son empreinte Git (`git_sha`) et la date maximale des données, permettant de versionner et d'isoler proprement les prévisions, anomalies et quantiles conformes.

---

> **Mise à jour Sprint 1 (2026-11-10)** : implémenté dans [`src/etl/sql/V001__warehouse_schema.sql`](../../src/etl/sql/V001__warehouse_schema.sql). Deux écarts assumés :
> 1. `official_faostat` est remplacé par les drapeaux qualité réels de FAOSTAT (`fao_official`, `fao_external`, `fao_break` = observés ; `fao_estimated`, `fao_imputed` = non observés), voir [`ADR-009`](../adr/009-drapeaux-qualite-sources-et-tracabilite-des-versions.md).
> 2. Ajout de la table `etl_source_file` (MD5, taille et date de chaque fichier source par exécution), et de `etl_run_id` sur `fact_price_observation`.
> Les tables ML (`training_run`, `fact_forecast`, …) et `dim_exchange_rate` seront créées par des migrations ultérieures (Sprints 2, 3 et 5).

## 1. Du MCD au MLD : Justification des choix de modélisation

En combinant la rigueur de **Merise** (intégrité référentielle stricte) et la modélisation décisionnelle de **Kimball (*Star Schema*)**, notre schéma résout 6 défis d'ingénierie des données :

1. **Garantie d'intégrité de grain temporel (`MONTHLY` vs `ANNUAL`) par clés étrangères composites** :
   - La table `fact_price_observation` **ne duplique pas** `reference_year` ni `reference_month` (qui appartiennent exclusivement à `dim_calendar`).
   - En revanche, elle porte `frequency` (`'MONTHLY'` | `'ANNUAL'`) et deux **clés étrangères composites** :
     - `(series_id, frequency) REFERENCES dim_series_catalog (series_id, frequency)`
     - `(calendar_id, frequency) REFERENCES dim_calendar (calendar_id, frequency)`
   - **Conséquence** : Le moteur PostgreSQL interdit physiquement de relier une série `MONTHLY` à un `calendar_id` `ANNUAL` (`YYYY00`) ou une série `ANNUAL` à un `calendar_id` `MONTHLY` (`YYYYMM`).
2. **Suppression de la redondance géographique (FK composite Marché / Pays)** :
   - `dim_market` expose une contrainte `UNIQUE (market_code, country_iso3)`.
   - `dim_series_catalog` référence `dim_market` via la **clé étrangère composite `(market_code, country_iso3)`**, rendant impossible toute incohérence où un marché du Mali serait rattaché au code pays du Sénégal.
   - La période de soudure (`lean_season_months`, ex. `'06,07,08,09'` au Sahel, `NULL` au Maroc) est rattachée à `dim_country` et retirée de `dim_calendar` (car la saisonnalité agricole dépend de la zone climatique du pays et non du calendrier universel).
3. **Remplacement de `price_flag` par `source_flag` + `is_observed`** :
   - `source_flag` conserve l'étiquette exacte du fournisseur (`'actual'`, `'aggregate'`, `'official_faostat'`).
   - `is_observed BOOLEAN NOT NULL` vaut `TRUE` uniquement pour les observations réelles/officielles (`source_flag IN ('actual', 'official_faostat')`) et `FALSE` pour les agrégats modélisés (`'aggregate'`). Ainsi, une seule clause `WHERE is_observed = TRUE` sélectionne proprement les relevés `actual` WFP **et** l'IPC officiel du Maroc.
4. **Référentiel de conversion d'unités (`ref_unit_conversion`) et règle de collision** :
   - Seules les **unités métriques standards** (`'KG'`, `'100 KG'`, `'500 G'`, `'70 G'`, `'TONNE'`, `'L'`) ont `is_metric_convertible = TRUE` et sont converties vers `'KG'` ou `'L'`.
   - Les **unités locales ou non-pondérales** (`'Pile'`, `'Head'`, `'Day'`, `'Unit'`) ont `is_metric_convertible = FALSE` et conservent `canonical_unit = raw_unit` sans conversion arbitraire.
   - **Règle déterministe en cas de collision après normalisation** : si deux lignes d'un même `(country, market, commodity, pricetype, canonical_unit, currency, calendar_id, source_flag)` proviennent d'unités brutes différentes (ex. `'KG'` et `'100 KG'`), l'ETL conserve en priorité l'observation déjà exprimée dans l'unité canonique native (`raw_unit = canonical_unit`), et verse la seconde dans `audit_rejected_rows` (`reason_code = 'UNIT_NORMALIZATION_COLLISION'`). *(Sur les 324 040 lignes WFP auditées, le nombre de collisions observées est de 0).*
5. **Versionnement MLOps via `training_run` et `fact_conformal_quantiles`** :
   - Chaque campagne d'entraînement crée un enregistrement dans `training_run (run_id, run_timestamp, max_data_date, git_sha, mlflow_parent_run_id)`.
   - Toutes les tables analytiques (`fact_forecast`, `fact_anomaly`, `fact_model_metrics_by_series`, `fact_conformal_quantiles`) possèdent une clé étrangère `run_id` et une contrainte `UNIQUE` composite explicite.
6. **Traçabilité ETL complète (`etl_run_audit` et `audit_rejected_rows`)** :
   - Chaque exécution de `make etl` est tracée dans `etl_run_audit`, et chaque ligne écartée est isolée dans `audit_rejected_rows` avec son motif et son payload brut.

---

## 2. Diagramme Entité-Relation Complet (MCD / MLD / MPD sous PostgreSQL 16)

```mermaid
erDiagram
    DIM_COUNTRY ||--o{ DIM_MARKET : "contient (1,N)"
    DIM_COUNTRY ||--o{ DIM_EXCHANGE_RATE : "possede_taux (0,N)"
    DIM_MARKET ||--o{ DIM_SERIES_CATALOG : "FK composite (market_code, country_iso3)"
    DIM_COMMODITY ||--o{ DIM_SERIES_CATALOG : "qualifie (1,N)"
    REF_UNIT_CONVERSION ||--o{ DIM_SERIES_CATALOG : "unit_measure = canonical_unit"

    DIM_SERIES_CATALOG ||--|{ FACT_PRICE_OBSERVATION : "FK composite (series_id, frequency)"
    DIM_CALENDAR ||--o{ FACT_PRICE_OBSERVATION : "FK composite (calendar_id, frequency)"
    REF_UNIT_CONVERSION ||--o{ FACT_PRICE_OBSERVATION : "raw_unit"

    TRAINING_RUN ||--o{ FACT_FORECAST : "versionne (1,N)"
    TRAINING_RUN ||--o{ FACT_ANOMALY : "versionne (1,N)"
    TRAINING_RUN ||--o{ FACT_MODEL_METRICS_BY_SERIES : "versionne (1,N)"
    TRAINING_RUN ||--o{ FACT_CONFORMAL_QUANTILES : "calibre (1,N)"

    DIM_SERIES_CATALOG ||--o{ FACT_FORECAST : "prevoit (0,N)"
    DIM_CALENDAR ||--o{ FACT_FORECAST : "origin & target_calendar_id"

    DIM_SERIES_CATALOG ||--o{ FACT_ANOMALY : "alerte (0,N)"
    DIM_CALENDAR ||--o{ FACT_ANOMALY : "date_choc (1,N)"

    DIM_SERIES_CATALOG ||--o{ FACT_MODEL_METRICS_BY_SERIES : "evalue (0,N)"

    ETL_RUN_AUDIT ||--o{ AUDIT_REJECTED_ROWS : "isole_rejets (0,N)"

    DIM_COUNTRY {
        varchar(3) country_iso3 PK "SEN, MLI, BFA, NER, CIV, MAR"
        varchar(100) country_name_fr "Nom francais"
        varchar(10) default_currency "XOF ou MAD"
        varchar(30) primary_source "WFP_HDX ou FAOSTAT"
        varchar(20) lean_season_months "Ex: '06,07,08,09' (Sahel) ou NULL"
        date max_observed_date "Derniere date collectee dans le pays"
    }

    DIM_MARKET {
        varchar(64) market_code PK "Ex: SEN_DAKAR_TILENE ou MAR_NATIONAL"
        varchar(3) country_iso3 FK "UK composite (market_code, country_iso3)"
        varchar(120) market_name "Nom du marche ou National Aggregate"
        varchar(100) admin1_region "Region administrative"
        varchar(100) admin2_district "Departement / Cercle"
        numeric(9,6) latitude "Latitude WGS84 (NULL si NATIONAL)"
        numeric(9,6) longitude "Longitude WGS84 (NULL si NATIONAL)"
        varchar(15) granularity_level "CHECK IN ('MARKET', 'NATIONAL')"
    }

    DIM_COMMODITY {
        varchar(64) commodity_code PK "Ex: WFP_RICE_IMP, FAO_23013"
        varchar(150) commodity_name_en "Libelle anglais"
        varchar(150) commodity_name_fr "Libelle francais"
        varchar(50) commodity_group "Rice, Millet, Sorghum, Maize, Beans, CPI_Food, Other"
        varchar(50) category "Categorie source"
        boolean is_food_security_basket "TRUE pour les 5 groupes UEMOA + IPC 23013"
    }

    REF_UNIT_CONVERSION {
        varchar(30) raw_unit PK "Ex: KG, 100 KG, 500 G, 70 G, L, Pile, Head, Day"
        varchar(30) canonical_unit "KG, L, INDEX_2015_100, ou raw_unit si non-metrique"
        numeric(14,6) multiplier_to_canonical "Ex: 0.01 pour 100 KG->KG, 2.0 pour 500 G->KG, 1.0 sinon"
        boolean is_metric_convertible "TRUE si metrique standard, FALSE si unite locale (Pile, Head...)"
    }

    DIM_CALENDAR {
        integer calendar_id PK "YYYYMM (mensuel ex: 202608) ou YYYY00 (annuel ex: 202400)"
        varchar(10) frequency "UK composite (calendar_id, frequency) - MONTHLY ou ANNUAL"
        smallint reference_year "Annee (1990..2035)"
        smallint reference_month "Mois 1..12 (NULL obligatoire si ANNUAL)"
        date period_start_date "YYYY-MM-01 ou YYYY-01-01"
        date wfp_reference_date "YYYY-MM-15 (NULL obligatoire si ANNUAL)"
        smallint quarter_num "Trimestre 1..4 (NULL si ANNUAL)"
    }

    DIM_EXCHANGE_RATE {
        serial exchange_rate_id PK
        varchar(3) country_iso3 FK "Reference DIM_COUNTRY"
        varchar(10) from_currency "XOF ou MAD"
        varchar(10) to_currency "EUR ou USD"
        integer calendar_id FK "Reference DIM_CALENDAR"
        numeric(14,6) rate_value "Ex: 655.957000 pour XOF/EUR"
    }

    DIM_SERIES_CATALOG {
        serial series_id PK "UK composite (series_id, frequency)"
        varchar(255) series_natural_key UK "Cle canonique unique a 8 composantes"
        varchar(64) market_code FK "FK composite (market_code, country_iso3) -> DIM_MARKET"
        varchar(3) country_iso3 FK "Partie de la FK composite vers DIM_MARKET"
        varchar(64) commodity_code FK "Reference DIM_COMMODITY"
        varchar(20) price_type "Retail, Wholesale, Producer, CPI"
        varchar(30) unit_measure FK "Unite canonique (KG, L, Pile, INDEX_2015_100...)"
        varchar(10) currency_code "XOF, MAD, USD, NONE (si INDEX)"
        varchar(10) frequency "CHECK IN ('MONTHLY', 'ANNUAL')"
        varchar(20) value_type "CHECK IN ('PRICE', 'INDEX', 'INFLATION_RATE')"
        varchar(15) granularity_level "CHECK IN ('MARKET', 'NATIONAL')"
        integer total_observed_count "Nb observations avec is_observed = TRUE"
        integer recent_continuous_months "Longueur segment continu recent (sans imputer)"
        integer max_consecutive_missing "Nb max mois manquants consecutifs dans le segment"
        date first_obs_date "Premiere date observee"
        date last_obs_date "Derniere date observee"
        boolean is_ml_eligible "TRUE pour les 738 series eligibles"
        varchar(120) ineligibility_reason "Motif explicite si is_ml_eligible = FALSE"
    }

    FACT_PRICE_OBSERVATION {
        bigserial observation_id PK "UK: UNIQUE (series_id, calendar_id, source_flag)"
        integer series_id FK "FK1 composite (series_id, frequency) -> DIM_SERIES_CATALOG"
        integer calendar_id FK "FK2 composite (calendar_id, frequency) -> DIM_CALENDAR"
        varchar(10) frequency "MONTHLY ou ANNUAL (verrouille par FK1 et FK2)"
        numeric(14,4) observed_value "Valeur en unite canonique (> 0)"
        numeric(14,4) raw_value "Valeur brute d'origine"
        varchar(30) raw_unit FK "Reference REF_UNIT_CONVERSION"
        varchar(20) source_flag "CHECK IN ('actual', 'aggregate', 'official_faostat')"
        boolean is_observed "TRUE si actual/official_faostat, FALSE si aggregate"
        timestamp ingested_at "Horodatage ETL"
    }

    TRAINING_RUN {
        serial run_id PK "Identifiant unique de la campagne ML/Anomalies"
        timestamp run_timestamp "Date d'execution de make train"
        date max_data_date "Date maximale des donnees utilisees"
        varchar(40) git_sha "Commit Git exact du code"
        varchar(64) mlflow_parent_run_id "Run parent MLflow de la campagne"
        boolean is_production_active "TRUE pour le dernier run valide servi par l'API"
    }

    FACT_CONFORMAL_QUANTILES {
        serial quantile_id PK "UK: (run_id, country_iso3, commodity_group, model_name, horizon_months, eval_window)"
        integer run_id FK "Reference TRAINING_RUN"
        varchar(3) country_iso3 FK "Pays du groupe"
        varchar(50) commodity_group "Groupe produit (Rice, Millet, CPI_Food...)"
        varchar(50) model_name "LightGBM_Global, Ridge_Seasonal, SeasonalNaive"
        smallint horizon_months "CHECK IN (1, 3, 6)"
        varchar(30) eval_window "VAL_W1_2022, VAL_W2_24_25, TEST_W3_25_26, PROD_FINAL"
        integer n_calibration_residuals "Taille de l'echantillon de calibration"
        numeric(10,6) q_rel_10 "Quantile 10% des erreurs relatives (y - yhat)/yhat"
        numeric(10,6) q_rel_90 "Quantile 90% des erreurs relatives (y - yhat)/yhat"
    }

    FACT_FORECAST {
        bigserial forecast_id PK "UK: UNIQUE (run_id, series_id, origin_calendar_id, horizon_months)"
        integer run_id FK "Reference TRAINING_RUN"
        integer series_id FK "Reference DIM_SERIES_CATALOG (is_ml_eligible=TRUE)"
        integer origin_calendar_id FK "Mois d'emission de la prevision"
        integer target_calendar_id FK "Mois cible predit (t+1, t+3, t+6)"
        smallint horizon_months "CHECK IN (1, 3, 6)"
        numeric(14,4) yhat_point "Prevision ponctuelle"
        numeric(14,4) yhat_lower_80 "Borne basse conforme 80%"
        numeric(14,4) yhat_upper_80 "Borne haute conforme 80%"
        varchar(50) champion_model_name "Modele retenu sur Fenetres 1-2"
        varchar(64) mlflow_group_run_id "Run MLflow du groupe (Pays, Produit, Modele)"
    }

    FACT_ANOMALY {
        bigserial anomaly_id PK "UK: UNIQUE (run_id, series_id, calendar_id)"
        integer run_id FK "Reference TRAINING_RUN"
        integer series_id FK "Reference DIM_SERIES_CATALOG"
        integer calendar_id FK "Reference DIM_CALENDAR"
        numeric(14,4) observed_value "Valeur observee P_t"
        numeric(14,4) expected_value "Valeur attendue unique exp(T_tilde_t + S_tilde_m)"
        numeric(10,4) log_residual "Residu r_t = ln(P_t) - ln(expected_value)"
        numeric(8,3) z_score_robust "r_t / (1.4826 * MAD_m)"
        numeric(8,2) yoy_change_pct "Variation annuelle (%)"
        varchar(15) severity "CHECK IN ('WARNING', 'CRITICAL')"
    }

    FACT_MODEL_METRICS_BY_SERIES {
        bigserial metric_id PK "UK: UNIQUE (run_id, series_id, model_name, horizon_months, eval_window)"
        integer run_id FK "Reference TRAINING_RUN"
        integer series_id FK "Reference DIM_SERIES_CATALOG"
        varchar(50) model_name "LightGBM_Global, Ridge_Seasonal, SeasonalNaive"
        smallint horizon_months "CHECK IN (1, 3, 6)"
        varchar(30) eval_window "VAL_W1_2022, VAL_W2_24_25, TEST_W3_25_26"
        numeric(10,4) mase "Vrai MASE (denominateur in-sample naif t-12)"
        numeric(10,4) rel_mae "Ratio MAE_modele / MAE_naive sur la fenetre"
        numeric(10,4) mape "Mean Absolute Percentage Error (%)"
        numeric(14,4) rmse "Root Mean Squared Error"
        numeric(6,4) picp_80 "Couverture empirique intervalle 80%"
        varchar(64) mlflow_group_run_id "Run MLflow du groupe"
    }

    ETL_RUN_AUDIT {
        serial etl_run_id PK
        timestamp started_at "Debut execution make etl"
        timestamp finished_at "Fin execution"
        varchar(20) status "SUCCESS ou FAILED"
        integer rows_read "Total lignes lues"
        integer rows_upserted "Total lignes inserees/mises a jour"
        integer rows_rejected "Total lignes en quarantaine"
        varchar(40) git_sha "Commit Git"
    }

    AUDIT_REJECTED_ROWS {
        bigserial rejected_id PK
        integer etl_run_id FK "Reference ETL_RUN_AUDIT"
        varchar(30) source_file "Nom du fichier CSV/ZIP"
        integer line_number "Numero de ligne source"
        varchar(50) reason_code "NEGATIVE_PRICE, INVALID_GPS, UNIT_NORMALIZATION_COLLISION..."
        text raw_payload_json "Ligne brute serialisee en JSON"
        timestamp rejected_at "Horodatage du rejet"
    }
```

---

## 3. Contraintes physiques SQL clés (MPD PostgreSQL 16 — Base `agriprix_dw`)

```sql
-- 1. Cles uniques composites sur les dimensions pour permettre les FK composites
ALTER TABLE dim_market ADD CONSTRAINT uq_market_country UNIQUE (market_code, country_iso3);
ALTER TABLE dim_calendar ADD CONSTRAINT uq_calendar_freq UNIQUE (calendar_id, frequency);
ALTER TABLE dim_series_catalog ADD CONSTRAINT uq_series_freq UNIQUE (series_id, frequency);

-- 2. FK composite Marche/Pays sur dim_series_catalog (elimine toute redondance/incoherence pays)
ALTER TABLE dim_series_catalog
ADD CONSTRAINT fk_series_market_country
FOREIGN KEY (market_code, country_iso3) REFERENCES dim_market (market_code, country_iso3);

-- 3. Contrainte interdisant d'inventer des mois pour les series annuelles dans dim_calendar
ALTER TABLE dim_calendar
ADD CONSTRAINT chk_calendar_frequency_month CHECK (
    (frequency = 'ANNUAL'  AND reference_month IS NULL AND wfp_reference_date IS NULL AND calendar_id = reference_year * 100)
    OR
    (frequency = 'MONTHLY' AND reference_month BETWEEN 1 AND 12 AND calendar_id = reference_year * 100 + reference_month)
);

-- 4. FK composites et Unicite sur fact_price_observation (sans reference_year/month redondants)
ALTER TABLE fact_price_observation
ADD CONSTRAINT fk_obs_series_freq FOREIGN KEY (series_id, frequency) REFERENCES dim_series_catalog (series_id, frequency),
ADD CONSTRAINT fk_obs_calendar_freq FOREIGN KEY (calendar_id, frequency) REFERENCES dim_calendar (calendar_id, frequency),
ADD CONSTRAINT chk_obs_source_flag CHECK (
    (source_flag IN ('actual', 'official_faostat') AND is_observed = TRUE)
    OR
    (source_flag = 'aggregate' AND is_observed = FALSE)
),
ADD CONSTRAINT uq_observation_series_calendar_flag UNIQUE (series_id, calendar_id, source_flag);

-- 5. Cles d'unicite sur les tables de faits analytiques rattachees a training_run
ALTER TABLE fact_forecast
ADD CONSTRAINT uq_forecast_run_series_origin_h UNIQUE (run_id, series_id, origin_calendar_id, horizon_months);

ALTER TABLE fact_anomaly
ADD CONSTRAINT uq_anomaly_run_series_cal UNIQUE (run_id, series_id, calendar_id);

ALTER TABLE fact_model_metrics_by_series
ADD CONSTRAINT uq_metrics_run_series_model_h_win UNIQUE (run_id, series_id, model_name, horizon_months, eval_window);

ALTER TABLE fact_conformal_quantiles
ADD CONSTRAINT uq_quantiles_run_group_model_h_win UNIQUE (run_id, country_iso3, commodity_group, model_name, horizon_months, eval_window);
```

---

## 4. Comment lire ce diagramme ?

1. **Suivez les clés composites (`FK composite`)** :
   - Entre `DIM_MARKET` et `DIM_SERIES_CATALOG`, la double clé `(market_code, country_iso3)` garantit qu'une série ne peut jamais associer un marché d'un pays A avec le code ISO d'un pays B.
   - Entre `FACT_PRICE_OBSERVATION`, `DIM_SERIES_CATALOG` et `DIM_CALENDAR`, la colonne `frequency` fait partie des deux clés étrangères composites `(series_id, frequency)` et `(calendar_id, frequency)` : il est ainsi impossible d'insérer une date mensuelle sur une série annuelle (et inversement).
2. **Suivez la table `TRAINING_RUN`** : chaque exécution de `make train` possède son `run_id` lié au `git_sha` et à `max_data_date`. Les 4 tables analytiques (`FACT_FORECAST`, `FACT_ANOMALY`, `FACT_MODEL_METRICS_BY_SERIES`, `FACT_CONFORMAL_QUANTILES`) incluent `run_id` dans leur contrainte d'unicité `UNIQUE`, permettant à l'API de servir la version active (`is_production_active = TRUE`) tout en conservant l'historique d'audit des campagnes précédentes.

---

## 5. Deux questions qu'un recruteur pourrait poser sur ce modèle de données

### Question 1 : *« Pourquoi avez-vous retiré `reference_year` et `reference_month` de `fact_price_observation` tout en y ajoutant `frequency` dans deux clés étrangères composites ? »*
> **Réponse conseillée** :
> « Stocker `reference_year` et `reference_month` à la fois dans `dim_calendar` et dans `fact_price_observation` violait la 3e Forme Normale (3NF) : une erreur de chargement aurait pu associer `calendar_id = 202608` avec `reference_month = 9` ! En supprimant ces deux colonnes de la table de faits, `calendar_id` devient l'unique source de vérité temporelle, et la contrainte d'unicité `UNIQUE (series_id, calendar_id, source_flag)` porte uniquement sur des colonnes `NOT NULL`. En revanche, ajouter `frequency` dans deux clés étrangères composites `(series_id, frequency) -> dim_series_catalog` et `(calendar_id, frequency) -> dim_calendar` permet à PostgreSQL de vérifier nativement que la fréquence de la série et la fréquence de la période calendaire sont toujours identiques (`MONTHLY = MONTHLY` ou `ANNUAL = ANNUAL`). »

### Question 2 : *« Comment gérez-vous dans votre schéma les unités locales comme le 'Pile' (tas) ou le 'Head' (tête de bétail) par rapport aux sacs de '100 KG' ? »*
> **Réponse conseillée** :
> « Nous utilisons une table de référence `ref_unit_conversion` dotée du booléen `is_metric_convertible`. Seules les unités métriques standards (`KG`, `100 KG`, `500 G`, `70 G`, `TONNE`, `L`) ont `is_metric_convertible = TRUE` et sont converties en `KG` ou `L` avec un facteur mathématique exact (`0.01` pour `100 KG`, `2.0` pour `500 G`), tout en conservant `raw_value` et `raw_unit` sur chaque observation. À l'inverse, les unités locales ou non pondérales (`Pile`, `Head`, `Day`, `Unit`) ont `is_metric_convertible = FALSE` et gardent leur unité propre (`canonical_unit = raw_unit`) afin de ne jamais inventer de poids fictif en kilogrammes. Enfin, en cas de collision après normalisation vers une même unité canonique, notre règle déterministe donne la priorité au relevé déjà exprimé dans l'unité canonique native (`raw_unit == canonical_unit`) et trace le doublon écarté dans `audit_rejected_rows`. »
