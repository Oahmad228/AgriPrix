# ADR-005 : Interface principale Streamlit découplée via FastAPI et BI Metabase en option (Sprint 5)

- **Statut** : Accepté
- **Date** : 2026-04-19
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `EF-14`, `EF-15`, `EF-16`, `ENF-01`, `US-14`, `US-15`, `US-20`

---

## 1. Contexte et Problème

Le projet AgriPrix Observatory doit fournir une interface visuelle permettant aux deux personas (Kofi l'analyste humanitaire et Yasmine la chargée d'études économiques) de :
1. Visualiser la carte interactive des marchés et des alertes d'anomalies.
2. Explorer les séries historiques avec affichage du `pricetype = 'Retail'` par défaut, superposition des prévisions à $t+1, t+3, t+6$ mois et de leurs intervalles conformes à 80 %, ou consultation des séries non éligibles avec bandeau explicatif.
3. Télécharger les données filtrées en CSV.

Par ailleurs, dans un cursus **MIAGE**, la maîtrise d'un outil de **Business Intelligence (BI, informatique décisionnelle permettant de créer des tableaux de bord SQL sans coder d'interface web)** comme **Metabase** ou **Apache Superset** est un atout apprécié, mais ces outils sont gourmands en mémoire vive.

---

## 2. Options envisagées

### Option A — Uniquement un outil BI (Metabase ou Apache Superset) branché sur PostgreSQL
- **Avantages** : Zéro code frontend à écrire, filtres SQL natifs.
- **Inconvénients** :
  - **Consommation RAM élevée** : Metabase tourne sur une machine virtuelle Java (JVM) qui réclame `768 Mo` à `1 Go` de RAM au repos ; Superset nécessite Python + Redis + Celery.
  - **Limitation sur les graphiques ML avancés** : Tracer proprement une courbe historique avec un cône d'incertitude ombré ($[q_{10}, q_{90}]$) et des marqueurs d'anomalies conditionnels est difficile et peu ergonomique dans Metabase standard.
  - **Court-circuite l'API REST** : Metabase interroge directement PostgreSQL en SQL et ne démontre donc pas l'utilisation de l'API `FastAPI`.

### Option B — Frontend JavaScript séparé (React / Vue.js) + FastAPI
- **Avantages** : Liberté graphique totale.
- **Inconvénients** : Ajoute un écosystème Node.js/TypeScript lourd à maintenir alors que l'objectif de stage d'Amine est orienté **Data Science / Data Analysis / IA** (écosystème Python).

### Option C — Dashboard analytique `Streamlit + Plotly` consommant exclusivement `FastAPI` (Cœur MVP, Sprint 4) + `Metabase` en profil optionnel (Bonus Sprint 5) (Retenue)
- **Description** :
  - **Cœur MVP (Sprint 4)** : Une application Python **Streamlit** (framework Python transformant des scripts de données en applications web interactives) couplée à **Plotly** (bibliothèque de graphiques interactifs avec zoom, survol et cônes d'incertitude) et **PyDeck / Folium** (cartographie).
  - **Règle d'architecture stricte** : Le conteneur `dashboard` (Streamlit) **ne possède aucun pilote SQL (`psycopg2` / `SQLAlchemy`) ni les identifiants de la base PostgreSQL**. Il communique **exclusivement via des requêtes HTTP REST** vers le conteneur `api` (`FastAPI`).
  - **Extension Bonus (Sprint 5, priorité `Could Have`, `US-20`)** : Un service `metabase/metabase:latest` défini dans `docker-compose.yml` sous le profil optionnel `profiles: ["bi"]`, branché sur PostgreSQL via l'utilisateur `agriprix_api_readonly`.

---

## 3. Décision et Justification

Nous retenons l'**Option C** :
1. **Légèreté mémoire pour le MVP** : `Streamlit` tourne dans une image `python:3.11-slim` et consomme moins de `200 Mo` de RAM (plafonné à `512m`).
2. **Démonstration de l'architecture 3-tiers** : En interdisant à Streamlit d'accéder directement à PostgreSQL, nous prouvons que `FastAPI` est le véritable point d'entrée unique de la logique métier.
3. **Rendu scientifique supérieur** : `Plotly` permet de dessiner nativement le ruban d'incertitude (`fill='tonexty'`) des intervalles conformes à 80 %, les seuils d'anomalies $Z$-score et les info-bulles méthodologiques expliquant pourquoi une série annuelle ou `aggregate` est en consultation seule.

---

## 4. Conséquences

- Le MVP démarre rapidement avec `docker compose up` sans charger de JVM.
- Si Amine souhaite montrer une brique BI décisionnelle lors d'une démonstration MIAGE (et si le Sprint 5 est réalisé), une simple commande `docker compose --profile bi up -d metabase` lance Metabase avec des tableaux de bord pré-configurés.
