# Phase 1 — Cahier des Charges : AgriPrix Observatory (Version révisée)

> **Note pédagogique (Lexique intégré)** : Chaque fois qu'un sigle ou un terme technique apparaît pour la première fois dans ce document, il est expliqué en une phrase simple entre parenthèses, et repris dans le **Glossaire** final (Section 10).

---

## 1. Introduction et Vision Produit (Approche AMOA / MIAGE)

### 1.1 Objectif du document
Ce **Cahier des Charges** (*document contractuel qui décrit précisément ce que le logiciel doit faire, pour qui, et sous quelles contraintes de qualité avant de commencer à programmer*) traduit les conclusions du cadrage et de l'audit des données en spécifications vérifiables. Il fait le pont entre :
- La **MOA** (*Maîtrise d'Ouvrage*, l'entité qui porte le besoin métier et les objectifs d'usage — représentée par Amine en tant qu'**AMOA** — *Assistance à Maîtrise d'Ouvrage*), et
- La **MOE** (*Maîtrise d'Œuvre*, l'équipe d'ingénierie logicielle, Data et DevOps chargée de concevoir, coder, tester et déployer la plateforme).

### 1.2 Vision du produit
**AgriPrix Observatory** est un **SID** (*Système d'Information Décisionnel*, plateforme informatique qui collecte, nettoie et modélise des données pour éclairer la prise de décision humaine) open-source et déployable en ligne. Il permet aux acteurs de la sécurité alimentaire et des filières agricoles en **Afrique de l'Ouest (zone UEMOA)** et au **Maroc** :
1. De **suivre l'historique réel** des prix alimentaires de détail (`Retail` par défaut) et de gros (`Wholesale`) en Afrique de l'Ouest (`XOF`), ainsi que l'indice mensuel des prix alimentaires (`base 2015 = 100`) et les prix producteurs annuels (`MAD/tonne`) au Maroc, en isolant strictement dans la base de données le **grain géographique** (`MARKET` vs `NATIONAL`), la **fréquence** (`MONTHLY` vs `ANNUAL`) et le **type de valeur** (`PRICE` vs `INDEX`).
2. D'**être alertés automatiquement en langage clair** lorsqu'une série mensuelle subit un choc anormal (**anomalie**), grâce à un détecteur validé sur des crises historiques documentées (2007–2008 et 2022).
3. D'**anticiper l'évolution à 1, 3 et 6 mois** des **746 séries mensuelles éligibles** (745 séries de prix de détail `actual` en Afrique de l'Ouest + la série mensuelle d'indice IPC alimentaire au Maroc) avec un **intervalle d'incertitude** (*fourchette entre une borne basse et une borne haute calculée à partir des erreurs passées réelles*) et une mesure honnête de la fiabilité par horizon.

---

## 2. Analyse des Besoins Utilisateurs et Indicateurs de Valeur (KPI)

### 2.1 Cartographie des besoins par profil d'utilisateur

| Profil utilisateur | Décision métier à prendre | Besoin fonctionnel essentiel | Besoin d'ergonomie et d'explicabilité |
| :--- | :--- | :--- | :--- |
| **ONG Humanitaires** *(Persona : Fatou)* | Allouer les budgets d'aide alimentaire ou de transferts monétaires vers les zones en surchauffe. | Voir par défaut les prix de détail (`Retail`) en `XOF`, repérer les marchés en alerte et connaître la fourchette haute prévue à 1, 3 et 6 mois. | **Zéro jargon** : alertes colorées (Vert / Orange / Rouge), phrases explicatives simples, lecture rapide. |
| **Décideurs Publics** *(Ministères, Offices céréaliers)* | Réguler les stocks nationaux et suivre l'inflation alimentaire. | Suivre et prévoir à 1, 3 et 6 mois l'**IPC alimentaire mensuel au Maroc (`base 2015=100`)**, consulter les prix producteurs annuels en `MAD/tonne`, et suivre les marchés de l'UEMOA en `XOF`. | Séparation visuelle et méthodologique explicite entre un indice mensuel, un prix annuel et un prix mensuel de marché. |
| **Coopératives Agricoles & Commerçants** *(Persona : Moussa)* | Choisir quand vendre ou stocker les récoltes (mil, maïs, sorgho, riz, niébé). | Comparer les prix de détail (`Retail` en `KG`) et, lorsqu'ils existent, de gros (`Wholesale` en `100 KG`) entre marchés régionaux en `XOF`. | Interface web légère, rapide, lisible sans compétence statistique. |
| **Acheteurs Institutionnels** *(Cantines scolaires, centrales d'achat)* | Négocier des contrats d'approvisionnement plurimensuels sans dépasser le budget annuel. | Utiliser la borne supérieure de l'intervalle d'incertitude à 3 et 6 mois comme **prix plafond de sécurité budgétaire**. | Affichage clair du taux de couverture historique de l'intervalle (**PICP**) sur ce produit. |
| **Analystes Data & Économistes** *(Persona : Youssef)* | Auditer les modèles statistiques/ML, vérifier l'absence de biais et croiser les données. | Vérifier que seules les observations `priceflag = 'actual'` et continues sur $\ge 60\text{ mois}$ sont modélisées, consulter les métriques par horizon (`1, 3, 6 mois`), et interroger l'API REST. | Transparence totale sur le découpage chronologique, le calcul conforme des intervalles et la validation sur les crises de 2008 et 2022. |

### 2.2 Indicateurs de valeur métier et d'impact (Objectifs Cibles du Projet)

> **Règle d'honnêteté scientifique** : Tant que les sprints correspondants ne sont pas exécutés, les seuils ci-dessous constituent des **objectifs cibles de conception** qui seront confrontés aux mesures réelles.

| Code KPI | Nom de l'indicateur | Définition en langage simple | Objectif cible (à mesurer en Sprint 2, 3 et 4) |
| :--- | :--- | :--- | :--- |
| **KPI-M1** | **Temps de diagnostic d'un choc de prix** | Temps nécessaire à un utilisateur non-technicien pour identifier les marchés en anomalie critique dans un pays donné sur le dashboard. | **Objectif cible : $\le 60\text{ secondes}$** lors du parcours de démo de 2 minutes. |
| **KPI-M2** | **Gain de précision prédictive (*Forecast Skill Score*)** | Réduction relative de l'erreur moyenne (`MAE` / `RMSE`) du meilleur modèle par rapport à la **baseline saisonnière** (*modèle de référence prédisant le prix du même mois l'an dernier ou le dernier prix connu*). | **Objectif cible : $> 0\text{ \%}$ mesuré par horizon** (et bascule transparente sur la baseline si celle-ci est meilleure à H+6). |
| **KPI-M3** | **Couverture empirique des intervalles (*PICP*)** | **PICP** (*Prediction Interval Coverage Probability*, pourcentage des vrais prix du jeu de test qui tombent effectivement entre la borne basse et la borne haute prévues). | **Objectif cible : écart $\le 10\text{ points}$** par rapport au niveau de confiance nominal de 80 % (soit entre 70 % et 90 % sur le jeu de test). |
| **KPI-M4** | **Validation du détecteur d'anomalies sur crises connues** | Capacité du détecteur à repérer les grands chocs historiques documentés (crises 2007–2008 et 2022) sans générer un excès de fausses alertes en période calme. | **Objectif cible : $\ge 80\text{ \%}$ des chocs de référence détectés** et **$< 5\text{ \%}$ d'alertes en période calme** (2015–2018). |
| **KPI-M5** | **Taux de conformité qualité de l'entrepôt** | Pourcentage des lignes en base PostgreSQL respectant 100 % des contraintes d'intégrité (valeurs $> 0$, grain, fréquence, type de valeur, unicité de la clé de série). | **Objectif cible : 100 % des lignes chargées en base**. |

---

## 3. Objectifs SMART du Projet

1. **SMART-01 (Ingestion & Entrepôt Hybride Multi-Fréquences — Sprint 1)** : Construire un pipeline **ETL** (*Extract, Transform, Load*) capable d'ingérer les **324 040 lignes d'observations** (**6 312 séries**) des 5 pays d'Afrique de l'Ouest (`SEN`, `MLI`, `BFA`, `NER`, `CIV` : `granularity_level = 'MARKET'`, `frequency = 'MONTHLY'`, `value_type = 'PRICE'`, devise `XOF`) ainsi que les données du Maroc (`MAR` : `granularity_level = 'NATIONAL'`) en distinguant strictement les **3 séries mensuelles d'IPC** (**942 observations mensuelles dépivotées**, `frequency = 'MONTHLY'`, `value_type = 'INDEX'` ou `'INFLATION_RATE'`) et les **367 séries annuelles de prix producteurs** (**8 942 observations annuelles dépivotées**, `frequency = 'ANNUAL'`, `value_type = 'PRICE'` en `MAD/tonne` ou `'INDEX'`, sans aucun mois fictif inventé), dans un entrepôt en étoile **PostgreSQL** validé par 100 % des tests de qualité.
2. **SMART-02 (Éligibilité Stricte, Prévisions à 1/3/6 Mois & Prédiction Conforme — Sprint 2)** : Filtrer les séries éligibles au Machine Learning selon la règle stricte (`frequency = 'MONTHLY'`, `priceflag = 'actual'` uniquement, activité récente $\ge 2024$, et **fenêtre continue d'au moins 60 mois avec $\le 3$ mois manquants consécutifs**, soit **745 séries `Retail` en UEMOA + 1 série mensuelle d'IPC alimentaire au Maroc = 746 séries**), comparer une baseline statistique et des modèles globaux par `(Pays, Produit, Horizon)` aux horizons **1, 3 et 6 mois** sans fuite temporelle, calculer les **intervalles d'incertitude par prédiction conforme** (en mesurant le **PICP** sur le jeu de test), et enregistrer les **métriques agrégées dans MLflow** (avec le détail par série en table PostgreSQL).
3. **SMART-03 (Détection d'Anomalies Validée sur Crises Historiques — Sprint 3)** : Développer un détecteur d'anomalies saisonnier sur les séries mensuelles, le valider objectivement sur un jeu de chocs historiques documentés (**crise alimentaire mondiale de 2007–2008** et **choc inflationniste de 2022**) en mesurant le taux de détection et le taux de fausses alertes en période stable, et générer une explication en français simple pour chaque anomalie.
4. **SMART-04 (API REST Sécurisée sous FastAPI — Sprint 3)** : Exposer les séries historiques (mensuelles et annuelles), les prévisions à 1/3/6 mois (avec bornes d'incertitude), les anomalies et les métriques via une **API REST FastAPI** documentée en **OpenAPI**, utilisant un **utilisateur PostgreSQL en lecture seule (`agriprix_readonly`)**, protégée par une **limitation de débit (*Rate Limiting*)** et une politique **CORS** (*Cross-Origin Resource Sharing*, contrôle des domaines web autorisés à interroger l'API) restreinte, avec un objectif cible de temps de réponse **$< 300\text{ ms}$ au 95e centile (p95)**.
5. **SMART-05 (Dashboard Produit Streamlit, Automatisation Mensuelle & Hébergement MVP — Sprint 4)** : Livrer un tableau de bord **Streamlit** connecté exclusivement à l'API FastAPI (affichant par défaut les prix de détail `Retail`, avec **Vue Décideur** sans jargon et **Vue Analyste** détaillée), mettre en place une **tâche d'actualisation mensuelle automatisée** (ETL + réentraînement ML), préparer le déploiement de la démo publique sous **Docker Compose** derrière un **Reverse Proxy HTTPS**, et maintenir un objectif cible de **couverture de tests automatisés $\ge 70\text{ \%}$** dans **GitHub Actions**.
6. **SMART-06 (Extensions Bonus Post-MVP : Observabilité, Kubernetes & BI — Sprint 5)** : Une fois le MVP (Sprints 1 à 4) terminé et stable, enrichir la plateforme au Sprint 5 avec les briques bonus de démonstration DevOps et BI : supervision **Prometheus + Grafana**, déploiement sur **Kubernetes local (`k3s` ou `kind`)** incluant un `CronJob` mensuel, conteneur **Metabase** branché en lecture seule sur PostgreSQL, et activation optionnelle de la conversion de devises sous *Feature Flag*.

---

## 4. Périmètre du Projet : Cœur MVP (Sprints 1–4), Bonus (Sprint 5) et Exclusions

| Catégorie | Éléments du périmètre | Statut & Sprint |
| :--- | :--- | :---: |
| **CŒUR MVP (Indispensable — Sprints 1 à 4)** | • **Afrique de l'Ouest (`SEN`, `MLI`, `BFA`, `NER`, `CIV`)** : 324 040 lignes (`MARKET`, `MONTHLY`, `PRICE`, `XOF`), affichage par défaut `Retail`.<br>• **Maroc (`MAR`)** : séparation stricte entre l'**IPC alimentaire mensuel** (`NATIONAL`, `MONTHLY`, `INDEX`, `2015=100`, 318 mois $\rightarrow$ **seule série marocaine prévue à 1/3/6 mois**) et les **prix producteurs agricoles annuels** (`NATIONAL`, `ANNUAL`, `PRICE`, `MAD/tonne`, 367 séries / 8 942 obs. $\rightarrow$ **consultation historique uniquement, sans mois inventé**).<br>• **Éligibilité ML stricte** : `priceflag = 'actual'` uniquement (exclusion des `aggregate` ivoiriens et de toute estimation) + fenêtre récente continue $\ge 60\text{ mois}$ avec $\le 3$ mois manquants consécutifs (**746 séries éligibles**).<br>• **Prévisions à 1, 3 et 6 mois** (modèles globaux par produit/pays + baseline) avec **intervalles d'incertitude par prédiction conforme** (`PICP` mesuré) et runs **MLflow agrégés**.<br>• **Détection d'anomalies** validée sur les crises de 2007–2008 et 2022 + explications en français simple.<br>• **API FastAPI sécurisée** (DB lecture seule, *Rate Limiting*, *CORS* restreint) + **Dashboard Streamlit** (Décideur & Analyste).<br>• **Automatisation mensuelle** (planificateur ETL + réentraînement).<br>• **Socle Docker Compose** (volumes nommés compatibles Windows), **CI GitHub Actions** (objectif $\ge 70\text{ \%}$ tests) et **Reverse Proxy HTTPS** pour l'hébergement public. | **Inclus Cœur MVP (Sprints 1 à 4 — *Must / Should*)** |
| **BONUS POST-MVP (Extensions DevOps & BI — Sprint 5)** | • **Monitoring Prometheus + Grafana** des métriques de l'API.<br>• **Orchestration Kubernetes locale (`k3s` ou `kind`)** avec manifestes / Helm et `CronJob` mensuel.<br>• **BI interne Metabase** branchée en lecture seule sur PostgreSQL.<br>• **Conversion active de devises (`EUR`, `USD`)** à la couche d'affichage sous *Feature Flag* (`ENABLE_CURRENCY_CONVERSION`). | **Bonus Post-MVP (Sprint 5 — *Could Have*)** |
| **EXCLUS (*Won't Have*)** | • **Prévision à 1, 3 ou 6 mois sur les séries annuelles marocaines** ou invention de dates mensuelles fictives (`YYYY-MM-15`) pour des données annuelles.<br>• **Entraînement ML sur des données `priceflag != 'actual'`** (`aggregate`, `estimate`, `forecast`).<br>• **Un run MLflow par série individuelle** (qui polluerait le serveur avec des milliers de runs).<br>• **Algérie** ; mélange des grains `MARKET`/`NATIONAL` ou des types `PRICE`/`INDEX` ; modification des devises locales en base ; installation hors Docker. | **Exclus (*Won't*)** |

---

## 5. Exigences Fonctionnelles (EF)

### 5.1 Domaine Ingestion, Typage et Entrepôt de Données (Sprint 1)

| ID | Exigence Fonctionnelle | Persona cible | Priorité |
| :--- | :--- | :---: | :---: |
| **EF-01** | **Collecte automatisée et polie Afrique de l'Ouest (WFP HDX)** : Télécharger avec pause de courtoisie (pour éviter le défi *AWS WAF*) et mettre en cache les fichiers CSV de prix et de marchés pour `SEN`, `MLI`, `BFA`, `NER` et `CIV`, avec repli possible sur l'API `hapi.humdata.org`. | Youssef (Analyste) | **Must** |
| **EF-02** | **Collecte et dépivotage différencié Maroc (FAOSTAT S3)** : Extraire du fichier `ConsumerPriceIndices_E_Africa_NOFLAG.csv` les séries mensuelles marocaines en les datant au mois (`frequency = 'MONTHLY'`, `value_type = 'INDEX'` pour `23013`/`23012` et `'INFLATION_RATE'` pour `23014`), et extraire de `Prices_E_Africa_NOFLAG.csv` les séries annuelles en les rattachant uniquement à leur année `reference_year` (`frequency = 'ANNUAL'`, `value_type = 'PRICE'` avec `unit = 'MAD/tonne'` pour `5530`, sans jamais inventer de mois fictif). | Youssef (Analyste) | **Must** |
| **EF-03** | **Définition stricte de la clé de série et filtrage `priceflag`** : Identifier chaque série par la clé `(country_iso3, market_id, commodity_id, pricetype, unit, currency_code, frequency, value_type)` et conserver la valeur exacte de `priceflag` (`'actual'` vs `'aggregate'`). Toute observation où `priceflag != 'actual'` est marquée non éligible à l'entraînement ML. | Tous | **Must** |
| **EF-04** | **Isolation stricte du grain, de la fréquence et du type de valeur** : Chaque enregistrement de l'entrepôt doit comporter les colonnes non nulles `granularity_level` (`'MARKET'` \| `'NATIONAL'`), `frequency` (`'MONTHLY'` \| `'ANNUAL'`) et `value_type` (`'PRICE'` \| `'INDEX'` \| `'INFLATION_RATE'`), interdisant toute agrégation croisée. | Youssef (Analyste) | **Must** |
| **EF-05** | **Respect de la devise et de l'unité d'origine** : Les prix (`value_type = 'PRICE'`) sont stockés en `XOF` (Afrique de l'Ouest, avec leur unité `KG`, `100 KG` ou `L`) ou en `MAD` (`MAD/tonne` pour les prix producteurs annuels marocains), tandis que l'IPC alimentaire mensuel marocain (`value_type = 'INDEX'`) est stocké avec `unit = 'Index (2015=100)'` et `currency_code = NULL` (jamais présenté comme un prix en `MAD`). | Tous | **Must** |
| **EF-06** | **Table dédiée aux taux de change mensuels** : Inclure dans le schéma de l'entrepôt une table séparée et datée au mois (`dim_exchange_rate`) pour préparer l'option post-MVP de conversion des prix (`value_type = 'PRICE'`) sans jamais modifier la table de faits. | Youssef (Analyste) | **Should** (Schéma) / **Could** (Activation) |

### 5.2 Domaine Science des Données : Éligibilité, Prévisions, Conformal Prediction et Anomalies (Sprints 2 & 3)

| ID | Exigence Fonctionnelle | Persona cible | Priorité |
| :--- | :--- | :---: | :---: |
| **EF-07** | **Règle stricte d'éligibilité au Machine Learning (`is_ml_eligible`)** : Marquer `is_ml_eligible = TRUE` uniquement pour les séries vérifiant simultanément : (1) `frequency = 'MONTHLY'`, (2) `priceflag = 'actual'`, (3) produit du panier de sécurité alimentaire ou IPC alimentaire Maroc (`23013`), (4) dernière observation $\ge \text{2024-01-15}$, et (5) **fenêtre continue récente d'au moins 60 mois observés avec au maximum 3 mois manquants consécutifs (`max_consecutive_missing <= 3`)** (soit 745 séries `Retail` UEMOA + 1 série IPC Maroc = 746 séries). | Youssef (Analyste) | **Must** |
| **EF-08** | **Validation chronologique sans fuite (*Walk-Forward*)** : Découper chaque série éligible de manière strictement chronologique (initialisation `lag_12` sur 12 mois + entraînement $\ge 24\text{ mois}$ + validation chronologique $12\text{ mois}$ + test hors-échantillon $12\text{ mois}$), en interpolant linéairement les trous courts ($\le 3\text{ mois}$) uniquement à l'intérieur du passé connu. | Youssef (Analyste) | **Must** |
| **EF-09** | **Stratégie d'entraînement scalable et suivi MLflow agrégé** : Comparer une **Baseline statistique vectorisée** (*Seasonal Naive* / *Drift*) et des **Modèles ML globaux par `(Pays, Produit, Horizon)`** (*Ridge* et *LightGBM / HistGradientBoosting*, plus *Holt-Winters / ETS* sur séries de référence). Enregistrer dans **MLflow uniquement un run par expérience globale `(model_family, horizon_months, granularity_level)` avec les métriques agrégées**, et stocker les métriques détaillées de chacune des 746 séries dans la table PostgreSQL `fact_model_metrics_by_series`. | Youssef (Analyste) | **Must** |
| **EF-10** | **Prévisions à 1, 3 et 6 mois et Intervalles par Prédiction Conforme** : Pour chaque série éligible (`is_ml_eligible = TRUE`) et chaque horizon $h \in \{1, 3, 6\}$, calculer la prévision centrale et les bornes d'incertitude (`lower_bound`, `upper_bound` à 80 %) par **Prédiction Conforme Temporelle (*Split Conformal Prediction* sur les quantiles des résidus de validation)**, et mesurer le taux de couverture réel (**PICP**) sur le jeu de test. | Fatou (ONG) & Moussa (Coop.) | **Must** |
| **EF-11** | **Détection d'anomalies validée sur crises historiques** : Calculer sur les séries mensuelles le score d'anomalie saisonnier (écart relatif et Z-score robuste sur résidus saisonniers), qualifier chaque choc (`NORMAL`, `WARNING`, `CRITICAL`) avec une phrase en français simple, et valider le détecteur sur un jeu de référence de chocs connus (**crises 2007–2008 et 2022**) en mesurant le taux de détection et le taux de fausses alertes en période calme. | Fatou (ONG) & Moussa (Coop.) | **Must** |

### 5.3 Domaine Exposition, Automatisation Mensuelle et Bonus Post-MVP (Sprints 3, 4 & 5)

| ID | Exigence Fonctionnelle | Persona cible | Priorité |
| :--- | :--- | :---: | :---: |
| **EF-12** | **API REST FastAPI complète et typée** : Exposer les routes de référentiel, d'historique (filtrables par `granularity_level`, `frequency`, `value_type` et `pricetype`, avec `'Retail'` par défaut), de prévisions à 1/3/6 mois (uniquement pour les séries mensuelles éligibles), d'anomalies et de métriques ML, ainsi que `/health`. | Tous | **Must** |
| **EF-13** | **Découplage strict Dashboard $\rightarrow$ API** : Le conteneur **Streamlit** ne doit posséder aucun pilote ni accès SQL direct à PostgreSQL ; il interroge exclusivement l'API **FastAPI**. | Équipe / Architecture | **Must** |
| **EF-14** | **Vue « Décideur / ONG / Coopérative » dans Streamlit (Retail par défaut)** : Afficher par défaut les séries `pricetype = 'Retail'` en Afrique de l'Ouest (`XOF/KG`) et l'IPC alimentaire mensuel au Maroc (`Index 2015=100`), avec bandeau d'alertes en français simple, graphique de prévision à 1, 3 et 6 mois entouré de son intervalle d'incertitude, et encadré d'aide à la décision. | Fatou (ONG) & Moussa (Coop.) | **Must** |
| **EF-15** | **Vue « Analyste / Économiste » dans Streamlit** : Afficher la comparaison des modèles par horizon ($H+1, H+3, H+6$), le **PICP** mesuré, le bilan de validation du détecteur d'anomalies sur les crises 2008/2022, la consultation des séries annuelles marocaines (`MAD/tonne`) et des séries ivoiriennes (`aggregate`), ainsi que les licences Open Data. | Youssef (Analyste) | **Must** |
| **EF-16** | **Mise à jour mensuelle automatisée (ETL + Réentraînement)** : Intégrer un mécanisme d'exécution planifiée mensuelle qui relance automatiquement le pipeline ETL, les tests de qualité et le réentraînement des modèles lorsque de nouvelles données mensuelles sont publiées sur HDX / FAOSTAT. | Équipe / Exploitation | **Must** (Planificateur Compose S4) / **Could** (`CronJob` K8s S5) |
| **EF-17** | **Conversion de devises optionnelle sous Feature Flag (Bonus Sprint 5)** : Lorsque `ENABLE_CURRENCY_CONVERSION=true`, permettre la conversion à la volée des séries de type `value_type = 'PRICE'` vers `EUR` ou `USD` dans la couche API à partir de `dim_exchange_rate` (les séries de type `INDEX` ne sont évidemment jamais converties en devise). | Youssef (Analyste) | **Could** (Sprint 5) |
| **EF-18** | **BI Interne Metabase branchée en lecture seule sur PostgreSQL (Bonus Sprint 5)** : Conteneur optionnel permettant d'explorer le schéma en étoile via le compte SQL `agriprix_readonly`. | Youssef (Analyste) | **Could** (Sprint 5) |

---

## 6. Exigences Non Fonctionnelles (ENF)

### 6.1 Exécution Conteneurisée, Compatibilité Windows et Reproductibilité
- **ENF-01 (Tout dans Docker & Volumes nommés sous Windows)** : **100 % des composants** s'exécutent dans des conteneurs Docker sans aucune installation sur le Windows hôte. Pour éviter les problèmes de permissions NTFS et de lenteur d'entrée/sortie sous Windows/WSL2, les données de PostgreSQL doivent impérativement utiliser un **volume nommé Docker (`pgdata:/var/lib/postgresql/data`)** et non un dossier hôte monté (*bind mount*).
- **ENF-02 (Démarrage unifié et Makefile)** : Un seul `docker compose up -d` (ou `make up`) démarre toute la pile du MVP. Le `Makefile` expose au minimum : `make up`, `make down`, `make test`, `make lint`, `make etl`, `make train`.
- **ENF-03 (Reproductibilité et temps de calcul raisonnable)** : Grâce à la stratégie de modèles globaux par `(Pays, Produit, Horizon)`, l'exécution complète de `make train` sur les 746 séries éligibles doit se terminer en **moins de 3 minutes** sur l'ordinateur portable d'Amine, avec des **graines aléatoires fixées** (`random_seed = 42`).

### 6.2 Sécurité de la Démo Publique et Exploitation (Point 8)
- **ENF-04 (Moindre privilège PostgreSQL — Utilisateur Lecture Seule)** : Le script d'initialisation de PostgreSQL doit créer deux rôles distincts :
  1. `agriprix_writer` : utilisé uniquement par les tâches internes `etl` et `train` pour insérer et mettre à jour les tables.
  2. **`agriprix_readonly`** : disposant uniquement du droit `SELECT` sur les tables de l'entrepôt, utilisé obligatoirement par l'API publique **FastAPI** (et par **Metabase** en Sprint 5).
- **ENF-05 (Protection de l'API publique : Rate Limiting & CORS restreint)** :
  - L'API FastAPI doit intégrer un mécanisme de **limitation du débit (*Rate Limiting*)** (ex. maximum 60 requêtes par minute et par adresse IP) pour prévenir les abus ou le déni de service sur la démo en ligne.
  - La politique **CORS** (*Cross-Origin Resource Sharing*) de FastAPI doit être restreinte explicitement aux origines autorisées (l'URL du dashboard Streamlit configurée par variable d'environnement, jamais `*` en production).
  - L'API publique n'expose que des routes de consultation (`GET`) ; aucune route publique ne permet de modifier la base ou de déclencher un entraînement coûteux.
- **ENF-06 (Zéro secret exposé & HTTPS)** : Aucun mot de passe ni clé secrète dans Git (`.env.example` uniquement) ni dans les réponses de l'API ou les journaux d'erreurs. L'exposition publique passe par un **Reverse Proxy HTTPS**.

### 6.3 Qualité Logicielle, CI/CD et Extensions Bonus (Sprint 5)
- **ENF-07 (Performance API — Objectif cible)** : Temps de réponse **$< 300\text{ ms}$ au 95e centile (p95)** sur les routes de lecture de l'API FastAPI, vérifié par test de performance au Sprint 3.
- **ENF-08 (Couverture de tests automatisés — Objectif cible)** : Suite de tests unitaires et d'intégration sous `pytest` visant une **couverture minimale de 70 %**, vérifiée automatiquement dans **GitHub Actions** à chaque `push` et `Pull Request`.
- **ENF-09 (Bonus Sprint 5 — Observabilité & Kubernetes)** : Exposition `/metrics` pour **Prometheus + Grafana** et manifestes **Kubernetes (`k3s` ou `kind`)** avec `CronJob` mensuel, réalisés au Sprint 5 après validation complète du MVP.

---

## 7. Matrice des Risques et Plan de Mitigation

| ID | Description du risque | Catégorie | Probabilité | Impact | Mesure préventive et plan de secours (Mitigation) |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **RSK-01** | **Confusion entre grain (`MARKET`/`NATIONAL`), fréquence (`MONTHLY`/`ANNUAL`) ou type (`PRICE`/`INDEX`)** (ex. traiter l'IPC marocain `2015=100` comme un prix en `MAD` ou inventer des mois pour les prix producteurs annuels). | Données / Métier | Moyenne | **Critique** | **Prévention** : Colonnes obligatoires `granularity_level`, `frequency`, `value_type` et `unit` dans PostgreSQL + contraintes SQL `CHECK` + exclusion stricte des séries `ANNUAL` des prévisions à 1/3/6 mois. |
| **RSK-02** | **Entraînement sur des données déjà estimées/agrégées (`priceflag != 'actual'`) ou sur des séries trop courtes/trouées**. | Data Science | Élevée | **Critique** | **Prévention** : Filtrage strict `priceflag == 'actual'` (excluant les 4 054 lignes `aggregate` de Côte d'Ivoire du ML) + exigence de $\ge 60\text{ mois}$ récents continus avec $\le 3$ mois manquants consécutifs. |
| **RSK-03** | **Explosion du temps de calcul ou pollution de MLflow** si l'on créait un modèle et un run MLflow par série locale ($746 \times 3$ horizons). | Ingénierie ML | Élevée | Élevé | **Prévention** : Modèles globaux de panel par `(Pays, Produit, Horizon)` + 1 seul run MLflow par expérience globale (métriques agrégées) et sauvegarde du détail des 746 séries en table PostgreSQL. |
| **RSK-04** | **Blocage temporaire des téléchargements HDX par le pare-feu AWS WAF (`HTTP 202 Challenge`)** ou panne de l'API FAOSTAT (`HTTP 521`). | Infrastructure / Réseau | **Certaine** *(observée en Phase 0)* | Élevé | **Prévention** : Pause de courtoisie entre téléchargements + cache local persistant + bascule possible sur l'API `hapi.humdata.org` et archives S3 `bulks-faostat.fao.org` + jeu de test embarqué (*seed*) pour la CI. |
| **RSK-05** | **Problèmes de droits de fichiers PostgreSQL sous Windows** ou exposition non sécurisée lors de la mise en ligne de la démo publique. | DevOps / Sécurité | Moyenne | Élevé | **Prévention** : Volume nommé Docker (`pgdata`) obligatoire sous Windows + compte SQL `agriprix_readonly` pour l'API + *Rate Limiting* + *CORS* restreint + Reverse Proxy HTTPS. |
| **RSK-06** | **Dispersion sur les outils DevOps bonus (Kubernetes, Prometheus, Metabase)** avant d'avoir terminé le cœur fonctionnel. | Gestion de projet | Moyenne | Élevé | **Prévention** : Séparation stricte en 5 sprints : Sprints 1 à 4 dédiés à 100 % au **MVP sous Docker Compose**, et Sprint 5 dédié aux **Bonus Post-MVP**. |

---

## 8. Critères d'Acceptation Globaux du Projet (Séparés en MVP et Bonus)

### 8.1 Critères de validation du MVP (Sprints 1 à 4 — Obligatoires)
1. **Démarrage MVP en une commande** : `docker compose up -d` (ou `make up`) démarre les conteneurs du MVP (`postgres` sur volume nommé, `etl`, `api`, `mlflow`, `dashboard`) et tous passent leur *healthcheck*.
2. **Entrepôt intègre et fidèle aux sources** : `make etl` charge les 324 040 lignes UEMOA (`MARKET`, `MONTHLY`, `PRICE`, `XOF`) et les données du Maroc (`NATIONAL` : IPC mensuel `INDEX` et prix producteurs annuels `PRICE` en `MAD/tonne` sans mois inventé), avec 100 % des tests de qualité au vert.
3. **Éligibilité stricte et prévisions conformes** : `make train` entraîne en $< 3\text{ minutes}$ les modèles à 1, 3 et 6 mois sur les **746 séries mensuelles éligibles** (`priceflag = 'actual'`, $\ge 60\text{ mois}$ récents continus, `gap <= 3`), calcule les intervalles par **prédiction conforme** (`PICP` mesuré sur le jeu de test), et logue les métriques agrégées dans **MLflow** (détail par série en base).
4. **Détecteur d'anomalies validé** : Les chocs historiques de référence (2007–2008 et 2022) sont détectés avec mesure du taux de détection et du taux de fausses alertes en période calme, et expliqués en français simple.
5. **API FastAPI sécurisée et rapide** : L'API interroge PostgreSQL via le rôle `agriprix_readonly`, applique le *Rate Limiting* et le *CORS* restreint, expose `/docs` (OpenAPI) et répond en $< 300\text{ ms}$ (p95 cible).
6. **Dashboard Streamlit (Retail par défaut) & Automatisation mensuelle** : Streamlit consomme uniquement l'API, affiche par défaut les prix `Retail`, propose les vues Décideur et Analyste, et la tâche de mise à jour mensuelle automatisée ainsi que la configuration Reverse Proxy HTTPS sont opérationnelles.
7. **Qualité logicielle et véracité** : `make lint` et `make test` passent dans Docker et dans GitHub Actions (objectif $\ge 70\text{ \%}$ de couverture), et 100 % des chiffres du `README.md` proviennent d'exécutions réelles.

### 8.2 Critères de validation des Bonus Post-MVP (Sprint 5 — *Could Have*)
8. **Bonus DevOps & BI** : Conteneurs **Prometheus + Grafana** fonctionnels, manifestes **Kubernetes (`k3s`/`kind`)** avec `CronJob` mensuel validés, conteneur **Metabase** connecté en lecture seule, et option de conversion de devises sous *Feature Flag* testée.

---

## 9. Glossaire Technique et Métier Complété (A à Z)

- **ADR (*Architecture Decision Record*)** : Court document qui explique et justifie un choix technique structurant ainsi que ses compromis.
- **AWS WAF (*Web Application Firewall*)** : Pare-feu de sécurité d'Amazon qui protège un site web contre les téléchargements automatisés trop rapides en renvoyant un défi (`HTTP 202 Challenge`).
- **Backtesting (Validation chronologique)** : Évaluation d'un modèle en l'entraînant uniquement sur le passé jusqu'à une date $T$ et en mesurant son erreur sur les mois suivants $T+1, T+3, T+6$.
- **CORS (*Cross-Origin Resource Sharing*)** : Règle de sécurité du navigateur web qui empêche un site extérieur inconnu d'appeler notre API à la place de notre dashboard officiel.
- **CronJob (Tâche planifiée)** : Mécanisme (sous Linux, Docker ou Kubernetes) qui lance automatiquement un programme à une date fixe, par exemple le 20 de chaque mois à 3h du matin.
- **FES (*Food Expenditure Share*)** : Indicateur du Programme Alimentaire Mondial mesurant le pourcentage du budget total d'un ménage dépensé pour se nourrir.
- **Modèle Global de Panel (*Global Panel Model*)** : Modèle de Machine Learning unique entraîné simultanément sur les séries de tous les marchés d'un pays et d'un produit, ce qui est beaucoup plus rapide et robuste que d'entraîner un petit modèle isolé par marché.
- **Moindre privilège (*Least Privilege*)** : Règle de cybersécurité consistant à ne donner à un programme (comme notre API) que les droits strictement nécessaires (ici : lire la base de données avec `SELECT`, sans jamais pouvoir écrire ni supprimer).
- **PICP (*Prediction Interval Coverage Probability*)** : Pourcentage des valeurs réelles du jeu de test qui tombent effectivement à l'intérieur de la fourchette basse/haute annoncée par le modèle.
- **Prédiction Conforme (*Conformal Prediction*)** : Méthode mathématique sans hypothèse de courbe en cloche qui construit l'intervalle d'incertitude d'une prévision à partir des quantiles des vraies erreurs commises par le modèle lors de la validation passée.
- **Rate Limiting (Limitation de débit)** : Bride de sécurité qui limite le nombre de requêtes qu'une même adresse IP peut envoyer à l'API chaque minute pour éviter la saturation du serveur.
- **Volume nommé Docker (*Named Volume*)** : Espace de stockage géré directement par Docker à l'intérieur de son environnement Linux, évitant les bugs de permissions et les lenteurs des dossiers Windows classiques.
