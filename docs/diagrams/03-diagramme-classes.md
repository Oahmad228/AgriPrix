# Diagramme 03 — Diagramme de classes du domaine (*Domain Class Diagram*)

> **Termes techniques introduits dans ce document (en une phrase simple)** :
> - **Diagramme de classes du domaine (*Domain Class Diagram*)** : Un schéma UML qui représente les concepts métier du projet, leurs attributs typés, leurs opérations et leurs relations (`1` à `*`), aligné avec le modèle de données de l'entrepôt.
> - **Objet de valeur / Référentiel (`RefUnitConversion`)** : Une classe qui encapsule la règle de conversion d'une unité brute vers une unité canonique uniquement lorsque l'unité est métrique (`is_metric_convertible = True`).
> - **Entité de traçabilité d'exécution (`TrainingRun`, `EtlRunAudit`)** : Une classe qui scelle le contexte exact d'un traitement batch (date maximale des données, commit Git `git_sha`, identifiant MLflow) pour garantir la reproductibilité scientifique.

---

## 1. Diagramme Mermaid (Rendu natif GitHub)

```mermaid
classDiagram
    direction TB

    %% Énumérations du domaine
    class GranularityLevel {
        <<enumeration>>
        MARKET
        NATIONAL
    }

    class Frequency {
        <<enumeration>>
        MONTHLY
        ANNUAL
    }

    class ValueType {
        <<enumeration>>
        PRICE
        INDEX
        INFLATION_RATE
    }

    class SourceFlag {
        <<enumeration>>
        actual
        aggregate
        official_faostat
    }

    class AnomalySeverity {
        <<enumeration>>
        WARNING
        CRITICAL
    }

    %% Entités géographiques, produits et unités
    class Country {
        +String country_iso3
        +String country_name_fr
        +String default_currency
        +String primary_source
        +String lean_season_months_nullable
        +Date max_observed_date
        +is_uemoa() bool
    }

    class Market {
        +String market_code
        +String country_iso3
        +String market_name
        +String admin1_region
        +String admin2_district
        +Float latitude_nullable
        +Float longitude_nullable
        +GranularityLevel granularity_level
        +is_national_aggregate() bool
    }

    class Commodity {
        +String commodity_code
        +String commodity_name_en
        +String commodity_name_fr
        +String commodity_group
        +String category
        +Boolean is_food_security_basket
    }

    class RefUnitConversion {
        +String raw_unit
        +String canonical_unit
        +Decimal multiplier_to_canonical
        +Boolean is_metric_convertible
        +normalize(Decimal raw_val) Decimal
    }

    class CalendarPeriod {
        +Integer calendar_id
        +Frequency frequency
        +Integer reference_year
        +Integer reference_month_nullable
        +Date period_start_date
        +Date wfp_reference_date_nullable
        +Integer quarter_num_nullable
    }

    class ExchangeRate {
        +Integer exchange_rate_id
        +String country_iso3
        +String from_currency
        +String to_currency
        +Integer calendar_id
        +Decimal rate_value
        +convert(Decimal amount) Decimal
    }

    %% Entité centrale : Série Temporelle Canonique
    class TimeSeriesCatalog {
        +Integer series_id
        +String series_natural_key
        +String market_code
        +String country_iso3
        +String commodity_code
        +String price_type
        +String unit_measure
        +String currency_code
        +Frequency frequency
        +ValueType value_type
        +GranularityLevel granularity_level
        +Integer total_observed_count
        +Integer recent_continuous_months
        +Integer max_consecutive_missing
        +Date first_obs_date
        +Date last_obs_date
        +Boolean is_ml_eligible
        +String ineligibility_reason_nullable
        +evaluate_ml_eligibility(Date country_max_date) Boolean
    }

    %% Entités de faits et de traçabilité d'exécution
    class PriceObservation {
        +Long observation_id
        +Integer series_id
        +Integer calendar_id
        +Frequency frequency
        +Decimal observed_value
        +Decimal raw_value
        +String raw_unit
        +SourceFlag source_flag
        +Boolean is_observed
        +resolve_unit_collision(PriceObservation other) PriceObservation
    }

    class TrainingRun {
        +Integer run_id
        +DateTime run_timestamp
        +Date max_data_date
        +String git_sha
        +String mlflow_parent_run_id
        +Boolean is_production_active
    }

    class ConformalQuantiles {
        +Integer quantile_id
        +Integer run_id
        +String country_iso3
        +String commodity_group
        +String model_name
        +Integer horizon_months
        +String eval_window
        +Integer n_calibration_residuals
        +Decimal q_rel_10
        +Decimal q_rel_90
        +compute_interval(Decimal yhat) Tuple
    }

    class PriceForecast {
        +Long forecast_id
        +Integer run_id
        +Integer series_id
        +Integer origin_calendar_id
        +Integer target_calendar_id
        +Integer horizon_months
        +Decimal yhat_point
        +Decimal yhat_lower_80
        +Decimal yhat_upper_80
        +String champion_model_name
        +String mlflow_group_run_id
    }

    class PriceAnomaly {
        +Long anomaly_id
        +Integer run_id
        +Integer series_id
        +Integer calendar_id
        +Decimal observed_value
        +Decimal expected_value
        +Decimal log_residual
        +Decimal z_score_robust
        +Decimal yoy_change_pct
        +AnomalySeverity severity
    }

    class SeriesModelMetrics {
        +Long metric_id
        +Integer run_id
        +Integer series_id
        +String model_name
        +Integer horizon_months
        +String eval_window
        +Decimal mase
        +Decimal rel_mae
        +Decimal mape
        +Decimal rmse
        +Decimal picp_80
        +String mlflow_group_run_id
    }

    class EtlRunAudit {
        +Integer etl_run_id
        +DateTime started_at
        +DateTime finished_at
        +String status
        +Integer rows_read
        +Integer rows_upserted
        +Integer rows_rejected
        +String git_sha
    }

    class AuditRejectedRow {
        +Long rejected_id
        +Integer etl_run_id
        +String source_file
        +Integer line_number
        +String reason_code
        +String raw_payload_json
    }

    %% Relations et Cardinalités
    Country "1" *-- "1..*" Market : possède >
    Country "1" --> "0..*" ExchangeRate : utilise >
    Market "1" o-- "0..*" TimeSeriesCatalog : localise (FK composite market+country) >
    Commodity "1" o-- "0..*" TimeSeriesCatalog : qualifie >
    RefUnitConversion "1" --> "0..*" TimeSeriesCatalog : définit unit_measure >
    RefUnitConversion "1" --> "0..*" PriceObservation : convertit raw_unit >

    TimeSeriesCatalog "1" *-- "1..*" PriceObservation : contient (FK series_id+frequency) >
    CalendarPeriod "1" o-- "0..*" PriceObservation : date (FK calendar_id+frequency) >

    TrainingRun "1" *-- "1..*" ConformalQuantiles : calibre >
    TrainingRun "1" *-- "1..*" PriceForecast : génère >
    TrainingRun "1" *-- "1..*" PriceAnomaly : détecte >
    TrainingRun "1" *-- "1..*" SeriesModelMetrics : évalue >

    TimeSeriesCatalog "1" *-- "0..*" PriceForecast : projette >
    TimeSeriesCatalog "1" *-- "0..*" PriceAnomaly : signale >
    TimeSeriesCatalog "1" *-- "0..*" SeriesModelMetrics : mesure >

    EtlRunAudit "1" *-- "0..*" AuditRejectedRow : isole en quarantaine >
```

---

## 2. Comment lire ce diagramme ?

1. **L'alignement 1-pour-1 avec l'entrepôt de données** :
   - `PriceObservation` ne contient plus `reference_year` ni `reference_month` : elle est liée à `CalendarPeriod` et `TimeSeriesCatalog` via le couple `(calendar_id, frequency)` et `(series_id, frequency)`, et distingue `source_flag` (`actual`, `aggregate`, `official_faostat`) du booléen unifié `is_observed` (`True` / `False`).
2. **La gouvernance des exécutions (`TrainingRun` et `EtlRunAudit`)** :
   - À gauche en bas, `EtlRunAudit` agrège les lignes rejetées (`AuditRejectedRow`), y compris les éventuelles collisions de normalisation d'unité (`resolve_unit_collision`).
   - Au centre, `TrainingRun` regroupe de manière cohérente les quantiles conformes (`ConformalQuantiles`), les prévisions (`PriceForecast`), les anomalies (`PriceAnomaly`) et les métriques par série (`SeriesModelMetrics`).

---

## 3. Deux questions qu'un recruteur pourrait poser sur ce diagramme

### Question 1 : *« Pourquoi avoir remplacé le simple attribut `price_flag` par le couple `(source_flag, is_observed)` dans `PriceObservation` ? »*
> **Réponse conseillée** :
> « Parce que nos deux fournisseurs de données utilisent des conventions différentes : le PAM (WFP) utilise `actual` vs `aggregate`, tandis que FAOSTAT fournit les séries officielles marocaines (`official_faostat`). Si le code du pipeline ML filtrait naïvement sur `source_flag == 'actual'`, il exclurait par erreur l'IPC alimentaire du Maroc ! En introduisant le booléen métier `is_observed = True` (pour `actual` et `official_faostat`) et `False` (pour `aggregate`), tous les algorithmes en aval (calcul d'éligibilité, entraînement ML, détection d'anomalies) filtrent sur un prédicat unique `is_observed == True`, tout en conservant `source_flag` pour l'auditabilité. »

### Question 2 : *« Quel est le rôle de la classe `ConformalQuantiles` entre `TrainingRun` et `PriceForecast` ? »*
> **Réponse conseillée** :
> « Dans notre méthode de Prédiction Conforme (*Split Conformal Prediction*), les déciles d'erreur relative ($q_{\text{rel}, 10}$ et $q_{\text{rel}, 90}$) sont calibrés au niveau du **groupe `(country_iso3, commodity_group, model_name, horizon_months, eval_window)`** (soit 19 groupes $\times 3$ horizons), puis appliqués à chacune des 738 séries individuelles pour construire `[yhat_lower_80, yhat_upper_80]`. Persister l'objet `ConformalQuantiles` rattaché à `TrainingRun` permet d'inspecter directement la largeur relative du cône d'incertitude par pays, produit et horizon (par exemple comparer $[-7\%, +11\%]$ à $t+1$ contre $[-16\%, +24\%]$ à $t+6$) sans avoir à la recalculer à partir des prévisions individuelles. »
