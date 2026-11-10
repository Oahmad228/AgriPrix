# 🌾 AgriPrix Observatory

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-100%25_Containerized-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11.18--slim-3776AB?logo=python&logoColor=white)](docker/Dockerfile)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16--alpine-4169E1?logo=postgresql&logoColor=white)](docker/postgres/01-init.sql)

**Plateforme data de bout en bout pour le suivi, la détection d'anomalies et la prévision (1, 3 et 6 mois, avec intervalles d'incertitude) des prix alimentaires en Afrique de l'Ouest (UEMOA) et au Maroc.**

> **État du projet (novembre 2026)** : socle technique et entrepôt de données opérationnels (ETL vérifié, 343 079 observations).
> Les modèles, la détection d'anomalies et le dashboard sont **en cours de construction**
> (voir la feuille de route ci-dessous). Ce README ne présente comme acquis que ce qui a été exécuté.

---

## 🎯 Problématique

Dans les pays suivis (**Sénégal `SEN`, Mali `MLI`, Burkina Faso `BFA`, Niger `NER`, Côte d'Ivoire `CIV`, Maroc `MAR`**), l'alimentation représente une part importante du budget des ménages (sources détaillées dans [`docs/00-cadrage.md`](docs/00-cadrage.md)). Les prix publics existent sous licence ouverte (**CC BY-IGO 3.0** via **WFP / HDX**, **CC BY 4.0** via **FAOSTAT**) mais restent fragmentés et sans prévision probabiliste en libre accès.

### Entrepôt de données (Sprint 1 — chiffres mesurés)

Mesuré le **2026-11-10** par l'exécution ETL `etl_run_id = 5`, sur les fichiers HDX mis à jour les 4 et 5 novembre 2026 et les archives FAOSTAT d'octobre 2026. Le MD5 de chaque fichier est enregistré dans la table `etl_source_file`.

| Indicateur | Valeur | Requête / commande |
| :--- | ---: | :--- |
| Observations chargées | **343 079** (336 939 mensuelles, 6 140 annuelles) | `SELECT frequency, COUNT(*) FROM fact_price_observation GROUP BY 1` |
| Lignes rejetées (quarantaine) | **0** (0,000 %) | `SELECT COUNT(*) FROM audit_rejected_rows` |
| Séries / marchés / produits | **6 623 / 367 / 227** | `dim_series_catalog`, `dim_market`, `dim_commodity` |
| Séries éligibles à la prévision | **782** dans **19 groupes** (pays, produit) et **183 marchés** | `SELECT COUNT(*) FROM dim_series_catalog WHERE is_ml_eligible` |
| Par pays | BFA 278 · MLI 264 · NER 196 · SEN 43 · MAR 1 · CIV 0 | — |
| Rechargement mensuel (sans changement) | **~22 s** de traitement (somme des étapes), dont 6,4 s de chargement des faits | logs `stage ...` de `make etl` |

**Réconciliation avec l'audit des Phases 0–2.** Sur les fichiers figés de l'audit (3 novembre 2026), l'ETL retrouve **exactement les 738 séries éligibles** annoncées, pays par pays (BFA 275, MLI 230, NER 187, SEN 45, MAR 1), avec la commande `make reconcile`. L'écart avec 782 vient uniquement des données ajoutées depuis par HDX (relevés jusqu'à septembre et octobre 2026).

Règles d'éligibilité : série mensuelle du panier (riz, mil, sorgho, maïs, niébé au détail ; IPC alimentaire du Maroc), observée dans les 3 derniers mois disponibles du pays, avec au moins **60 mois observés** dans son segment récent, sans trou de plus de 3 mois. **Aucune valeur n'est interpolée.** Les valeurs agrégées (WFP) et estimées ou imputées (FAOSTAT) sont stockées mais exclues du ML ([`ADR-009`](docs/adr/009-drapeaux-qualite-sources-et-tracabilite-des-versions.md)). La Côte d'Ivoire (relevés `aggregate` de 2020 à 2026) reste en consultation seule.

### Ce qui sera construit (cibles, non encore mesurées)
- Prévisions à 1, 3 et 6 mois évaluées en *rolling-origin* (tests successifs dans le temps sans voir le futur), avec intervalles conformes à 80 %.
- Détection d'anomalies robuste, évaluée sur un catalogue fixé à l'avance de 5 crises documentées (2008, 2012, 2020, 2022, 2023–2024), résultats rapportés tels quels.
- API REST en lecture seule, dashboard, mise à jour mensuelle et démo publique en HTTPS.

---

## 🏗️ Architecture conteneurisée

| Conteneur | Technologie | Limite RAM | Rôle |
| :--- | :--- | :---: | :--- |
| `agriprix-db` | `postgres:16-alpine` | 512 Mo | 2 bases isolées : `agriprix_dw` (entrepôt) et `mlflow_db` (suivi MLflow), volume nommé `pgdata` |
| `agriprix-mlflow` | MLflow 2.22 | 512 Mo | Suivi des expériences, connecté uniquement à `mlflow_db` |
| `agriprix-api` | FastAPI + SQLAlchemy 2 | 512 Mo | API connectée à l'entrepôt avec un rôle **en lecture seule** |
| `agriprix-dashboard` | Streamlit | 512 Mo | Interface qui passe **uniquement par l'API** (aucun accès SQL) |
| `job-runner` | Python (pandas, LightGBM, pytest, ruff) | 1 280 Mo | Conteneur éphémère pour ETL, entraînement, tests et lint |

Les ports ne sont publiés que sur `127.0.0.1`. Les dépendances Python sont figées dans [`requirements.lock`](requirements.lock) et installées telles quelles dans l'image (voir [`ADR-008`](docs/adr/008-image-unique-et-verrouillage-des-dependances.md)).

---

## 🚀 Démarrage rapide

Prérequis : Docker Desktop (ou Docker Engine + Compose v2). Rien d'autre n'est installé sur l'hôte.

```bash
docker compose up -d --build --wait
```

- API (Swagger) : http://localhost:8000/docs
- Santé API + base : http://localhost:8000/api/v1/health (`200` si la base répond, `503` sinon)
- Dashboard : http://localhost:8501
- MLflow : http://localhost:5000

### Commandes courantes

`make` est optionnel : chaque cible a son équivalent `docker compose` (utile sous Windows, où `make` n'est pas installé par défaut).

| Action | `make` | Équivalent sans `make` |
| :--- | :--- | :--- |
| Construire l'image | `make build` | `docker compose build api` |
| Démarrer la stack | `make up` | `docker compose up -d --build --wait` |
| Lint + format | `make lint` | `docker compose --profile jobs run --rm job-runner sh -c "ruff check src tests && ruff format --check src tests"` |
| Tests + couverture | `make test` | `docker compose --profile jobs run --rm job-runner pytest` |
| ETL (télécharge + vérifie + charge) | `make etl` | `docker compose --profile jobs run --rm job-runner python -m src.etl.cli` |
| ETL sans téléchargement | `make etl-offline` | `docker compose --profile jobs run --rm job-runner python -m src.etl.cli --offline` |
| Réconciliation avec l'audit | `make reconcile` | `docker compose --profile jobs run --rm job-runner python -m src.etl.reconcile data/raw/snapshot_20261103` |
| Entraînement *(Sprint 2)* | `make train` | `docker compose --profile jobs run --rm job-runner python -m src.ml.cli` |
| Arrêter (garde les données) | `make down` | `docker compose --profile jobs down` |
| Tout réinitialiser (efface les volumes) | `make clean` | `docker compose --profile jobs down -v` |

---

## 🗺️ Feuille de route

| Sprint | Contenu | État |
| :--- | :--- | :--- |
| Phases 0–3 | Cadrage, cahier des charges, conception, socle Docker/CI | ✅ terminé |
| Sprint 0.5 | Remise à niveau du socle (lock des dépendances, CI, santé API) | ✅ terminé |
| Sprint 1 | ETL HDX/FAOSTAT + contrôle d'intégrité + entrepôt en étoile | 🔄 en validation |
| Sprint 2 | Prévisions 1/3/6 mois + intervalles conformes + MLflow | ⏳ à venir |
| Sprint 3 | Détection d'anomalies validée + API sécurisée | ⏳ à venir |
| Sprint 4 | Dashboard + mise à jour mensuelle + démo publique HTTPS (fin du MVP) | ⏳ à venir |
| Sprint 5 | Bonus : Prometheus/Grafana, Kubernetes, Metabase, devises | ⏳ optionnel |

---

## 📚 Documentation d'ingénierie

- **Cadrage et sources** : [`00-cadrage`](docs/00-cadrage.md) · [`01-etude-existant`](docs/01-etude-existant.md) · [`02-sources-donnees`](docs/02-sources-donnees.md)
- **Spécifications** : [`03-cahier-des-charges`](docs/03-cahier-des-charges.md) · [`04-backlog`](docs/04-backlog.md)
- **Conception** : [`05-conception`](docs/05-conception.md) · diagrammes [`01`](docs/diagrams/01-cas-utilisation.md) [`02`](docs/diagrams/02-processus-bpmn.md) [`03`](docs/diagrams/03-diagramme-classes.md) [`04`](docs/diagrams/04-diagrammes-sequence.md) [`05`](docs/diagrams/05-activite-pipeline.md) [`06`](docs/diagrams/06-modele-donnees.md) [`07`](docs/diagrams/07-architecture-c4.md)
- **Décisions d'architecture (ADR)** : [`001`](docs/adr/001-surdimensionnement-architecture-devops.md) · [`002`](docs/adr/002-entrepot-postgresql-etoile-multi-grains.md) · [`003`](docs/adr/003-strategie-ml-globale-fenetre-historique-rolling-origin.md) · [`004`](docs/adr/004-intervalles-conformes-erreurs-relatives-par-groupe.md) · [`005`](docs/adr/005-dashboard-streamlit-et-bi-metabase-optionnel.md) · [`006`](docs/adr/006-devises-locales-et-feature-flag-conversion.md) · [`007`](docs/adr/007-hebergement-vps-vs-oracle-arm-et-ci-multi-arch.md) · [`008`](docs/adr/008-image-unique-et-verrouillage-des-dependances.md) · [`009`](docs/adr/009-drapeaux-qualite-sources-et-tracabilite-des-versions.md)
- **Journal de bord** : [`docs/JOURNAL.md`](docs/JOURNAL.md)

---

## 📄 Licence

Code sous licence **MIT** ([`LICENSE`](LICENSE)). Données sources sous licences ouvertes **CC BY-IGO 3.0** (WFP / HDX) et **CC BY 4.0** (FAOSTAT).
