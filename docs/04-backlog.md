# Phase 1 — Backlog Produit et Planification Agile en 5 Sprints (Version révisée)

> **Note pédagogique (Lexique Agile intégré)** : Chaque terme méthodologique ou technique utilisé pour la première fois dans ce document est expliqué en une phrase simple entre parenthèses.

---

## 1. Méthodologie de Gestion du Backlog et Arbitrage MVP / Bonus

Notre **Backlog Produit** (*liste ordonnée et priorisée de toutes les fonctionnalités et tâches techniques du projet*) distingue de manière stricte :
1. **Le Cœur du MVP (Sprints 1 à 4 — Catégories *Must Have* et *Should Have*)** :
   - **ETL hybride** (Afrique de l'Ouest `MARKET`/`MONTHLY`/`PRICE` en `XOF` + Maroc `NATIONAL` séparant `MONTHLY`/`INDEX` et `ANNUAL`/`PRICE` en `MAD/tonne`) + **Entrepôt PostgreSQL** (sur volume nommé Docker compatible Windows) + **Modèles de prévision à 1, 3 et 6 mois avec prédiction conforme et MLflow agrégé** + **Détection d'anomalies validée sur crises historiques + API FastAPI sécurisée** + **Dashboard Streamlit + Mise à jour mensuelle automatisée + CI GitHub Actions + Hébergement public sous Docker Compose**.
2. **Les Bonus Post-MVP (Sprint 5 — Catégorie *Could Have*)** :
   - **Supervision Prometheus + Grafana**, **Orchestration Kubernetes locale (`k3s` ou `kind` avec `CronJob` mensuel)**, **BI interne Metabase** et **Conversion active de devises sous *Feature Flag***. Ces briques ne sont engagées qu'une fois le MVP des Sprints 1 à 4 terminé, testé et stable.

> **Calibration de l'effort par sprint** : Aucun chiffrage en heures ou en points d'effort n'est figé tant qu'Amine n'a pas précisé sa **disponibilité hebdomadaire (en heures/semaine)** afin de dimensionner honnêtement la charge de chaque sprint.

---

## 2. Vue d'ensemble des Épopées (Epics) sur 5 Sprints

| Code Epic | Titre de l'Épopée | Phase / Sprint cible | Statut MoSCoW |
| :--- | :--- | :---: | :---: |
| **EPIC-0** | **Socle Docker Compose, Volumes Windows & CI GitHub Actions** | Phase 3 (Mise en place) | **Must (MVP)** |
| **EPIC-1** | **Ingestion Hybride, Typage Multi-Fréquences & Entrepôt en Étoile PostgreSQL** | **Sprint 1** | **Must (MVP)** |
| **EPIC-2** | **EDA, Éligibilité Stricte (60 mois), Prévisions 1/3/6 mois, Conformal & MLflow** | **Sprint 2** | **Must (MVP)** |
| **EPIC-3** | **Détection d'Anomalies Validée & API REST FastAPI Sécurisée** | **Sprint 3** | **Must (MVP)** |
| **EPIC-4** | **Dashboard Streamlit (Retail), Automatisation Mensuelle & Hébergement MVP** | **Sprint 4 (Fin MVP)** | **Must / Should (MVP)** |
| **EPIC-5** | **Bonus DevOps & BI Avancés : Prometheus/Grafana, Kubernetes (`k3s`/`kind`), Metabase & Devises** | **Sprint 5 (Bonus)** | **Could (Post-MVP)** |

---

## 3. Catalogue Détaillé des User Stories et Critères d'Acceptation

### EPIC-0 — Socle Docker Compose, Volumes Windows & CI GitHub Actions (Phase 3)

#### US-01 : Socle 100 % conteneurisé avec volumes nommés sous Windows et Makefile
- **Énoncé** : *En tant que* **Développeur / Évaluateur**, *je veux* démarrer, arrêter, tester et vérifier tout le projet via `docker compose up` et un `Makefile` sans rien installer sur Windows, en stockant PostgreSQL dans un **volume nommé Docker** (*espace disque géré nativement par le moteur Linux de Docker*), *afin d'* éviter les erreurs de permissions Windows/NTFS et garantir une reproductibilité totale.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `ENF-01`, `ENF-02`
- **Critères d'acceptation** :
  1. *Quand* je lance `docker compose up -d` (ou `make up`), *alors* les conteneurs du MVP démarrent sans erreur et PostgreSQL utilise un volume nommé `pgdata` (aucun montage de dossier hôte Windows pour les fichiers internes de la base).
  2. *Quand* j'inspecte le `Makefile`, *alors* les cibles `make up`, `make down`, `make test`, `make lint`, `make etl` et `make train` s'exécutent toutes dans des conteneurs Docker.

#### US-02 : Pipeline CI GitHub Actions (Lint, Build d'images Multi-Arch `amd64`/`arm64` et Tests)
- **Énoncé** : *En tant qu'* **Ingénieur Logiciel (Amine)**, *je veux* qu'un workflow **GitHub Actions** vérifie automatiquement le code (`lint`), exécute les tests et construise les images Docker en **multi-architecture (`linux/amd64` et `linux/arm64`)** avec **Docker Buildx** (*extension de Docker permettant de compiler une même image pour les processeurs PC classiques Intel/AMD `amd64` et les processeurs basse consommation `arm64` comme Oracle Cloud Ampere*), *afin de* garantir la qualité continue du MVP et sa compatibilité avec un hébergement cloud gratuit ARM ou un VPS classique.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `ENF-08`
- **Critères d'acceptation** :
  1. *Quand* un commit est poussé sur GitHub, *alors* le workflow `.github/workflows/ci.yml` lance **Ruff**, **pytest** (objectif cible $\ge 70\text{ \%}$ couverture) et valide la construction multi-architecture (`linux/amd64,linux/arm64`).

---

### EPIC-1 — Ingestion Hybride, Typage Multi-Fréquences & Entrepôt en Étoile (Sprint 1)

#### US-03 : Collecte polie et mise en cache des prix par marché en Afrique de l'Ouest (WFP HDX)
- **Énoncé** : *En tant qu'* **Analyste de données (Youssef)**, *je veux* que l'ETL télécharge avec une pause de courtoisie (et mette en cache localement) les fichiers des 5 pays UEMOA (`SEN`, `MLI`, `BFA`, `NER`, `CIV`) en conservant la colonne `price` en `XOF` et la valeur exacte de `priceflag` (`'actual'` vs `'aggregate'`), *afin de* disposer des 324 040 lignes sans déclencher le blocage *AWS WAF* de HDX.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-01`, `EF-03`, `EF-05`
- **Critères d'acceptation** :
  1. *Quand* je lance `make etl`, *alors* les 5 fichiers sont téléchargés (ou lus depuis le cache) avec `granularity_level = 'MARKET'`, `frequency = 'MONTHLY'`, `value_type = 'PRICE'` et `currency_code = 'XOF'`.
  2. *Alors* les 319 986 lignes `actual` et les 4 054 lignes `aggregate` (Côte d'Ivoire) sont distinguées par leur colonne `priceflag`.

#### US-04 : Collecte et dépivotage différencié des séries du Maroc (IPC mensuel vs Prix producteurs annuels)
- **Énoncé** : *En tant qu'* **Analyste de données (Youssef)**, *je veux* que l'ETL extraie des archives FAOSTAT S3 les séries du Maroc (`Area Code = 143`) en distinguant l'**IPC alimentaire mensuel** (`frequency = 'MONTHLY'`, `value_type = 'INDEX'`, `unit = 'Index (2015=100)'`) et les **prix producteurs agricoles annuels** (`frequency = 'ANNUAL'`, `value_type = 'PRICE'`, `unit = 'MAD/tonne'`), **sans jamais inventer de mois fictif (`YYYY-MM-15`) pour les données annuelles**, *afin de* respecter la nature exacte de chaque indicateur marocain.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-02`, `EF-04`, `EF-05`
- **Critères d'acceptation** :
  1. *Quand* `make etl` traite `ConsumerPriceIndices_E_Africa_NOFLAG.csv`, *alors* les 3 séries mensuelles marocaines (**942 observations**) sont chargées avec `frequency = 'MONTHLY'`, leur mois réel (`1..12`), `value_type = 'INDEX'` (ou `'INFLATION_RATE'`), `unit = 'Index (2015=100)'` (ou `'%'`) et `currency_code = NULL`.
  2. *Quand* `make etl` traite `Prices_E_Africa_NOFLAG.csv`, *alors* les 367 séries annuelles (**8 942 observations**) sont chargées avec `frequency = 'ANNUAL'`, rattachées uniquement à leur année `reference_year` (colonne `reference_month = NULL`), avec `value_type = 'PRICE'`, `unit = 'MAD/tonne'` et `currency_code = 'MAD'` pour l'élément `5530`.

#### US-05 : Entrepôt en étoile PostgreSQL, Rôles SQL et Règle stricte `is_ml_eligible` (60 mois continus)
- **Énoncé** : *En tant qu'* **Architecte SI Décisionnel (Youssef)**, *je veux* que l'entrepôt PostgreSQL structure les données en étoile avec les colonnes `granularity_level`, `frequency`, `value_type` et `unit`, sépare les rôles SQL (`agriprix_writer` et `agriprix_readonly`), et calcule `is_ml_eligible = TRUE` uniquement selon la **règle stricte de continuité récente sur 60 mois**, *afin de* n'entraîner des modèles que sur des séries mensuelles réelles et statistiquement solides.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-04`, `EF-06`, `EF-07`, `ENF-04`
- **Critères d'acceptation** :
  1. *Quand* `make etl` se termine, *alors* seules les séries vérifiant simultanément `frequency = 'MONTHLY'`, `priceflag = 'actual'`, appartenance au panier (ou IPC alimentaire Maroc `23013`), dernière observation $\ge \text{2024-01-15}$ et **fenêtre continue récente $\ge 60\text{ mois}$ avec $\le 3$ mois manquants consécutifs** reçoivent `is_ml_eligible = TRUE` (soit **745 séries `Retail` en UEMOA** + **1 série mensuelle IPC au Maroc** = **746 séries**).
  2. *Alors* toutes les séries annuelles du Maroc (`frequency = 'ANNUAL'`) et toutes les séries `aggregate` de Côte d'Ivoire ont `is_ml_eligible = FALSE` (consultables mais non prévues).
  3. *Alors* l'utilisateur PostgreSQL `agriprix_readonly` ne possède que le privilège `SELECT` (toute tentative de `INSERT/UPDATE/DELETE` échoue).

#### US-06 : Déduplication sur clé complète de série et contrôles automatisés de qualité
- **Énoncé** : *En tant qu'* **Analyste de données (Youssef)**, *je veux* qu'une suite de tests automatisés vérifie l'unicité sur la **clé complète d'observation `(country_iso3, market_id, commodity_id, pricetype, unit, currency_code, frequency, value_type, period_key)`** ainsi que la stricte positivité des prix et l'intégrité des colonnes de typage, *afin d'* empêcher toute fusion erronée entre prix de détail (`Retail` en `KG`) et prix de gros (`Wholesale` en `100 KG`).
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-03`, `KPI-M5`, `ENF-08`
- **Critères d'acceptation** :
  1. *Quand* je lance `make test` à la fin du Sprint 1, *alors* les tests vérifient que la clé unique inclut bien `pricetype` (`Retail`/`Wholesale`) et `unit` (`KG`/`100 KG`/`L`/`MAD/tonne`/`Index (2015=100)`), et qu'aucun doublon ni prix $\le 0$ n'existe en base.

---

### EPIC-2 — EDA, Prévisions Multi-Horizons (1/3/6 mois), Conformal Prediction & MLflow (Sprint 2)

#### US-07 : Analyse exploratoire reproductible (EDA) et vérification des 746 séries éligibles
- **Énoncé** : *En tant que* **Data Scientist (Youssef)**, *je veux* un notebook Jupyter reproductible analysant la saisonnalité, la stationnarité, les trous temporels et les différences entre les marchés UEMOA (`XOF`) et l'IPC mensuel marocain (`2015=100`), *afin de* documenter scientifiquement la modélisation.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-07`, `ENF-03`
- **Critères d'acceptation** :
  1. *Quand* on exécute le notebook d'exploration, *alors* chaque graphique est suivi d'une analyse écrite en français expliquant la saisonnalité agricole (période de soudure) et justifiant le seuil de 60 mois continus.

#### US-08 : Entraînement scalable (Modèles globaux par Produit/Pays vs Baseline) et suivi MLflow agrégé
- **Énoncé** : *En tant que* **Data Scientist (Youssef)**, *je veux* comparer sur découpage strictement chronologique (12 mois validation + 12 mois test) une **Baseline statistique vectorisée** (*Seasonal Naive* / *Drift*) et des **Modèles ML globaux par `(Pays, Produit, Horizon)`** (*Ridge* et *LightGBM / HistGradientBoosting*, plus *Holt-Winters / ETS* sur séries de référence) aux horizons **1, 3 et 6 mois**, en créant **uniquement des runs MLflow agrégés par famille de modèle et horizon** (et en stockant le détail des 746 séries dans une table PostgreSQL), *afin* que l'entraînement reste rapide ($< 3\text{ minutes}$ sur laptop) et que MLflow reste lisible.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-08`, `EF-09`, `SMART-02`
- **Critères d'acceptation** :
  1. *Quand* je lance `make train`, *alors* seules les observations `priceflag = 'actual'` des 746 séries éligibles sont utilisées, sans aucune fuite du futur (*Data Leakage*).
  2. *Alors* **MLflow** contient des runs propres par expérience globale `(model_family, horizon_months, granularity_level)` avec les métriques agrégées (`MAE`, `RMSE`, `MAPE`, `PICP`), tandis que la table PostgreSQL `fact_model_metrics_by_series` contient les scores détaillés pour chacune des 746 séries.

#### US-09 : Prévisions à 1, 3 et 6 mois et Intervalles d'Incertitude par Prédiction Conforme
- **Énoncé** : *En tant que* **Coordinatrice ONG (Fatou)** et **Analyste (Youssef)**, *je veux* obtenir pour chacune des 745 séries `Retail` ouest-africaines (en `XOF`) et pour la série mensuelle d'indice IPC alimentaire du Maroc (en `Index 2015=100`) une prévision à **1, 3 et 6 mois** entourée d'une **borne basse** et d'une **borne haute** calculées par **Prédiction Conforme Temporelle** (*quantiles empiriques des erreurs de validation*), *afin de* disposer d'une fourchette d'incertitude honnête dont le taux de couverture (**PICP**) est mesuré sur le jeu de test.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-10`, `KPI-M3`
- **Critères d'acceptation** :
  1. *Quand* les prévisions sont générées dans `fact_price_forecasts`, *alors* aucune série annuelle marocaine (`MAD/tonne`) ni aucune série `aggregate` n'est prévue.
  2. *Alors* chaque prévision inclut `horizon_months` $\in \{1, 3, 6\}$, `predicted_value`, `lower_bound`, `upper_bound`, `value_type` (`PRICE` ou `INDEX`), `unit` et le score **PICP** mesuré sur le jeu de test pour cet horizon.

---

### EPIC-3 — Détection d'Anomalies Validée & API REST FastAPI Sécurisée (Sprint 3)

#### US-10 : Détection d'anomalies saisonnières et validation CI sur un catalogue *a priori* de crises historiques (2008, 2012, 2020, 2022, 2023–2024)
- **Énoncé** : *En tant que* **Coordinatrice ONG (Fatou)** et **Data Scientist (Youssef)**, *je veux* que le détecteur repère les chocs anormaux par rapport à la tendance et la saisonnalité de chaque série mensuelle ($\ge 5\text{ ans}$, $\text{MAD} \times 1{,}4826$), génère une explication en français simple, et soit **validé dans un test automatique de la CI (`pytest`) sur un catalogue fixé *a priori* de 5 crises historiques documentées** (`2007–2008`, `2012 Crise sahélienne`, `2020 COVID-19`, `2022 Inflation/Ukraine`, `2023–2024 Sanctions Niger`) en rapportant le **rappel événement par événement** et le **taux d'alertes en période calme**, *afin de* vérifier la non-régression du détecteur sans bloquer artificiellement le pipeline mensuel de production.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-11`, `SMART-03`, `KPI-M4`
- **Critères d'acceptation** :
  1. *Quand* `make test` s'exécute dans la CI, *alors* le test automatique d'évaluation du détecteur s'exécute sur le catalogue fixé *a priori* (`SHOCK-01` 2008 à `SHOCK-05` 2023–2024), génère un tableau de rappel événement par événement, et vérifie le seuil documenté ($\ge 80\%$ des crises détectées à $|Z_{\text{rob}}| \ge 2{,}5$ et taux d'alerte hors crise $\le 10\%$).

#### US-11 : API REST FastAPI sécurisée (Lecture seule PostgreSQL, Rate Limiting, CORS restreint)
- **Énoncé** : *En tant qu'* **Ingénieur Logiciel (Amine)**, *je veux* que l'API FastAPI se connecte à PostgreSQL exclusivement avec l'utilisateur en lecture seule `agriprix_readonly`, applique une limitation du débit (*Rate Limiting*) par IP et restreigne les origines *CORS*, *afin de* pouvoir exposer la démo publique sur Internet en toute sécurité.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `ENF-04`, `ENF-05`, `ENF-06`
- **Critères d'acceptation** :
  1. *Quand* l'API FastAPI démarre, *alors* elle utilise les identifiants `agriprix_readonly`, refuse les origines CORS non autorisées et renvoie un code `HTTP 429 Too Many Requests` si une adresse IP dépasse le quota autorisé par minute.

#### US-12 : Routes API d'exploration (Retail par défaut, Multi-Fréquences), Prévisions et Anomalies
- **Énoncé** : *En tant que* **Client API (Dashboard Streamlit ou Analyste Youssef)**, *je veux* interroger les routes `/api/v1/countries`, `/api/v1/markets`, `/api/v1/commodities`, `/api/v1/series/history`, `/api/v1/forecasts`, `/api/v1/anomalies` et `/api/v1/models/metrics` avec filtrage explicite sur `granularity_level`, `frequency`, `value_type` et `pricetype` (`'Retail'` par défaut), *afin d'* alimenter le dashboard en $< 300\text{ ms}$ (p95 cible).
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-12`, `ENF-07`
- **Critères d'acceptation** :
  1. *Quand* j'appelle `/api/v1/series/history` sans préciser `pricetype`, *alors* l'API retourne par défaut les séries `'Retail'` pour l'Afrique de l'Ouest (`XOF`), et distingue clairement les séries `MONTHLY`/`INDEX` (`2015=100`) et `ANNUAL`/`PRICE` (`MAD/tonne`) pour le Maroc.
  2. *Quand* j'ouvre `/docs`, *alors* la documentation **OpenAPI** est complète et tous les tests d'intégration `pytest` de l'API passent.

---

### EPIC-4 — Dashboard Streamlit, Automatisation Mensuelle & Hébergement MVP (Sprint 4 — Fin du MVP)

#### US-13 : Vue « Décideur / ONG / Coopérative » dans Streamlit (Prix Retail par défaut)
- **Énoncé** : *En tant que* **Coordinatrice ONG (Fatou)** ou **Gérant de coopérative (Moussa)**, *je veux* une interface Streamlit claire, consommant uniquement l'API FastAPI et affichant par défaut les prix de détail (`Retail`), avec bandeau d'alertes d'anomalies en français simple et courbe de prévision à 1, 3 et 6 mois entourée de son intervalle d'incertitude conforme, *afin de* prendre mes décisions en moins de 2 minutes.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-13`, `EF-14`, `KPI-M1`
- **Critères d'acceptation** :
  1. *Quand* j'ouvre la Vue Décideur, *alors* aucune connexion directe à PostgreSQL n'est utilisée, le filtre par défaut est `Retail`, les unités et types (`XOF/KG` vs `Indice 2015=100` pour le Maroc) sont explicites, et un encadré traduit la fourchette à 1, 3 et 6 mois en langage non-technique.

#### US-14 : Vue « Analyste Data / Économiste » dans Streamlit
- **Énoncé** : *En tant qu'* **Analyste MIAGE (Youssef)**, *je veux* un onglet dédié dans Streamlit permettant d'inspecter les métriques des modèles par horizon ($H+1, H+3, H+6$), le **PICP** mesuré sur le jeu de test, les résultats de validation du détecteur d'anomalies sur les crises 2008/2022, ainsi que les séries historiques annuelles du Maroc (`MAD/tonne`) et les séries ivoiriennes (`aggregate`), *afin d'* auditer toute la chaîne méthodologique.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-15`
- **Critères d'acceptation** :
  1. *Quand* j'ouvre la Vue Analyste, *alors* tous les chiffres affichés proviennent dynamiquement de l'API FastAPI (alimentée par les exécutions réelles) et les licences `CC BY-IGO 3.0` / `CC BY 4.0` sont affichées.

#### US-15 : Mise à jour mensuelle automatisée (Planificateur ETL + Réentraînement ML)
- **Énoncé** : *En tant qu'* **Exploitant de la plateforme (Amine)**, *je veux* qu'une tâche planifiée mensuelle exécute automatiquement la collecte ETL, les tests de qualité et le réentraînement des modèles de prévision et d'anomalies, *afin que* l'observatoire se mette à jour chaque mois sans intervention manuelle.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `EF-16`
- **Critères d'acceptation** :
  1. *Quand* la tâche mensuelle planifiée est déclenchée dans Docker Compose (ou via le workflow planifié), *alors* l'enchaînement `ETL -> Validation Qualité -> Réentraînement ML` s'exécute de manière idempotente (sans créer de doublons en base).

#### US-16 : Hébergement de la Démo Publique sous Docker Compose (Reverse Proxy HTTPS) et README final
- **Énoncé** : *En tant que* **Candidat en entretien de stage (Amine)**, *je veux* une configuration de déploiement sous Docker Compose avec **Reverse Proxy HTTPS** ainsi qu'un `README.md` complet (schéma d'architecture, chiffres 100 % réels, limites connues, scénario de démo de 2 minutes), *afin de* partager un lien de démonstration public sécurisé et présenter le MVP complet aux recruteurs.
- **Priorité MoSCoW** : **Must (MVP)** | **Exigences liées** : `ENF-06`
- **Critères d'acceptation** :
  1. *Quand* le Sprint 4 est terminé, *alors* le MVP complet tourne sous Docker Compose derrière le Reverse Proxy et 100 % des résultats numériques du `README.md` sont issus des sorties réelles de nos commandes.

---

### EPIC-5 — Bonus Post-MVP : Observabilité, Kubernetes, Metabase & Devises (Sprint 5 — *Could Have*)

#### US-17 : Supervision technique avec Prometheus et Grafana (Bonus Sprint 5)
- **Énoncé** : *En tant qu'* **Ingénieur DevOps (Amine)**, *je veux* ajouter deux conteneurs **Prometheus** et **Grafana** moissonnant la route `/metrics` de FastAPI, *afin de* visualiser le débit, la latence et la santé de l'API.
- **Priorité MoSCoW** : **Could (Bonus Sprint 5)** | **Exigences liées** : `ENF-09`

#### US-18 : Orchestration Kubernetes locale (`k3s` ou `kind`) et CronJob mensuel (Bonus Sprint 5)
- **Énoncé** : *En tant qu'* **Ingénieur DevOps (Amine)**, *je veux* décliner l'architecture sous forme de manifestes **Kubernetes** (ou chart **Helm**) incluant un **`CronJob` mensuel** pour l'ETL/réentraînement, testables sur un cluster local (`k3s` ou `kind`), *afin de* démontrer mes compétences d'orchestration cloud-native.
- **Priorité MoSCoW** : **Could (Bonus Sprint 5)** | **Exigences liées** : `EF-16`, `ENF-09`, `SMART-06`

#### US-19 : BI Interne Metabase branchée en lecture seule sur PostgreSQL (Bonus Sprint 5)
- **Énoncé** : *En tant qu'* **Analyste BI / MIAGE (Youssef)**, *je veux* un conteneur **Metabase** optionnel connecté via le compte `agriprix_readonly` à l'entrepôt en étoile PostgreSQL, *afin de* démontrer mes compétences BI SQL une fois le MVP terminé et stable.
- **Priorité MoSCoW** : **Could (Bonus Sprint 5)** | **Exigences liées** : `EF-18`

#### US-20 : Conversion active de devises (`EUR`, `USD`) à l'affichage sous Feature Flag (Bonus Sprint 5)
- **Énoncé** : *En tant qu'* **Analyste International (Youssef)**, *je veux* pouvoir activer le *Feature Flag* `ENABLE_CURRENCY_CONVERSION=true` pour convertir à la volée dans l'API les séries de type `value_type = 'PRICE'` vers `EUR` ou `USD` à partir de `dim_exchange_rate` (sans jamais toucher aux séries `INDEX` ni aux données d'entraînement), *afin de* réaliser des comparaisons internationales ponctuelles.
- **Priorité MoSCoW** : **Could (Bonus Sprint 5)** | **Exigences liées** : `EF-06`, `EF-17`

---

## 4. Planification Opérationnelle en 5 Sprints et Calibration réaliste de l'effort

### 4.1 Estimation honnête de la charge (en heures de travail effectif)

Pour le **Cœur MVP (Phase 3 + Sprints 1 à 4)**, la charge totale réaliste (en travaillant en binôme avec l'assistant IA qui génère et teste le code sous ta revue) est estimée à **~52 heures de travail effectif** (et **+18 heures** pour le **Sprint 5 Bonus**, soit 70 h au total) :

| Étape | Périmètre | Thème principal | User Stories | Charge estimée (h) | Durée à **10 h/sem** *(En période de cours)* | Durée à **15 h/sem** *(Rythme soutenu)* | Durée à **25 h/sem** *(Intensif)* |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Phase 3** | **Socle MVP** | Git, Docker Compose (volumes nommés Windows), Makefile, CI Multi-Arch (`amd64`+`arm64`) | `US-01`, `US-02` | **6 h** | ~0,5 sem. | ~0,5 sem. | ~2 jours |
| **Sprint 1** | **Cœur MVP** | **ETL Hybride (contrôle d'intégrité anti-troncature) + Entrepôt Étoile + Fraîcheur relative ($\le 3$ mois $\rightarrow$ 738 séries)** | `US-03`, `US-04`, `US-05`, `US-06` | **12 h** | ~1,2 sem. | ~0,8 sem. | ~3 jours |
| **Sprint 2** | **Cœur MVP** | **EDA + Découpage par date calendrier commune + Rolling-Origin + Conformal (par erreur relative) + MLflow agrégé** | `US-07`, `US-08`, `US-09` | **14 h** | ~1,5 sem. | ~1,0 sem. | ~4 jours |
| **Sprint 3** | **Cœur MVP** | **Détection d'Anomalies (validée sur 2008/2022) + API FastAPI Sécurisée (`readonly`, *Rate Limit*, *CORS*)** | `US-10`, `US-11`, `US-12` | **10 h** | ~1,0 sem. | ~0,7 sem. | ~3 jours |
| **Sprint 4** | **Fin du MVP** | **Dashboard Streamlit (`Retail` par défaut) + Automatisation Mensuelle + Hébergement Docker Compose (VPS / ARM)** | `US-13`, `US-14`, `US-15`, `US-16` | **10 h** | ~1,0 sem. | ~0,7 sem. | ~3 jours |
| **TOTAL MVP** | **Sprints 1–4** | **Produit Complet Déployable sous Docker Compose** | **`US-01` à `US-16`** | **~52 h** | **~5,2 semaines** | **~3,5 semaines** | **~2 semaines** |
| **Sprint 5** | **Bonus Post-MVP** | **DevOps & BI Avancés : Prometheus/Grafana, Kubernetes (`k3s`/`kind` + `CronJob`), Metabase & Devises** | `US-17` à `US-20` | **+18 h** | +1,8 sem. | +1,2 sem. | +5 jours |

### 4.2 Diagnostic de faisabilité et Plan de délestage (Ce qu'on coupe si le délai est court)

> **Avis franc d'ingénieur** : Si ta disponibilité réelle `[X]` est inférieure à **10–12 h/semaine** ou si ta date cible est à **moins de 3,5 à 5 semaines**, vouloir tout coder sans compromis est **trop ambitieux** (risque de bâcler les tests ou la compréhension du code pour tes entretiens). Voici l'ordre exact des coupes de sécurité (du moins douloureux au plus structurant) :
> 1. **Coupe n°1 (Déjà actée)** : **Sacrifier le Sprint 5 entier (`-18 h`)** — Kubernetes (`k3s`/`kind`), Prometheus/Grafana, Metabase et la conversion de devises restent documentés dans la conception (Phase 2) comme trajectoire d'évolution industrielle, sans être codés.
> 2. **Coupe n°2 (`-4 h` sur le Sprint 4)** : Remplacer le conteneur démon d'ordonnancement mensuel interne par un simple **workflow GitHub Actions planifié (`on: schedule: cron: '0 3 20 * *'`)** qui appelle `make etl && make train` une fois par mois (zéro code Python supplémentaire à maintenir).
> 3. **Coupe n°3 (`-4 h` sur le Sprint 2)** : Limiter la compétition de modèles au Sprint 2 à **2 familles** au lieu de 3 : (1) la **Baseline saisonnière vectorisée** (*Seasonal Naive*) et (2) **un seul modèle ML global de panel** (*LightGBM* ou *HistGradientBoosting* par `(Pays, Produit, Horizon)`), en retirant le modèle statistique local *Holt-Winters/SARIMAX* (souvent lent et capricieux à faire converger sur 738 séries).
> 4. **Coupe n°4 (`-3 h` sur le Sprint 1)** : Ne charger dans l'entrepôt pour le Maroc que les **3 séries mensuelles d'IPC (`ConsumerPriceIndices`)** et les **5 cultures principales de `Prices_E_Africa.csv`** (Blé, Orge, Maïs, Sorgho, Sucre) au lieu de nettoyer les 367 séries annuelles secondaires (amandes, épices, etc.).
> $\rightarrow$ **Avec les Coupes 1 à 4, le MVP descend à ~41 heures** (soit **4 semaines à 10 h/semaine** ou **2,5 semaines à 16 h/semaine**) sans perdre aucun argument technique ni métier en entretien !
