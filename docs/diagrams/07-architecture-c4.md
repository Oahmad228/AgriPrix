# Diagramme 07 — Architecture C4 : Contexte et Conteneurs (*C4 Model*)

> **Termes techniques introduits dans ce document (en une phrase simple)** :
> - **Modèle C4 (*Context, Containers, Components, Code*)** : Une méthode de schématisation d'architecture logicielle créée par Simon Brown qui présente le système par niveaux de zoom successifs (C1 : Contexte global ; C2 : Conteneurs déployables).
> - **Cloisonnement multi-bases PostgreSQL (`agriprix_dw` vs `mlflow_db`)** : La séparation logique au sein d'un même serveur PostgreSQL entre la base de l'entrepôt métier (`agriprix_dw`) et la base interne de suivi MLOps (`mlflow_db`), chacune disposant de ses propres rôles et permissions SQL.

---

## 1. Niveau C1 — Diagramme de Contexte Système (*System Context*)

```mermaid
flowchart TB
    %% Utilisateurs & Clients externes
    Analyst["👤 Analyste Sécurité Alimentaire<br/>[Personne : Kofi - PAM / ONG]<br/><i>Identifie les tensions de marché et<br/>anticipe les achats avant la soudure</i>"]
    Decider["🏛️ Chargée d'Études Économiques<br/>[Personne : Yasmine - Ministère]<br/><i>Compare la dynamique des prix locaux<br/>et prépare les bulletins d'alerte</i>"]
    ThirdParty["💻 Développeur / Système Tiers<br/>[Personne ou Système Externe]<br/><i>Consomme l'API REST JSON (/prices, /forecasts,<br/>/anomalies) pour ses propres analyses</i>"]
    AdminOps["🛠️ Administrateur Data / MLOps<br/>[Personne : Rôle Exploitation & Ingénierie]<br/><i>Supervise l'ETL, l'entraînement ML,<br/>la qualité des données et le CI/CD</i>"]

    %% Système Central
    subgraph CentralSystem ["Système Cible"]
        AgriPrix["🌾 <b>AgriPrix Observatory</b><br/>[Système Logiciel & Data]<br/><i>Plateforme d'observation, de détection d'anomalies<br/>et de prévision à 1, 3 et 6 mois (avec intervalles<br/>conformes à 80 %) des prix alimentaires en Afrique<br/>de l'Ouest (UEMOA) et au Maroc</i>"]
    end

    %% Systèmes Externes
    HDX["🌐 <b>UN OCHA HDX / WFP VAM</b><br/>[Système Externe - Open Data CC BY 4.0]<br/><i>API CKAN & Fichiers CSV mensuels des prix<br/>alimentaires sur 207 marchés (SEN, MLI, BFA, NER, CIV)</i>"]
    FAO["🌐 <b>FAOSTAT Bulk Repository</b><br/>[Système Externe - Open Data CC BY 4.0]<br/><i>Archives ZIP officielles pour le Maroc :<br/>IPC alimentaire mensuel (base 2015=100)<br/>et Prix producteurs annuels (MAD/t)</i>"]
    GHA["⚙️ <b>GitHub Actions (CI/CD)</b><br/>[Système Externe - Intégration Continue]<br/><i>Exécute les tests pytest/ruff, compile les images<br/>multi-arch (amd64 + arm64) et déclenche la mise à jour</i>"]
    GHCR["📦 <b>GitHub Container Registry (GHCR)</b><br/>[Système Externe - Registre d'Images OCI]<br/><i>Héberge les images Docker multi-architecture<br/>(linux/amd64 et linux/arm64)</i>"]

    %% Interactions Utilisateurs -> Système
    Analyst -- "Consulte les cartes, prévisions (t+1..6)<br/>et exporte les CSV [HTTPS]" --> AgriPrix
    Decider -- "Consulte les alertes d'anomalies<br/>et les séries nationales/marchés [HTTPS]" --> AgriPrix
    ThirdParty -- "Interroge /api/v1/prices, /forecasts,<br/>/anomalies, /metadata [HTTPS JSON]" --> AgriPrix
    AdminOps -- "Déclenche make up / etl / train<br/>et inspecte les runs MLflow [CLI / HTTPS]" --> AgriPrix

    %% Interactions Système <-> Systèmes Externes (Sens exact des flux réseau)
    AgriPrix -- "Interroge les métadonnées CKAN (package_show)<br/>et télécharge les CSV vérifiés [HTTPS GET]" --> HDX
    AgriPrix -- "Télécharge les archives ZIP<br/>CP et PP [HTTPS GET]" --> FAO
    GHA -- "Construit et pousse les images<br/>multi-arch [Docker Push HTTPS]" --> GHCR
    GHA -- "Déclenche le déploiement continu<br/>sur l'hôte de démo [SSH]" --> AgriPrix
    AgriPrix -- "Télécharge les images conteneurs<br/>[Docker Pull HTTPS]" --> GHCR
```

---

## 2. Niveau C2 — Diagramme des Conteneurs (*Container Diagram* : Cœur MVP vs Bonus Sprint 5)

```mermaid
flowchart TB
    %% Acteurs externes
    UserWeb["👤 Utilisateurs Web (Kofi & Yasmine)<br/>[Navigateur HTTPS]"]
    ClientAPI["💻 Développeur / Système Tiers<br/>[Client HTTP REST]"]
    ExtData["🌐 Serveurs Open Data<br/>[HDX CKAN API & FAOSTAT S3 Bulk]"]

    subgraph HostBoundary ["Hôte Docker : Laptop Windows 16 Go (WSL2) ou VM Cloud Démo (Oracle ARM64 / VPS x86) — Budget RAM MVP <= 3,25 Go"]
        
        %% Proxy Frontal (Démo Publique Sprint 4)
        Proxy["🔒 <b>Reverse Proxy (Démo Cloud)</b><br/>[Caddy 2 Alpine — mem_limit: 64m]<br/><i>Terminaison TLS HTTPS automatique<br/>et routage vers Dashboard / API</i>"]

        subgraph MVPBoundary ["🟢 CŒUR MVP (Sprints 1 à 4 — Démarré par `docker compose up`)"]
            
            UI["🖥️ <b>Dashboard Analytique (`dashboard`)</b><br/>[Python 3.11-slim / Streamlit + Plotly]<br/><b>mem_limit: 512m | cpus: 0.50</b><br/><i>Interface interactive : Carte des marchés,<br/>courbes Retail par défaut, cônes d'incertitude 80 %,<br/>alertes d'anomalies et bandeaux d'inéligibilité</i>"]

            API["⚡ <b>API REST (`api`)</b><br/>[Python 3.11-slim / FastAPI + Pydantic + SlowAPI]<br/><b>mem_limit: 512m | cpus: 0.75</b><br/><i>Expose /health, /prices, /forecasts, /anomalies,<br/>/metadata. Rate-limit (60 req/min/IP), CORS strict,<br/>conversion devise optionnelle sous Feature Flag</i>"]

            JobRunner["⚙️ <b>Exécuteur Pipeline (`job-runner`)</b><br/>[Python 3.11-slim / Pandas + LightGBM + Statsmodels]<br/><b>mem_limit: 1280m | cpus: 1.50 (Éphémère : make etl / train)</b><br/><i>1. ETL + Contrôle intégrité HDX (DQ-01/DQ-02)<br/>2. Entraînement 19 groupes (W1-W2 val, W3 test)<br/>3. Quantiles conformes & Anomalies (MAD x 1.4826)</i>"]

            subgraph PGContainer ["🗄️ Conteneur Serveur SGBD (`db` : PostgreSQL 16-alpine — mem_limit: 512m | cpus: 0.75)"]
                DB_DW[("🏛️ <b>Base `agriprix_dw` (Entrepôt Étoile)</b><br/><i>333 924 obs, 738 séries ML, training_run.<br/>Rôles dédiés :<br/>- `agriprix_etl_writer` (RW)<br/>- `agriprix_api_readonly` (RO)</i>")]
                DB_ML[("🔬 <b>Base `mlflow_db` (Backend MLflow)</b><br/><i>Tables internes MLflow isolées.<br/>Rôle dédié : `mlflow_user` (RW sur mlflow_db,<br/>aucun droit sur agriprix_dw)</i>")]
            end

            MLflow["📊 <b>Serveur MLOps (`mlflow`)</b><br/>[Python 3.11-slim / MLflow Tracking Server]<br/><b>mem_limit: 512m | cpus: 0.50</b><br/><i>Enregistre les 57 runs de groupes (19 x 3)<br/>+ 1 run parent = 58 runs par campagne</i>"]

            VolPG[("💾 Volume Nommé Docker<br/>`pgdata`<br/><i>Stockage natif Linux WSL2</i>")]
            VolML[("💾 Volume Nommé Docker<br/>`mlflow_artifacts`<br/><i>Modèles sérialisés & Rapports</i>")]
        end

        subgraph BonusBoundary ["🟣 EXTENSION BONUS — SPRINT 5 (`Could Have` — Profils optionnels `--profile observability / bi`)"]
            Prom["📈 <b>Prometheus</b><br/>[prom/prometheus — mem_limit: 256m]<br/><i>Collecte les métriques HTTP /metrics<br/>de FastAPI et la fraîcheur des données</i>"]
            Graf["📊 <b>Grafana</b><br/>[grafana/grafana-oss — mem_limit: 256m]<br/><i>Tableaux de bord techniques DevOps<br/>(latence p95, taux d'erreur, RAM)</i>"]
            Meta["📉 <b>Metabase BI</b><br/>[metabase/metabase — mem_limit: 768m]<br/><i>Exploration SQL décisionnelle self-service<br/>branchée en lecture seule</i>"]
        end
    end

    %% Relations Utilisateurs & Clients -> Système
    UserWeb -- "HTTPS (443) / HTTP (8501)" --> Proxy
    ClientAPI -- "HTTPS (443) / HTTP (8000) JSON" --> Proxy
    Proxy --> UI
    Proxy --> API

    %% Relations internes MVP (Règle stricte : UI -> API -> DB_DW)
    UI -- "Appels REST JSON uniquement<br/>[HTTP interne port 8000]" --> API
    API -- "SELECT uniquement sur agriprix_dw<br/>[TCP 5432 — Rôle: agriprix_api_readonly]" --> DB_DW

    JobRunner -- "HTTPS GET : API CKAN + CSV/ZIP" --> ExtData
    JobRunner -- "UPSERT atomiques sur agriprix_dw<br/>[TCP 5432 — Rôle: agriprix_etl_writer]" --> DB_DW
    JobRunner -- "Log 58 runs & artefacts modèles<br/>[HTTP interne port 5000]" --> MLflow

    MLflow -- "Backend store isolé sur mlflow_db<br/>[TCP 5432 — Rôle: mlflow_user]" --> DB_ML
    DB_DW --- VolPG
    DB_ML --- VolPG
    MLflow --- VolML

    %% Relations Bonus Sprint 5
    Prom -. "Scrape /metrics [HTTP]" .-> API
    Graf -. "Requête PromQL" .-> Prom
    Meta -. "SELECT sur agriprix_dw<br/>[Rôle: agriprix_api_readonly]" .-> DB_DW
```

---

## 3. Récapitulatif du Budget Ressources et du Cloisonnement SQL

| Conteneur | Périmètre | Image de base | Limite RAM | Limite CPU | Base & Rôle SQL utilisés |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `db` | **MVP (S1)** | `postgres:16-alpine` | `512 Mo` | `0.75` | Héberge 2 bases isolées : `agriprix_dw` et `mlflow_db` |
| `mlflow` | **MVP (S2)** | `python:3.11-slim` | `512 Mo` | `0.50` | Base `mlflow_db` uniquement via le rôle `mlflow_user` |
| `api` | **MVP (S3)** | `python:3.11-slim` | `512 Mo` | `0.75` | Base `agriprix_dw` uniquement via `agriprix_api_readonly` (`SELECT`) |
| `dashboard` | **MVP (S4)** | `python:3.11-slim` | `512 Mo` | `0.50` | **Aucun accès SQL** (passe à 100 % par `api` HTTP) |
| `job-runner` | **MVP (S1–S3)** | `python:3.11-slim` | `1 280 Mo` | `1.50` | Base `agriprix_dw` via `agriprix_etl_writer` (`SELECT/INSERT/UPDATE`) |
| **TOTAL MVP** | **Sprints 1 à 4** | — | **2 048 Mo repos / 3 328 Mo pic** | **2.50 à 4.00** | **Strictement sous la barre des 4 Go de RAM** |

---

## 4. Comment lire ces diagrammes ?

1. **Sur le Niveau C1 (Contexte)** :
   - Les personnes sont représentées par leur **rôle fonctionnel** (`Analyste`, `Chargée d'Études`, `Développeur / Système Tiers`, `Administrateur Data / MLOps`).
   - Les flèches respectent le sens d'appel réseau : `GitHub Actions` pousse (`docker push`) vers `GHCR`, tandis qu'`AgriPrix Observatory` tire (`docker pull`) les images depuis `GHCR`.
2. **Sur le Niveau C2 (Conteneurs)** :
   - Zoomez sur le conteneur `db` : au lieu de mélanger les tables métier de l'entrepôt et les tables internes d'alembic/MLflow dans une seule base, le script d'initialisation `/docker-entrypoint-initdb.d/01-init.sql` crée **deux bases de données distinctes** (`agriprix_dw` et `mlflow_db`) et **trois rôles cloisonnés** (`agriprix_etl_writer`, `agriprix_api_readonly`, `mlflow_user`), tout en mutualisant le même processus `postgres:16-alpine` de `512 Mo` pour économiser la RAM.

---

## 5. Deux questions qu'un recruteur pourrait poser sur cette architecture C4

### Question 1 : *« Pourquoi avoir créé deux bases de données séparées (`agriprix_dw` et `mlflow_db`) avec trois rôles SQL distincts à l'intérieur du même conteneur PostgreSQL ? »*
> **Réponse conseillée** :
> « Lancer deux conteneurs PostgreSQL distincts aurait doublé la consommation mémoire de la base de données (`2 x 512 Mo`), alors que créer deux bases logiques (`CREATE DATABASE agriprix_dw` et `CREATE DATABASE mlflow_db`) au sein de la même instance `postgres:16-alpine` ne coûte quasiment aucun octet de RAM supplémentaire. En revanche, sur le plan de la sécurité et de la propreté du schéma, cette séparation est essentielle : MLflow crée automatiquement une quinzaine de tables techniques (`experiments`, `runs`, `metrics`, `alembic_version`) et exécute des migrations de schéma. En isolant MLflow dans `mlflow_db` avec son propre utilisateur `mlflow_user`, il ne pollue pas l'entrepôt en étoile `agriprix_dw` et ne possède aucun droit de lecture ou d'écriture sur les données métier. »

### Question 2 : *« Sur le diagramme C1, pourquoi la flèche entre AgriPrix Observatory et GitHub Container Registry (GHCR) part-elle d'AgriPrix vers GHCR ? »*
> **Réponse conseillée** :
> « Parce qu'en modélisation C4, le sens d'une flèche indique qui initie la requête ou la dépendance réseau. Un registre de conteneurs comme GHCR est un serveur de stockage passif : il ne se connecte jamais de lui-même à notre machine virtuelle. C'est `GitHub Actions` qui initie un `HTTPS POST/PUT (docker push)` vers `GHCR`, puis déclenche par `SSH` la commande `docker compose pull` sur l'hôte `AgriPrix Observatory`, lequel initie alors une requête sortante `HTTPS GET (docker pull)` vers `GHCR`. »
