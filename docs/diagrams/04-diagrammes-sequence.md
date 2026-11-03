# Diagramme 04 — Diagrammes de séquence des 3 scénarios clés (*Sequence Diagrams*)

> **Termes techniques introduits dans ce document (en une phrase simple)** :
> - **Diagramme de séquence (*Sequence Diagram*)** : Un schéma UML chronologique (lu de haut en bas) qui montre l'ordre exact des appels entre les conteneurs du système.
> - **Isolation des bases et rôles SQL (`agriprix_dw` vs `mlflow_db`)** : Le fait d'héberger dans le serveur PostgreSQL deux bases de données logiquement séparées avec des utilisateurs dédiés afin que le serveur MLflow ne puisse ni lire ni modifier ni encombrer les tables métier de l'entrepôt.

---

## 1. Scénario 1 — Exécution du pipeline ETL avec contrôle d'intégrité anti-troncature HDX et normalisation `ref_unit_conversion`

```mermaid
sequenceDiagram
    autonumber
    actor DevOps as ⏰ Planificateur / DevOps<br/>(make etl)
    participant Runner as 🐍 Conteneur job-runner<br/>(ETL Python)
    participant HDX as 🌐 API CKAN & Serveur HDX<br/>(data.humdata.org)
    participant FAO as 🌐 Bulk Server FAOSTAT<br/>(bulks-faostat.fao.org)
    participant DB as 🗄️ PostgreSQL 16 (agriprix_dw)<br/>(Rôle : agriprix_etl_writer)

    DevOps->>Runner: Lance `python -m src.etl.run_pipeline`
    activate Runner
    Runner->>DB: INSERT INTO etl_run_audit (started_at, status='RUNNING', git_sha)

    loop Pour chacun des 5 pays UEMOA (SEN, MLI, BFA, NER, CIV)
        Runner->>HDX: GET /api/3/action/package_show?id=wfp-food-prices-for-{iso3}
        HDX-->>Runner: JSON Métadonnées (resource_url, expected_size, md5_hash, fs_check_info)
        Runner->>Runner: Pause polie (sleep 2s anti-WAF)
        Runner->>HDX: GET {resource_url} (Téléchargement flux CSV)
        alt Passerelle DQ-01 (HTTP 202 WAF) ou DQ-02 (size != expected_size ou MD5/lignes invalides)
            HDX-->>Runner: Flux incomplet (ex. NER tronqué à 57k lignes au lieu de 68.7k)
            Runner->>Runner: Rejet immédiat du fichier corrompu + Backoff exponentiel (5s, 15s)
            Runner->>HDX: Nouvelle tentative GET {resource_url}
            HDX-->>Runner: HTTP 200 CSV complet (taille, MD5 et lignes conformes)
        else Téléchargement intègre dès le 1er essai
            HDX-->>Runner: HTTP 200 CSV complet (taille, MD5 et lignes conformes)
        end
    end

    Runner->>FAO: GET ConsumerPriceIndices_E_Africa_NOFLAG.zip & Prices_E_Africa_NOFLAG.zip
    FAO-->>Runner: Archives ZIP intègres (Filtrage Area = Morocco)

    Runner->>Runner: Dépivotage FAOSTAT + Application ref_unit_conversion (métriques -> KG/L ; locales non converties)<br/>Qualification source_flag ('actual', 'official_faostat', 'aggregate') & is_observed (TRUE/FALSE)
    Runner->>Runner: Déduplication sur (series_id, calendar_id, source_flag) + Résolution collision unité (priorité unité native)<br/>Calcul is_ml_eligible (sur is_observed=TRUE, fraîcheur <= 3m, >= 60m continus sans imputer -> 738 séries)

    Runner->>DB: BEGIN TRANSACTION
    Runner->>DB: UPSERT dim_country, dim_market, dim_commodity, ref_unit_conversion, dim_calendar, dim_series_catalog
    Runner->>DB: UPSERT fact_price_observation (ON CONFLICT (series_id, calendar_id, source_flag) DO UPDATE)
    Runner->>DB: INSERT INTO audit_rejected_rows & UPDATE etl_run_audit (status='SUCCESS')
    Runner->>DB: COMMIT TRANSACTION
    DB-->>Runner: Confirmation (333 924 observations synchronisées, 0 doublon)

    Runner-->>DevOps: Code retour 0 + Rapport JSON (data/reports/etl_quality_report.json)
    deactivate Runner
```

---

## 2. Scénario 2 — Entraînement global (Sélection sur Fenêtres 1–2, Test final sur Fenêtre 3) et publication versionnée (`training_run`)

```mermaid
sequenceDiagram
    autonumber
    actor DevOps as ⚙️ Planificateur / DevOps<br/>(make train)
    participant Trainer as 🧠 Conteneur job-runner<br/>(Module ML & Anomalies)
    participant DB as 🗄️ PostgreSQL 16 (agriprix_dw)<br/>(Rôle : agriprix_etl_writer)
    participant MLflow as 📊 Serveur MLflow<br/>(Base dédiée : mlflow_db / Rôle : mlflow_user)

    DevOps->>Trainer: Lance `python -m src.ml.train_pipeline`
    activate Trainer

    Trainer->>MLflow: start_run(run_name="training_campaign") -> mlflow_parent_run_id
    Trainer->>DB: INSERT INTO training_run (run_timestamp, max_data_date, git_sha, mlflow_parent_run_id) RETURNING run_id
    Trainer->>DB: SELECT séries & observations WHERE is_ml_eligible = TRUE AND is_observed = TRUE
    DB-->>Trainer: 738 séries mensuelles (737 Retail UEMOA 'actual' + 1 IPC Maroc 'official_faostat') dans 19 groupes

    loop Pour chacun des 19 groupes (country_iso3, commodity_group) [18 groupes UEMOA + 1 groupe MAR CPI_Food]
        Trainer->>Trainer: Conserver les mois manquants à NaN (aucune imputation)<br/>Aligner les marchés sur les dates de coupure communes T_cutoff (W1: 2021-12, W2: 2024-06, W3: 2025-08)
        loop Pour chaque horizon h in {1, 3, 6} mois
            Trainer->>Trainer: Entraîner SeasonalNaive, Ridge_Seasonal/SARIMA, LightGBM_Global sur W1 (671/605 séries) & W2 (738 séries)
            Trainer->>Trainer: Calculer vrai MASE (dénominateur in-sample t-12) et RelMAE_h sur W1-W2<br/>Sélectionner le modèle champion du groupe UNIQUEMENT sur W1-W2
            Trainer->>Trainer: Évaluer une seule fois sur la Fenêtre 3 (Hold-out Test 2025-2026 : 738 séries)<br/>Calibrer les quantiles relatifs [q_rel_10, q_rel_90] et mesurer PICP_80 (W3 récent & W1 choc 2022)
        end
        Trainer->>MLflow: log_runs (3 runs enfants par groupe : SeasonalNaive, Ridge_Seasonal, LightGBM_Global -> 57 runs enfants)
        MLflow-->>Trainer: mlflow_group_run_ids
        Trainer->>Trainer: Ré-entraîner le champion jusqu'à max_data_date et prédire t+1, t+3, t+6
    end

    Trainer->>Trainer: Exécuter détection d'anomalies (résidu log-tendance-saisonnalité >= 60 mois, MAD * 1.4826)<br/>Qualifier WARNING (|z| >= 2.5) et CRITICAL (|z| >= 3.5) (Validation du catalogue de 5 crises en test CI pytest)

    Trainer->>DB: BEGIN TRANSACTION
    Trainer->>DB: INSERT INTO fact_conformal_quantiles (run_id, ...)
    Trainer->>DB: INSERT INTO fact_model_metrics_by_series (run_id, ...)
    Trainer->>DB: INSERT INTO fact_forecast (run_id, ... [2 214 prévisions])
    Trainer->>DB: INSERT INTO fact_anomaly (run_id, ...)
    Trainer->>DB: UPDATE training_run SET is_production_active = TRUE WHERE run_id = current_run_id
    Trainer->>DB: COMMIT TRANSACTION
    DB-->>Trainer: Confirmation COMMIT

    Trainer-->>DevOps: Code retour 0 (Campagne ML terminée en < 3 min, 58 runs MLflow enregistrés)
    deactivate Trainer
```

---

## 3. Scénario 3 — Consultation interactive par un utilisateur ou un développeur tiers (`Streamlit / Client API` $\rightarrow$ `FastAPI` $\rightarrow$ `PostgreSQL Lecture Seule`)

```mermaid
sequenceDiagram
    autonumber
    actor User as 👤 Personas (Fatou, Youssef, Moussa) / Développeur Tiers<br/>(Navigateur Web ou Client HTTP)
    participant UI as 🖥️ Conteneur dashboard<br/>(Streamlit + Plotly)
    participant API as ⚡ Conteneur api<br/>(FastAPI + SlowAPI)
    participant DBRO as 🗄️ PostgreSQL 16 (agriprix_dw)<br/>(Rôle : agriprix_api_readonly)

    User->>UI: Sélectionne un Pays, un Marché et un Produit<br/>(Filtre par défaut : pricetype = 'Retail')
    activate UI

    UI->>API: GET /api/v1/prices?country=SEN&market=SEN_DAKAR_TILENE&commodity=WFP_RICE_IMP&pricetype=Retail
    activate API
    API->>API: Vérifier Rate Limit (<= 60 req/min/IP) & Valider paramètres Pydantic
    API->>DBRO: SELECT serie, observations FROM dim_series_catalog JOIN fact_price_observation JOIN dim_calendar
    DBRO-->>API: Métadonnées série (is_ml_eligible, frequency, value_type, unit_measure) + Observations
    API-->>UI: HTTP 200 JSON (Série historique + métadonnées d'éligibilité)
    deactivate API

    alt La série est éligible au ML (is_ml_eligible == true, ex. Riz Retail à Dakar ou IPC 23013 Maroc)
        par Appels parallèles Prévisions & Anomalies (sur le run_id actif)
            UI->>API: GET /api/v1/forecasts?series_id=42
            activate API
            API->>DBRO: SELECT forecast, quantiles, metrics FROM fact_forecast JOIN training_run WHERE is_production_active = TRUE
            DBRO-->>API: Prévisions à t+1, t+3, t+6 + intervalles 80 % + MASE/RelMAE/PICP (W3 & Choc 2022)
            API-->>UI: HTTP 200 JSON (Prévisions + Intervalles conformes à 80 %)
            deactivate API
        and
            UI->>API: GET /api/v1/anomalies?series_id=42
            activate API
            API->>DBRO: SELECT calendar_id, observed_value, expected_value, z_score_robust, severity FROM fact_anomaly JOIN training_run WHERE is_production_active = TRUE
            DBRO-->>API: Liste des chocs détectés (ex. Août 2008, Août 2022)
            API-->>UI: HTTP 200 JSON (Anomalies qualifiées WARNING / CRITICAL)
            deactivate API
        end
        UI-->>User: Affiche le graphique Plotly : Courbe historique + Cône d'incertitude 80 % (t+1, t+3, t+6)<br/>+ Marqueurs d'anomalies + Encart performance (MASE, RelMAE & PICP)
    else La série n'est PAS éligible au ML (is_ml_eligible == false, ex. Producteur annuel Maroc ou CIV aggregate)
        UI->>API: GET /api/v1/anomalies?series_id=815 (si frequency=='MONTHLY' et >= 60 mois observés)
        API-->>UI: HTTP 200 JSON
        UI-->>User: Affiche la courbe historique seule + Bandeau pédagogique d'avertissement :<br/>"Série en consultation seule : [ineligibility_reason] — Aucune prévision extrapolée."
    end
    deactivate UI
```

---

## 4. Comment lire ces diagrammes ?

1. **Dans le Scénario 2 (étape 4)**, la requête filtre sur `WHERE is_ml_eligible = TRUE AND is_observed = TRUE` : grâce au booléen `is_observed`, les 737 séries `actual` UEMOA **et** la série `official_faostat` de l'IPC Alimentaire du Maroc sont récupérées ensemble sans exclusion accidentelle.
2. **Dans le Scénario 2 (étapes 3 et 12–18)**, toutes les insertions analytiques se font sous un nouvel identifiant `run_id` de la table `training_run`, qui ne bascule à `is_production_active = TRUE` qu'à la toute fin de la transaction SQL (`COMMIT`). Pendant les 2 à 3 minutes que dure l'entraînement, l'API continue donc de servir l'ancien `run_id` sans aucune coupure ni lecture partielle (*Zero-Downtime Model Refresh*).

---

## 5. Deux questions qu'un recruteur pourrait poser sur ces séquences

### Question 1 : *« Dans le Scénario 2, que s'est-il passé lorsque vous aviez initialement écrit `WHERE price_flag = 'actual'` et comment l'avez-vous corrigé ? »*
> **Réponse conseillée** :
> « C'était un bug subtil de conception multi-sources : dans les fichiers WFP d'Afrique de l'Ouest, les vraies observations portent le drapeau `actual`, mais dans FAOSTAT pour le Maroc, elles portent le drapeau `official_faostat`. Filtrer sur `price_flag = 'actual'` éliminait silencieusement l'IPC alimentaire du Maroc lors de l'entraînement ! Nous avons donc remplacé `price_flag` par le couple `(source_flag, is_observed)` où `is_observed = TRUE` pour `actual` et `official_faostat` (et `FALSE` pour `aggregate`). Le pipeline ML filtre désormais sur `WHERE is_ml_eligible = TRUE AND is_observed = TRUE`, ce qui sélectionne exactement nos 738 séries (737 UEMOA + 1 Maroc). »

### Question 2 : *« Comment fonctionne la bascule atomique `is_production_active = TRUE` sur la table `training_run` entre le Scénario 2 et le Scénario 3 ? »*
> **Réponse conseillée** :
> « Au lieu d'écraser en place les prévisions existantes pendant que des utilisateurs consultent l'API, chaque exécution de `make train` insère ses nouvelles prévisions, anomalies, quantiles conformes et métriques avec un nouveau `run_id` (en gardant `is_production_active = FALSE` pendant les calculs). Une fois que les 19 groupes sont entraînés et que les anomalies sont calculées, une transaction atomique passe l'ancien run à `FALSE` et le nouveau `run_id` à `TRUE` (tandis que la non-régression du détecteur sur le catalogue de 5 crises historiques 2008–2023 est garantie en amont par les tests automatiques de la CI). L'API FastAPI joint `training_run WHERE is_production_active = TRUE` : la bascule est instantanée et permet de revenir en arrière (*rollback*) en une seconde si besoin. »
