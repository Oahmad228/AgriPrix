# 🌾 AgriPrix Observatory

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-100%25_Containerized-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11--slim-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16--alpine-4169E1?logo=postgresql&logoColor=white)](docker/postgres/01-init.sql)

**Plateforme data de bout en bout pour le suivi, la détection d'anomalies et la prévision conforme (1, 3 et 6 mois) des prix alimentaires en Afrique de l'Ouest (UEMOA) et au Maroc.**

---

## 🎯 Problématique et Périmètre (Données Réelles Auditées)

Dans la région du Sahel et d'Afrique de l'Ouest (**Sénégal `SEN`, Mali `MLI`, Burkina Faso `BFA`, Niger `NER`, Côte d'Ivoire `CIV`**) ainsi qu'au **Maroc (`MAR`)**, les dépenses alimentaires représentent entre **35 % et plus de 65 %** du budget des ménages. Les données publiques de prix alimentaires existent sous licence ouverte (**CC BY-IGO 3.0** via **UN OCHA HDX / PAM-WFP** et **CC BY 4.0** via **FAOSTAT**), mais restent fragmentées et dépourvues de prévisions multi-horizons probabilistes en libre accès.

**AgriPrix Observatory** unifie et modélise **333 924 observations historiques** :
- **Afrique de l'Ouest (UEMOA — Source WFP/HDX, licence `CC BY-IGO 3.0`)** : **324 040 observations mensuelles** couvrant **366 marchés dans le panier de sécurité alimentaire**, dont **183 marchés actifs éligibles à la prévision ML** regroupant **737 séries `Retail`** réparties dans **18 groupes `(Pays, Produit)`** sur 4 pays (`SEN` : 45, `MLI` : 230, `BFA` : 275, `NER` : 187 ; la Côte d'Ivoire `CIV` étant maintenue en consultation historique seule en raison de `37,49 %` de lignes modélisées `aggregate` entre 2020 et 2026).
- **Maroc (`MAR` — Source FAOSTAT Bulk, licence `CC BY 4.0`)** : **1 série nationale mensuelle d'Indice des Prix à la Consommation Alimentaire (`Item 23013`, base `2015 = 100`, 318 mois continus)** éligible à la prévision ML (+ **367 séries annuelles** de prix producteurs agricoles, soit **8 942 observations** en consultation historique seule sans mois inventé).
- **Total des séries prédites à $t+1, t+3, t+6$ mois** : **738 séries mensuelles dans 19 groupes**, évaluées en *Rolling-Origin* (sélection du modèle champion sur les Fenêtres 1–2 incluant le choc de 2022, rapport final sur la Fenêtre 3 `2025–2026`) avec **intervalles de prédiction conformes à 80 %** calibrés sur les erreurs relatives par groupe, et un **détecteur d'anomalies robuste** ($\ge 5\text{ ans}$, résidu log-tendance-saisonnalité, $\text{MAD} \times 1{,}4826$) validé en CI sur un catalogue *a priori* de 5 crises historiques documentées (`2007–2008`, `2012 Crise sahélienne`, `2020 COVID-19`, `2022 Inflation/Ukraine`, `2023–2024 Sanctions Niger`).

---

## 🏗️ Architecture Conteneurisée (Budget RAM MVP $\le 3,25\text{ Go}$)

Tout le projet s'exécute exclusivement dans **Docker Compose** sans aucune installation requise sur la machine hôte :

| Conteneur | Technologie | Limite RAM | Limite CPU | Rôle et Cloisonnement |
| :--- | :--- | :---: | :---: | :--- |
| **`agriprix-db`** | `postgres:16-alpine` | `512 Mo` | `0.75` | Héberge 2 bases isolées : `agriprix_dw` (Entrepôt en étoile) et `mlflow_db` (Backend MLflow) sur volume nommé `pgdata`. |
| **`agriprix-mlflow`** | `python:3.11-slim` | `512 Mo` | `0.50` | Serveur MLOps connecté uniquement à `mlflow_db` via `mlflow_user` (58 runs par campagne). |
| **`agriprix-api`** | `FastAPI` + `SQLAlchemy 2` | `512 Mo` | `0.75` | API REST publique connectée à `agriprix_dw` uniquement en **lecture seule (`agriprix_api_readonly`)**. |
| **`agriprix-dashboard`** | `Streamlit` + `Plotly` | `512 Mo` | `0.50` | Interface analytique qui interroge **exclusivement l'API HTTP** (zéro accès SQL direct). |
| **`job-runner`** | `Pandas` + `LightGBM` + `Pytest` | `1 280 Mo` | `1.50` | Conteneur éphémère (`make etl`, `make train`, `make test`, `make lint`) disposant du rôle `agriprix_etl_writer`. |

---

## 🚀 Démarrage Rapide (Quickstart)

### 1. Démarrer toute la plateforme en une seule commande
```bash
docker compose up -d --build
```
- **API FastAPI (Swagger UI)** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **Healthcheck API & Base** : [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Dashboard Streamlit** : [http://localhost:8501](http://localhost:8501)
- **Serveur MLflow** : [http://localhost:5000](http://localhost:5000)

### 2. Commandes du `Makefile` (100 % exécutées dans Docker)
```bash
make up       # Construit et démarre tous les services du MVP en arrière-plan
make ps       # Vérifie l'état et les healthchecks des conteneurs
make lint     # Exécute Ruff (linter + format check) dans le conteneur job-runner
make test     # Exécute la suite Pytest (couverture >= 70 %) dans le conteneur job-runner
make etl      # Lance le pipeline ETL (collecte, contrôle d'intégrité HDX, entrepôt en étoile)
make train    # Lance l'entraînement global Rolling-Origin (19 groupes), anomalies et MLflow
make down     # Arrête proprement les conteneurs
```

---

## 📚 Documentation d'Ingénierie (Livrables Phases 0 à 2)

- **Cadrage, Benchmark & Audit des Sources** :
  - [`docs/00-cadrage.md`](docs/00-cadrage.md) — Besoin, parties prenantes, personas, sources FES et pitch.
  - [`docs/01-etude-existant.md`](docs/01-etude-existant.md) — Étude comparative (WFP VAM/HDX, FAO FPMA/FAOSTAT, Banque mondiale RTFP, FEWS NET).
  - [`docs/02-sources-donnees.md`](docs/02-sources-donnees.md) — Audit empirique des 333 924 observations, `source_flag`, unités et couverture.
- **Spécifications & Backlog Agile** :
  - [`docs/03-cahier-des-charges.md`](docs/03-cahier-des-charges.md) — Objectifs SMART, exigences fonctionnelles/non-fonctionnelles, risques et glossaire.
  - [`docs/04-backlog.md`](docs/04-backlog.md) — Épopées, 20 User Stories MoSCoW, découpage en 5 sprints et plan de délestage.
- **Analyse, Conception, Diagrammes Mermaid & ADR** :
  - [`docs/05-conception.md`](docs/05-conception.md) — Synthèse de conception, règles de qualité `DQ-01..07` et stratégie de tests.
  - **Diagrammes UML / BPMN / Merise / C4** : [`01-cas-utilisation`](docs/diagrams/01-cas-utilisation.md) · [`02-processus-bpmn`](docs/diagrams/02-processus-bpmn.md) · [`03-diagramme-classes`](docs/diagrams/03-diagramme-classes.md) · [`04-diagrammes-sequence`](docs/diagrams/04-diagrammes-sequence.md) · [`05-activite-pipeline`](docs/diagrams/05-activite-pipeline.md) · [`06-modele-donnees`](docs/diagrams/06-modele-donnees.md) · [`07-architecture-c4`](docs/diagrams/07-architecture-c4.md)
  - **Architecture Decision Records (ADR)** : [`ADR-001`](docs/adr/001-surdimensionnement-architecture-devops.md) · [`ADR-002`](docs/adr/002-entrepot-postgresql-etoile-multi-grains.md) · [`ADR-003`](docs/adr/003-strategie-ml-globale-fenetre-historique-rolling-origin.md) · [`ADR-004`](docs/adr/004-intervalles-conformes-erreurs-relatives-par-groupe.md) · [`ADR-005`](docs/adr/005-dashboard-streamlit-et-bi-metabase-optionnel.md) · [`ADR-006`](docs/adr/006-devises-locales-et-feature-flag-conversion.md) · [`ADR-007`](docs/adr/007-hebergement-vps-vs-oracle-arm-et-ci-multi-arch.md)
  - [`docs/JOURNAL.md`](docs/JOURNAL.md) — Journal de bord d'ingénierie du projet.

---

## 📄 Licence

Distribué sous licence **MIT**. Voir [`LICENSE`](LICENSE). Données sources sous licences ouvertes **CC BY-IGO 3.0** (WFP / UN OCHA HDX) et **CC BY 4.0** (FAOSTAT).
