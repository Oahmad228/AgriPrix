# ADR-001 : Architecture multi-conteneurs et sur-dimensionnement volontaire (Démonstration DevOps / MIAGE)

- **Statut** : Accepté
- **Date** : 2026-11-03
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `ENF-01`, `ENF-03`, `EF-18`, Contraintes non négociables n°1, n°2 et n°3

---

## 1. Contexte et Problème

Le volume total des données historiques d'AgriPrix Observatory est de **333 924 observations** après mise au format long (~35 Mo sur disque en CSV brut, moins de 150 Mo indexés en base de données). Sur le plan strictement volumétrique, un tel jeu de données tiendrait intégralement en mémoire vive (*in-memory*) dans un simple script Python local couplé à des fichiers **Parquet** (un format de fichier binaire orienté colonnes très rapide et compressé) ou une base embarquée comme **SQLite** ou **DuckDB** (un moteur analytique léger qui s'exécute directement dans le processus de l'application sans serveur dédié).

Pourtant, le projet prévoit une architecture distribuée en microservices conteneurisés sous **Docker Compose** (un outil permettant de définir et d'orchestrer plusieurs conteneurs isolés sur une même machine via un fichier YAML unique) pour le MVP (Sprints 1 à 4), complétée en Bonus (Sprint 5) par **Kubernetes** (un orchestrateur industriel qui automatise le déploiement, la mise à l'échelle et la résilience de conteneurs sur un cluster), **Prometheus** (collecteur de métriques système et applicatives) et **Grafana** (visualiseur de tableaux de bord de supervision).

**Question posée** : Pourquoi concevoir une architecture multi-conteneurs avec base de données serveur (`PostgreSQL`), serveur de suivi d'expériences (`MLflow`), API REST (`FastAPI`) et interface découplée (`Streamlit`) alors que les données pèsent moins de 150 Mo ? Et comment éviter que cette architecture ne sature la machine de développement d'Amine (16 Go de RAM sous Windows) ?

---

## 2. Options envisagées

### Option A — Architecture minimaliste (Monolithe Streamlit + DuckDB / Fichiers Parquet)
- **Description** : Une seule application Streamlit qui télécharge les CSV, les sauvegarde en fichiers Parquet locaux, entraîne les modèles au démarrage et affiche les graphiques directement.
- **Avantages** : Empreinte mémoire minuscule (< 400 Mo de RAM), développement initial très rapide, aucune administration de base de données.
- **Inconvénients** :
  - **Couplage fort** : L'interface graphique, la logique métier, le stockage et le Machine Learning sont mélangés dans le même code.
  - **Faible valeur démonstrative pour un stage Data / MIAGE** : Ne démontre ni la conception d'un entrepôt de données relationnel avec contraintes d'intégrité, ni l'exposition d'une API REST documentée, ni l'industrialisation MLOps, ni la sécurisation des accès par rôles.

### Option B — Big Data lourd (Apache Spark + Airflow + Kafka + Kubernetes dès le Sprint 1)
- **Description** : Déploiement complet d'un cluster Spark, d'un ordonnanceur Airflow (qui nécessite à lui seul un scheduler, un webserver, un worker Celery et Redis) et d'un cluster Kubernetes local dès le premier sprint.
- **Avantages** : Technologies très demandées sur les offres d'emploi Data Engineer.
- **Inconvénients** :
  - **Violation de la contrainte matérielle (< 4 Go de RAM)** : Airflow + Spark + PostgreSQL + MLflow dépassent facilement 8 à 10 Go de RAM sous WSL2 (le sous-système Linux de Windows utilisé par Docker Desktop).
  - **Disproportion caricaturale** : Lancer une JVM (*Java Virtual Machine*, la machine virtuelle lourde qui exécute Spark) pour filtrer 333 000 lignes ajoute 30 secondes de temps de démarrage pour un calcul qui prend 0,2 seconde en Python/SQL.
  - **Risque d'échec projet** : Complexité d'infrastructure étouffant le travail sur la qualité des données et la rigueur statistique des modèles.

### Option C — Architecture modulaire maîtrisée en 2 paliers : Cœur MVP sous Docker Compose (< 3,5 Go RAM) + Bonus DevOps au Sprint 5 (Retenue)
- **Description** :
  1. **Palier 1 — Cœur MVP (Sprints 1 à 4, priorités `Must` et `Should`)** : 4 services permanents légers sous Docker Compose (`postgres:16-alpine`, `mlflow-slim`, `fastapi-slim`, `streamlit-slim`) + 1 conteneur de tâche ponctuel (`job-runner` pour l'ETL et l'entraînement).
  2. **Palier 2 — Extension Bonus (Sprint 5, priorité `Could`)** : Ajout optionnel via un profil Docker Compose dédié (`--profile observability` / `--profile bi`) de `Prometheus`, `Grafana`, `Metabase`, et manifestes `Kubernetes` (K3s/Kind) uniquement après validation complète du MVP.

---

## 3. Décision et Justification

Nous retenons l'**Option C**. Nous assumons explicitement et honnêtement que cette architecture est **volontairement sur-dimensionnée par rapport au volume brut des données (~333k lignes)**, mais **strictement dimensionnée par rapport aux objectifs pédagogiques et professionnels d'un élève-ingénieur Génie Logiciel + Master MIAGE** :

1. **Séparation des responsabilités (*Separation of Concerns*, principe d'ingénierie logicielle consistant à isoler le stockage, la logique métier et l'affichage dans des briques indépendantes)** :
   - L'entrepôt `PostgreSQL` garantit le typage strict, les clés étrangères et l'idempotence via `ON CONFLICT DO UPDATE`.
   - L'API `FastAPI` centralise les règles métier, la validation de schémas (`Pydantic`), la limitation de débit (*rate limiting*) et n'accède à la base qu'avec un compte SQL en lecture seule (`agriprix_readonly`).
   - Le dashboard `Streamlit` est un pur client HTTP qui consomme l'API, prouvant que l'architecture peut servir simultanément une application web, un notebook d'analyste ou un système tiers.
2. **Respect strict du budget matériel (< 4 Go de RAM)** :
   - Chaque service du MVP utilise une image `alpine` ou `python:3.11-slim` et possède une directive `mem_limit` et `cpus` dans `docker-compose.yml` :
     - `db` (`postgres:16-alpine`) : `512m`
     - `mlflow` (`python:3.11-slim`) : `512m`
     - `api` (`python:3.11-slim`) : `512m`
     - `dashboard` (`python:3.11-slim`) : `512m`
     - `job-runner` (éphémère, actif uniquement pendant `make etl` ou `make train`) : `1280m`
     - **Total maximal simultané du MVP** : **3 328 Mo (~3,25 Go)**, laissant plus de 12 Go libres au système hôte Windows.
3. **Protection du calendrier (MVP d'abord, DevOps avancé ensuite)** :
   - En isolant `Prometheus`, `Grafana`, `Metabase` et `Kubernetes` dans le **Sprint 5 (Bonus `Could Have`)**, le projet reste 100 % fonctionnel, publiable et démontrable dès la fin du Sprint 4 même si le temps disponible d'Amine impose d'arrêter avant le Sprint 5.

---

## 4. Conséquences

### Positives
- **Crédibilité en entretien technique** : Savoir dire à un recruteur *« Pour 333 000 lignes, DuckDB aurait suffi en production pure, mais j'ai conçu une architecture 3-tiers conteneurisée PostgreSQL + FastAPI + Streamlit avec MLflow pour démontrer ma maîtrise des patrons d'architecture logicielle et MLOps tout en plafonnant la RAM à 3,25 Go »* montre une maturité d'architecte rare chez un junior.
- **Démarrage en une commande** : `docker compose up -d` lance l'intégralité du MVP sans aucune dépendance sur la machine hôte.

### Négatives et Mitigations
- **Surcharge réseau interne** : Le passage par HTTP entre Streamlit et FastAPI ajoute ~5 à 15 ms de latence locale par rapport à une requête SQL directe. *Mitigation* : Utilisation du cache mémoire de Streamlit (`@st.cache_data(ttl=3600)`) pour éviter de ré-interroger l'API à chaque clic utilisateur.
- **Performance d'écriture disque sous Windows (WSL2)** : Les montages de dossiers Windows (*bind mounts*) vers un moteur PostgreSQL Linux sous Docker Desktop sont lents et peuvent corrompre les verrous de fichiers. *Mitigation* : Utilisation obligatoire de **volumes nommés Docker** (`pgdata:/var/lib/postgresql/data` et `mlflow_artifacts:/mlflow`) gérés nativement dans le système de fichiers Linux de WSL2.
