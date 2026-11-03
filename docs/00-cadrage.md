# Phase 0 — Cadrage du Projet : AgriPrix Observatory (Version révisée)

> **Note pédagogique (Lexique intégré)** : Chaque fois qu'un sigle ou un terme technique apparaît pour la première fois dans ce document, il est suivi d'une explication simple en une phrase.

---

## 1. Reformulation du besoin et du problème résolu

### 1.1 Le contexte métier : l'instabilité des prix alimentaires en Afrique de l'Ouest et au Maroc
En Afrique de l'Ouest — au sein de l'**UEMOA** (*Union Économique et Monétaire Ouest-Africaine*, regroupant huit pays partageant la même monnaie, le franc CFA ou `XOF`) — ainsi qu'au Maroc (utilisant le dirham marocain, `MAD`), le poids de l'alimentation dans le budget des ménages — mesuré par le **PAM / WFP** (*Programme Alimentaire Mondial / World Food Programme*) via l'indicateur **FES** (*Food Expenditure Share*, part des dépenses totales d'un ménage consacrée à l'alimentation) — constitue un marqueur critique de vulnérabilité :
- **En Afrique de l'Ouest et au Sahel** :
  - **Seuils méthodologiques de vulnérabilité FES** : définis par **Lisa C. Smith & Ali Subandoro (2007)** dans *Measuring Food Security Using Household Expenditure Surveys* (IFPRI, série *Food Security in Practice*, Washington D.C., [doi:10.2499/0896297675](https://doi.org/10.2499/0896297675)) et repris par le **PAM (WFP VAM)** dans le guide officiel **CARI** (*Consolidated Approach for Reporting Indicators of Food Security*, éd. 2015 / révisé 2021, [wfp.org/publications/cari-guidelines](https://www.wfp.org/publications/consolidated-approach-reporting-indicators-food-security-cari-guidelines)) : `< 50 %` (faible vulnérabilité), `50–65 %` (moyenne), `65–75 %` (élevée) et `> 75 %` (très élevée / insécurité alimentaire sévère).
  - **Enquêtes nationales harmonisées UEMOA (EHCVM II 2021/2022, publiées en 2023–2024)** : au **Sénégal**, l'enquête **ANSD — EHCVM II (2021/2022)** ([ansd.sn](https://www.ansd.sn)) mesure une part alimentaire atteignant **50,0 % du budget chez les ménages pauvres** (et ~53 % dans les comparaisons internationales incluant les boissons non alcoolisées, contre ~35,5 % à > 40 % tous ménages confondus) ; au **Burkina Faso**, l'enquête **INSD — EHCVM II (2021/2022)** ([insd.bf](https://www.insd.bf)) relève une part alimentaire moyenne de **40 % à 49 %**, dépassant **60 % à 75 %** chez les ménages ruraux ou déplacés vulnérables.
- **Au Maroc** : selon le **HCP** (*Haut-Commissariat au Plan*, [hcp.ma](https://www.hcp.ma)) dans l'*Enquête Nationale sur la Consommation et les Dépenses des Ménages (ENCDM 2013/2014)* et les notes sur les conditions de vie des ménages (**2022–2023**), la part des dépenses alimentaires s'établit autour de **37 % à 40 % en moyenne nationale** (et dépasse **45 %** en milieu rural).

Une hausse brutale du prix du riz, du mil, du maïs ou du sorgho sur un marché local — comme le choc réel observé dans nos données où le **mil au détail sur le marché de Sankaryaré (Ouagadougou, Burkina Faso) est passé de `249 XOF/kg` en août 2021 à `468 XOF/kg` en août 2022 (+88,0 % en un an)**, ou lors de la crise de 2008 où le **riz importé à Tilène (Dakar, Sénégal) a bondi de `215 XOF/kg` à `437,50 XOF/kg` (+103,5 %)** — met immédiatement sous tension les budgets des **ONG** (*Organisations Non Gouvernementales*, associations d'aide humanitaire indépendantes des États), des coopératives agricoles et des pouvoirs publics.

Pourtant, les acteurs de terrain (ONG, coopératives, acheteurs institutionnels, commerçants et décideurs publics) font face à **quatre obstacles majeurs** :
1. **Dispersion et hétérogénéité des données publiques** : Les données existent en **Open Data** (*données ouvertes*, données publiques gratuites réutilisables sous réserve de citer la source), mais sont réparties entre la plateforme **HDX** (*Humanitarian Data Exchange*, portail de données humanitaires de l'ONU) pour le PAM et **FAOSTAT** (*base statistique centrale de l'Organisation des Nations Unies pour l'Alimentation et l'Agriculture — FAO*).
2. **Différence de niveau de détail (« grain »), de fréquence et de nature des valeurs** :
   - En Afrique de l'Ouest (WFP HDX), les données sont des **prix mensuels en francs CFA (`XOF`)** relevés à l'échelle de chaque **marché local** (`granularity_level = 'MARKET'`, `frequency = 'MONTHLY'`, `value_type = 'PRICE'`).
   - Au Maroc (FAOSTAT), il n'existe pas de base ouverte par marché local sur HDX : les données disponibles à l'échelle **nationale** (`granularity_level = 'NATIONAL'`) se divisent entre l'**IPC alimentaire mensuel** (*Indice des Prix à la Consommation alimentaire*, mesure sans devise exprimée en base `2015 = 100`, `frequency = 'MONTHLY'`, `value_type = 'INDEX'`) et les **prix aux producteurs agricoles** qui sont uniquement **annuels** (`frequency = 'ANNUAL'`, exprimés en `MAD/tonne`, `value_type = 'PRICE'`). Mélanger ces échelles, ces fréquences ou ces types de valeurs fausserait toute analyse.
3. **Absence de vision prédictive probabiliste accessible aux non-techniciens** : Les portails et API existants permettent de télécharger le passé, mais ne fournissent pas de prévisions publiques à **1, 3 et 6 mois** accompagnées d'un **intervalle d'incertitude** (*fourchette basse et haute encadrant la prévision pour indiquer la marge d'erreur probable du modèle*) lisible par un responsable d'ONG ou de coopérative.
4. **Manque d'alertes automatisées et validées en langage simple** : Lorsqu'un prix s'envole anormalement sur un marché précis par rapport à sa saisonnalité habituelle, les décideurs ont besoin d'une alerte lisible sans devoir manipuler des fichiers **CSV** (*Comma-Separated Values*, format de fichier texte tabulaire où les colonnes sont séparées par des virgules).

### 1.2 La réponse d'AgriPrix Observatory
**AgriPrix Observatory** est un **SID** (*Système d'Information Décisionnel*, ensemble d'outils informatiques qui transforment des données brutes en indicateurs et graphiques pour éclairer la prise de décision) complet, industrialisé et déployable en ligne, qui :
- **Collecte et nettoie automatiquement** via un pipeline **ETL** (*Extract, Transform, Load*, programme automatisé qui extrait les données brutes d'une source, les nettoie/transforme, puis les charge dans une base de données propre) les prix alimentaires de **5 pays d'Afrique de l'Ouest** (Sénégal, Mali, Burkina Faso, Niger, Côte d'Ivoire) au niveau marché et les séries nationales du **Maroc** (IPC alimentaire mensuel et prix producteurs annuels).
- **Stocke les données** dans un **entrepôt de données** (*Data Warehouse*, base de données structurée pour l'analyse historique et statistique) relationnel **PostgreSQL** (*système de gestion de base de données relationnelle open-source*), en isolant strictement :
  1. Le **grain géographique** (`granularity_level` : `'MARKET'` vs `'NATIONAL'`),
  2. La **fréquence temporelle** (`frequency` : `'MONTHLY'` vs `'ANNUAL'`, sans jamais inventer de mois fictif pour une donnée annuelle),
  3. Le **type de valeur** (`value_type` : `'PRICE'` en `XOF` ou `MAD/tonne`, `'INDEX'` en base `2015=100`, ou `'INFLATION_RATE'` en `%`).
- **Applique une règle stricte d'éligibilité au Machine Learning** : seules les séries **mensuelles (`MONTHLY`)**, constituées de relevés de terrain réels (**`priceflag = 'actual'`**, excluant toute valeur agrégée, estimée ou imputée), actives récemment et disposant d'une **fenêtre continue d'au moins 60 mois avec au maximum 3 mois manquants consécutifs** sont éligibles aux prévisions à 1, 3 et 6 mois (soit **745 séries de détail `Retail` en Afrique de l'Ouest** + **la série mensuelle d'indice IPC alimentaire au Maroc** ; les séries annuelles de prix producteurs marocains et les séries ivoiriennes `aggregate` sont consultables historiquement mais exclues des prévisions).
- **Détecte les anomalies de prix** (*Détection d'anomalies*, méthode statistique repérant automatiquement les valeurs anormalement hautes ou basses par rapport au comportement saisonnier habituel), validée sur des crises historiques documentées (2007–2008 et 2022).
- **Génère des prévisions à 1, 3 et 6 mois** avec des **intervalles d'incertitude** calibrés par **prédiction conforme** (*Conformal Prediction*, méthode qui construit la fourchette d'incertitude à partir des quantiles des vraies erreurs observées lors de la validation chronologique passée) et suivis dans **MLflow** (*outil open-source qui enregistre les entraînements de modèles, leurs paramètres et leurs scores agrégés*).
- **Expose les résultats** via une **API REST** (*Application Programming Interface*, interface standardisée permettant à un logiciel de demander des données à un serveur web) sécurisée sous **FastAPI** et un tableau de bord **Streamlit** (*bibliothèque Python permettant de créer des applications web de visualisation de données*) affichant par défaut les **prix de détail (`Retail`)** dans la devise ou l'unité locale d'origine.

---

## 2. Parties prenantes (Stakeholders) et gouvernance AMOA

Dans une démarche d'**AMOA** (*Assistance à Maîtrise d'Ouvrage*, rôle d'interface entre les besoins métier des utilisateurs finaux et l'équipe technique — compétence clé du parcours **MIAGE**), les parties prenantes sont :

| Catégorie | Partie prenante | Rôle et intérêt dans AgriPrix Observatory | Attentes principales |
| :--- | :--- | :--- | :--- |
| **Fournisseurs de données (Amont)** | **PAM (WFP VAM)**, **FAO (FAOSTAT)**, Instituts nationaux (**HCP** au Maroc, **ANSD** au Sénégal, **INSTAT** au Mali) | Collectent les relevés sur le terrain et publient les jeux de données ouverts. | Respect strict des licences ouvertes (`CC BY-IGO` / `CC BY 4.0`), distinction claire entre relevés réels et agrégats, attribution explicite. |
| **Utilisateurs Décisionnels (Cœur de cible)** | **ONG humanitaires**, **Décideurs publics** (Ministères Agriculture/Commerce, dispositifs nationaux de sécurité alimentaire) | Allouent des budgets d'aide alimentaire, déclenchent des distributions ou suivent l'inflation nationale. | Lecture en un coup d'œil des prix de détail (`Retail`) en `XOF` (ou de l'indice IPC au Maroc), alertes de chocs sans jargon, fourchettes de prévision à 1, 3 et 6 mois. |
| **Utilisateurs Économiques de Terrain** | **Coopératives agricoles**, **Acheteurs institutionnels**, **Commerçants / Grossistes** | Négocient les achats/ventes de céréales, planifient le stockage et comparent détail (`Retail`) et gros (`Wholesale`). | Savoir si un prix local dérape par rapport aux marchés voisins et si la tendance à 1–3 mois est haussière ou baissière. |
| **Utilisateurs Techniques / Études** | **Analystes de données**, **Économistes agricoles**, **Chercheurs** | Étudient la transmission de l'inflation, comparent les modèles et croisent les séries. | Métriques d'erreur transparentes par horizon, séparation stricte `MARKET`/`NATIONAL` et `MONTHLY`/`ANNUAL`, export API. |
| **Équipe Projet & Évaluateurs** | **Amine** (Product Owner / AMOA / Ingénieur Logiciel & Data MIAGE), **Recruteurs / Jury de stage** | Pilote les choix fonctionnels et architecturaux ; évalue la rigueur d'ingénierie logicielle, Data Science et DevOps. | Code reproductible, architecture conteneurisée propre, démo publique sécurisée en ligne, zéro chiffre inventé. |

---

## 3. Personas utilisateurs

Un **persona** (*portrait-robot réaliste représentant un groupe d'utilisateurs types du logiciel, avec ses objectifs et ses frustrations*) guide la conception de chaque fonctionnalité.

### Persona 1 — Fatou (42 ans) : Coordinatrice Sécurité Alimentaire & Achats ONG (« La Décideuse »)
- **Profil** : Basée à Dakar (Sénégal), coordonne les programmes d'achats locaux de céréales pour une ONG opérant au Sénégal, au Mali, au Burkina Faso et au Niger.
- **Compétences techniques** : Utilise Excel au quotidien, mais ne maîtrise ni Python ni le jargon statistique.
- **Besoins métier** :
  - Voir rapidement quels marchés connaissent une **hausse anormale** sur les prix de détail (`Retail`) du riz, du mil ou du maïs en **francs CFA (`XOF`)**.
  - Connaître la tendance prévue à **1, 3 et 6 mois** avec sa fourchette d'incertitude pour dimensionner son budget de réserve.
- **Frustrations actuelles** :
  - Les rapports PDF arrivent trop tard ou convertissent les prix en dollars (`USD`) alors qu'elle achète en `XOF`.
  - Les graphiques scientifiques remplis d'acronymes sans explication concrète.

### Persona 2 — Youssef (29 ans) : Analyste Marchés & SI Décisionnel (« L'Analyste MIAGE / Data »)
- **Profil** : Basé à Rabat (Maroc), diplômé d'un Master MIAGE / Économie appliquée. Il suit la dynamique de l'inflation alimentaire au Maroc et la compare aux marchés céréaliers ouest-africains.
- **Compétences techniques** : Maîtrise SQL, les API REST, les outils BI et l'analyse des séries temporelles.
- **Besoins métier** :
  - Suivre et prévoir à 1, 3 et 6 mois l'**indice mensuel des prix alimentaires à la consommation au Maroc (`IPC base 2015 = 100`)**, et consulter en parallèle l'historique des **prix annuels aux producteurs agricoles marocains en `MAD/tonne`**, en ayant la garantie absolue que le système ne mélange jamais une série annuelle, un indice national et un prix mensuel de marché en `XOF`.
  - Vérifier que seules les observations réellement relevées (`priceflag = 'actual'`) servent à entraîner les modèles, afin d'éviter tout **biais de modélisation** (*erreur consistant à entraîner un modèle sur des chiffres déjà estimés ou lissés par un autre algorithme*).
  - Comparer les performances des modèles par horizon (1, 3, 6 mois) sans **fuite de données** (*Data Leakage*, utilisation accidentelle d'informations du futur lors de l'entraînement).

### Persona 3 — Moussa (37 ans) : Gérant d'une Union de Coopératives Céréalières (« L'Acteur Économique de Terrain »)
- **Profil** : Basé à Bobo-Dioulasso (Burkina Faso), gère la commercialisation des stocks de maïs, mil et sorgho de 12 coopératives villageoises.
- **Besoins métier** :
  - Consulter par défaut les prix de détail (`Retail`) en `XOF/kg` (et pouvoir filtrer les prix de gros `Wholesale` en `100 KG` lorsqu'ils existent au Burkina Faso et au Niger) pour décider quand écouler les stocks.

---

## 4. Périmètre retenu : Cœur MVP (Sprints 1 à 4) et Bonus Post-MVP (Sprint 5)

Suite aux arbitrages de rigueur méthodologique, le périmètre est structuré en deux paliers clairs :

### 4.1 Cœur du MVP (Sprints 1 à 4 — Indispensable)
1. **Données hybrides rigoureusement typées (`granularity_level`, `frequency`, `value_type`)** :
   - **Afrique de l'Ouest (`SEN`, `MLI`, `BFA`, `NER`, `CIV`)** : grain `'MARKET'`, fréquence `'MONTHLY'`, type `'PRICE'`, devise `'XOF'`, affichage par défaut `'Retail'`.
   - **Maroc (`MAR`)** : grain `'NATIONAL'`, distinguant :
     - L'**IPC alimentaire mensuel** (`frequency = 'MONTHLY'`, `value_type = 'INDEX'`, unité `'Index (2015=100)'`, 318 mois continus de 2000 à 2026) $\rightarrow$ **éligible aux prévisions à 1, 3 et 6 mois**.
     - Les **prix producteurs agricoles annuels** (`frequency = 'ANNUAL'`, `value_type = 'PRICE'`, unité `'MAD/tonne'`, 1991–2025) $\rightarrow$ **consultables en historique uniquement, non prévus**, stockés à l'année sans jamais inventer de mois fictif.
2. **Règle stricte d'éligibilité au Machine Learning** :
   - Seules les séries `MONTHLY` avec `priceflag = 'actual'`, actives récemment ($\ge 2024$) et disposant d'une **fenêtre continue d'au moins 60 mois avec $\le 3$ mois manquants consécutifs** sont entraînées (soit **745 séries `Retail` en UEMOA** + **1 série mensuelle IPC au Maroc** = **746 séries modélisées**).
3. **Modélisation réaliste et suivi MLflow propre** :
   - Comparaison entre **Baseline statistique vectorisée** (*Seasonal Naive* / *Drift*) et **Modèles globaux de panel par `(Pays, Produit, Horizon)`** (*Ridge* / *LightGBM*) + modèle statistique sur séries de référence, avec **intervalles d'incertitude par prédiction conforme** et suivi agrégé dans **MLflow** (détail par série stocké en table PostgreSQL).
4. **Détection d'anomalies validée scientifiquement** :
   - Évaluée sur des chocs historiques documentés (crise 2007–2008 et crise 2022) en mesurant le taux de détection et le taux de fausses alertes en période calme.
5. **Stack MVP sous Docker Compose, Sécurité Démo Publique & Automatisation Mensuelle** :
   - Conteneurs `postgres` (avec volume nommé Docker compatible Windows et utilisateur lecture seule pour l'API), `etl`, `api` (**FastAPI** avec *Rate Limiting* et *CORS* restreint), `mlflow`, `dashboard` (**Streamlit** consommant uniquement l'API), **CI GitHub Actions**, **planification mensuelle automatisée** (ETL + réentraînement), et déploiement démo publique derrière un **Reverse Proxy HTTPS**.

### 4.2 Bonus Post-MVP (Sprint 5 — Extensions DevOps & BI)
Une fois le MVP complet et stable à la fin du Sprint 4, le **Sprint 5** ajoute les composants avancés :
- **Supervision technique Prometheus + Grafana**.
- **Orchestration Kubernetes locale (`k3s` ou `kind`)** avec manifestes / Helm et `CronJob` mensuel.
- **BI interne Metabase** branchée en lecture seule sur PostgreSQL.
- **Activation optionnelle de la conversion de devises (`EUR`, `USD`)** à la couche d'affichage sous *Feature Flag*.

> **Note d'ingénierie (assumée dans un ADR en Phase 2)** : Pour ~333 000 lignes mensuelles, cette architecture multi-conteneurs (et son extension Kubernetes/Prometheus/Metabase) est **volontairement sur-dimensionnée** par rapport au strict volume de données. Ce choix est délibéré afin de servir de démonstrateur complet des compétences **Génie Logiciel, DevOps et SI Décisionnel (Master MIAGE)** d'Amine.

---

## 5. Cas d'usage, indicateurs de valeur (KPI) et pitch de démonstration (2 min)

### 5.1 Cas d'usage métier et objectifs de valeur (Cibles du projet)

| Cas d'usage (Use Case) | Persona cible | Décision métier éclairée | Indicateur de valeur métier (Objectif cible à mesurer en Sprint 3/4) |
| :--- | :--- | :--- | :--- |
| **UC1 — Alerte précoce de choc d'inflation locale** | Fatou (ONG / Décideur public) | Prioriser l'envoi d'aide alimentaire vers une région où le prix de détail (`Retail`) du mil ou du riz dérape anormalement. | **Objectif cible** : Temps d'identification d'un marché en anomalie **$\le 60\text{ secondes}$** sur le dashboard, avec un taux de détection vérifié sur les crises historiques de 2008 et 2022. |
| **UC2 — Planification budgétaire d'achats à 1, 3 et 6 mois** | Fatou (ONG) & Moussa (Coopérative) | Décider quand acheter les stocks de céréales et provisionner un budget de sécurité basé sur la borne haute de l'intervalle d'incertitude. | **Objectif cible** : Couverture empirique (**PICP**) des intervalles d'incertitude mesurée sur le jeu de test chronologique à $H+1, H+3, H+6$ mois. |
| **UC3 — Analyse comparative et suivi macro Maroc vs marchés UEMOA** | Youssef (Analyste MIAGE / Économiste) | Suivre les prévisions de l'IPC alimentaire mensuel au Maroc (`2015=100`), consulter les prix producteurs annuels en `MAD/tonne`, et auditer le gain des modèles ML face à la baseline. | **Objectif cible** : Mesure transparente du *Skill Score* (gain en % par rapport au modèle naïf saisonnier) par produit et par horizon, sans aucune fuite temporelle. |

### 5.2 Scénario de démonstration de 2 minutes (Pitch Entretien Stage Data Science / IA / MIAGE)
Tous les exemples cités dans ce pitch reposent sur des **observations réelles vérifiées dans nos fichiers** :

- **0 min 00 – 0 min 25 | L'accroche métier et la rigueur sur les données (Casquette MIAGE / AMOA)** :
  > *« En Afrique de l'Ouest, où l'alimentation absorbe ~50 % du budget des ménages (et plus de 65 % chez les plus vulnérables selon le PAM), anticiper les chocs de prix est vital. J'ai conçu **AgriPrix Observatory** à partir des données ouvertes du PAM (HDX) et de la FAO. En auditant les données réelles, j'ai constaté que l'Afrique de l'Ouest avait des prix mensuels par marché en `XOF`, tandis que le Maroc avait un indice IPC alimentaire mensuel (`base 2015=100`) et des prix producteurs uniquement annuels en `MAD/tonne`. Mon entrepôt en étoile sépare donc strictement le grain (`MARKET` vs `NATIONAL`), la fréquence (`MONTHLY` vs `ANNUAL`) et le type de valeur (`PRICE` vs `INDEX`). »*
- **0 min 25 – 1 min 05 | La Vue Décideur sur le Dashboard Streamlit (Orientation Produit)** :
  > *« Voici la vue dédiée à une coordinatrice d'ONG, affichant par défaut les prix de détail (`Retail`). Le détecteur d'anomalies — dont l'objectif est d'être validé au Sprint 3 sur des crises historiques documentées comme la flambée de **+88 % du mil à Ouagadougou (Sankaryaré) en août 2022** ou de **+103 % du riz à Dakar (Tilène) en août 2008** — signalera les marchés en surchauffe en français simple. En sélectionnant un marché, elle obtiendra la prévision à 1, 3 et 6 mois avec son **intervalle d'incertitude** calibré par prédiction conforme. »*
- **1 min 05 – 1 min 35 | La Vue Analyste, l'éligibilité stricte et MLflow (Casquette Data Science)** :
  > *« Côté Data Science, j'ai exclu toute donnée agrégée ou estimée (`priceflag != 'actual'`) et imposé une fraîcheur relative ($\le 3\text{ mois}$ par rapport à la dernière date du fichier) ainsi qu'une fenêtre continue d'au moins 60 mois avec au maximum 3 mois manquants consécutifs. Ainsi, les prévisions couvrent **4 pays d'Afrique de l'Ouest (`SEN`, `MLI`, `BFA`, `NER` — 737 séries `Retail`) plus l'indice IPC alimentaire mensuel du Maroc (`1 série`)**, tandis que la Côte d'Ivoire (`CIV`, passée en `aggregate` depuis 2020) et les prix producteurs annuels marocains restent en consultation historique. Les modèles globaux par produit/pays seront évalués en validation chronologique glissante (*rolling-origin*) face à une baseline saisonnière, avec des métriques agrégées dans MLflow et le détail par série en base. »*
- **1 min 35 – 2 min 00 | L'industrialisation DevOps et la sécurité (Casquette Génie Logiciel)** :
  > *« Enfin, l'architecture multi-conteneurs tourne sous Docker Compose avec un utilisateur PostgreSQL en lecture seule pour l'API FastAPI, une limitation de débit, un rafraîchissement mensuel automatisé, une CI GitHub Actions et une extension Kubernetes/Prometheus/Grafana documentée. »*
