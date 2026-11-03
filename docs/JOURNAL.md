# Journal d'Ingénierie — AgriPrix Observatory

> Ce journal documente en toute transparence chaque étape du projet : **ce qui a été fait**, **pourquoi**, **les erreurs ou obstacles rencontrés (ce qui a échoué)** et **les apprentissages techniques et méthodologiques**.

---

## Phase 0 — Cadrage, Étude de l'Existant et Audit des Sources de Données
**Date** : 3 novembre 2026

### 1. Ce que nous avons fait
1. **Audit technique réel des sources de données publiques** avant tout engagement sur le périmètre :
   - Interrogation de l'**API CKAN** (*interface programmable du portail de données ouvertes de l'ONU*) sur `https://data.humdata.org/api/3/action/package_show` pour vérifier la disponibilité, la licence et la fraîcheur des jeux de données du **PAM / WFP** (*Programme Alimentaire Mondial*) en Afrique de l'Ouest et au Maroc.
   - Téléchargement et comptage exact en flux mémoire des 5 fichiers nationaux de la zone **UEMOA** (*Union Économique et Monétaire Ouest-Africaine*) : Sénégal (`54 039 lignes`), Mali (`132 286 lignes`), Burkina Faso (`58 203 lignes`), Niger (`68 699 lignes`) et Côte d'Ivoire (`10 813 lignes`), soit un total vérifié de **324 040 lignes de prix**.
   - Test de disponibilité et inspection du contenu des archives officielles **FAOSTAT** (*base statistique de la FAO*) sur `https://bulks-faostat.fao.org/production/` (`ConsumerPriceIndices_E_Africa.zip` et `Prices_E_Africa.zip`) pour le Maroc (`Area Code = 143` : 36 séries mensuelles d'indices des prix alimentaires 2000–2026 et 367 séries de prix producteurs en dirhams `MAD`).
2. **Co-construction du cadrage avec Amine** (5 questions structurantes) :
   - Validation de l'approche hybride à deux grains strictement séparés (`MARKET` pour l'Afrique de l'Ouest en `XOF`, `NATIONAL` pour le Maroc en `MAD`).
   - Validation du panier de sécurité alimentaire (5 à 8 produits clés avec $\ge 36$ mois d'historique).
   - Validation des horizons de prévision (1, 3 et 6 mois avec intervalles d'incertitude) et de la règle stricte des devises (modélisation et affichage par défaut en devise locale uniquement ; conversion en devise tierce isolée en option post-MVP derrière un *Feature Flag*).
   - Évolution de l'ambition DevOps : suppression du plafond strict de 4 Go de RAM au profit d'une architecture multi-conteneurs complète (PostgreSQL, ETL, FastAPI, MLflow, Streamlit, Prometheus/Grafana, et Metabase en option *Could*), orchestrée avec Docker Compose puis Kubernetes local (`k3s` / `kind`), plus stratégie d'hébergement public à faible coût.
3. **Production des livrables de la Phase 0** :
   - [`docs/00-cadrage.md`](./00-cadrage.md) : reformulation du besoin, gouvernance AMOA, parties prenantes, 3 personas, cas d'usage avec indicateurs de valeur (KPI) et pitch d'entretien de 2 minutes.
   - [`docs/01-etude-existant.md`](./01-etude-existant.md) : étude comparative (WFP VAM, FAO FPMA/FAOSTAT, Banque mondiale RTFP, FEWS NET, RESIMAO/HCP) et positionnement différenciant.
   - [`docs/02-sources-donnees.md`](./02-sources-donnees.md) : preuves d'audit, volumétrie réelle, schémas exacts, règles de filtrage et analyse juridique des licences (`CC BY-IGO` et `CC BY 4.0`) pour l'usage public et commercial.

### 2. Pourquoi nous l'avons fait ainsi
- En Data Science et en **AMOA** (*Assistance à Maîtrise d'Ouvrage*), bâtir un cahier des charges sur des données supposées sans avoir vérifié les fichiers réels est la première cause d'échec des projets data.
- Isoler dès la Phase 0 la différence de **grain** (*niveau de détail d'une ligne de données*) entre l'Afrique de l'Ouest (marché local) et le Maroc (national) ainsi que la gestion des devises (`XOF` vs `MAD`) évite de concevoir en Phase 2 un schéma de base de données incohérent ou biaisé.

### 3. Ce qui a échoué (et comment nous l'avons résolu)
1. **Absence du Maroc sur WFP HDX (`HTTP 404`)** :
   - *Constat* : La requête sur `wfp-food-prices-for-morocco` a échoué (`MISS / 404`). Le PAM ne suit pas les marchés locaux marocains sur HDX.
   - *Résolution* : Bascule sur les archives officielles **FAOSTAT Afrique** pour le Maroc, en assumant et en documentant la différence de granularité (`NATIONAL` contre `MARKET`).
2. **Panne du serveur d'API directe de FAOSTAT (`Error 521`)** :
   - *Constat* : L'appel `curl.exe -s "https://fenixservices.fao.org/faostat/api/v1/en/definitions/domain/PP"` a renvoyé `error code: 521` (le serveur web d'origine de la FAO était hors ligne derrière Cloudflare).
   - *Résolution* : Test des dépôts d'archives compressées hébergés sur Amazon S3 (`https://bulks-faostat.fao.org/production/ConsumerPriceIndices_E_Africa.zip` et `Prices_E_Africa.zip`), qui ont répondu en moins de 2 secondes avec `HTTP 200 OK`. Notre pipeline ETL s'appuiera donc sur ces archives S3 hautement disponibles plutôt que sur l'API `fenixservices` instable.
3. **Démon Docker Desktop arrêté lors du premier test** :
   - *Constat* : `docker --version` (`29.4.2`) et `docker compose version` (`v5.1.3`) fonctionnent, mais `docker run` a renvoyé `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` car l'application Docker Desktop n'était pas lancée en tâche de fond.
   - *Résolution* : L'audit de la Phase 0 ne nécessitant que des requêtes HTTP de vérification documentaire, nous avons utilisé `curl.exe` et les flux mémoire natifs de l'OS sans rien installer sur l'hôte. Nous démarrerons le moteur Docker Desktop au début de la Phase 3 (Mise en place).
4. **Lecture binaire par défaut de `Invoke-WebRequest` sur les CSV de HDX** :
   - *Constat* : HDX renvoie certains fichiers CSV avec un type MIME binaire, ce qui faisait échouer le découpage de chaînes `.Split("`n")` dans PowerShell.
   - *Résolution* : Utilisation directe de `curl.exe -s -L` pour compter exactement les 324 040 lignes et extraire la première et la dernière ligne de chaque pays.

### 4. Ce que nous avons appris
- **Leçon Data Engineering n°1** : Toujours préférer les dépôts de fichiers statiques versionnés sur stockage objet (comme le S3 de FAOSTAT ou les ressources CKAN de HDX) aux API institutionnelles dynamiques souvent sujettes aux coupures (`HTTP 521`).
- **Leçon Data Modeling n°2** : Les fichiers WFP actuels sur HDX n'incluent plus systématiquement la ligne de tags `#HXL` en ligne 2 (les données commencent directement en ligne 2), tandis que les fichiers FAOSTAT sont en format « large » (une colonne par année `Y2000`..`Y2026`) et nécessiteront un dépivotage (*unpivot*) dans l'ETL.
- **Leçon Architecture & ML n°3** : Ne jamais convertir les prix en devise étrangère (`USD` ou `EUR`) avant l'entraînement d'un modèle de prévision local, car cela injecterait la volatilité du marché des changes (taux `USD/XOF` ou `USD/MAD`) dans un modèle censé prédire l'offre et la demande agricoles locales.


---

## Phase 1 — Cahier des Charges et Backlog Agile (MoSCoW & 4 Sprints)
**Date** : 3 novembre 2026

### 1. Ce que nous avons fait
1. **Rédaction du Cahier des Charges complet ([`docs/03-cahier-des-charges.md`](./03-cahier-des-charges.md))** :
   - **Analyse des besoins utilisateurs (approche AMOA / MIAGE)** : formalisation des décisions métiers pour 5 profils d'utilisateurs (ONG humanitaires, décideurs publics, coopératives agricoles/commerçants, acheteurs institutionnels, analystes data/économistes) et définition de **4 KPI** (*indicateurs clés de performance*) mesurables : délai de diagnostic d'un choc (`KPI-M1`), gain de précision prédictive par rapport à la baseline (`KPI-M2`), fiabilité de couverture des intervalles d'incertitude `PICP` (`KPI-M3`) et conformité qualité de l'entrepôt (`KPI-M4`).
   - **Définition de 6 objectifs SMART** couvrant l'ETL hybride, le Machine Learning à 1/3/6 mois avec intervalles d'incertitude, la détection d'anomalies, l'API FastAPI, le dashboard bi-persona Streamlit et l'architecture multi-conteneurs (Docker Compose + Kubernetes local + Prometheus/Grafana + CI/CD).
   - **Spécification de 17 Exigences Fonctionnelles (`EF-01` à `EF-17`) et 13 Exigences Non Fonctionnelles (`ENF-01` à `ENF-13`)**, incluant les contraintes strictes sur les devises locales (`XOF` et `MAD`), l'isolation des grains (`MARKET` vs `NATIONAL`), la table séparée de taux de change et le *Feature Flag* de conversion post-MVP.
   - **Matrice des risques (`RSK-01` à `RSK-06`)** et **Glossaire complet (A à Z)** expliquant chaque sigle ou terme technique en une phrase simple.
2. **Construction du Backlog Produit et du plan en 4 Sprints ([`docs/04-backlog.md`](./04-backlog.md))** :
   - Découpage en **5 Épopées (`EPIC-0` à `EPIC-4`)** et **19 User Stories (`US-01` à `US-19`)** munies de critères d'acceptation vérifiables (*Étant donné / Quand / Alors*).
   - Priorisation **MoSCoW** : séparation nette entre le socle obligatoire (*Must*), les démonstrateurs DevOps avancés (*Should* : Prometheus/Grafana, Kubernetes `k3s`/`kind`), et les options post-MVP (*Could* : conversion de devises sous *Feature Flag* et BI interne Metabase).

### 2. Pourquoi nous l'avons fait ainsi
- Dans un projet combinant **Génie Logiciel, Data Science et Master MIAGE**, le cahier des charges ne doit pas être une simple liste technique : il doit prouver que chaque modèle mathématique et chaque conteneur Docker sert une décision métier mesurable (acheter un stock de céréales, déclencher une alerte d'aide alimentaire, auditer la fiabilité d'une prévision).
- Placer la conversion de devises et Metabase en catégorie **Could** tout en intégrant dès maintenant leurs prérequis d'architecture (table de taux de change mensuels séparée, schéma en étoile propre, isolation des conteneurs) nous protège contre la dérive du périmètre (*Scope Creep*) tout en préparant une évolution sans dette technique.

### 3. Ce qui a échoué / Points de vigilance identifiés
- *Aucun échec technique durant cette phase de spécification*, mais l'exercice d'écriture des critères d'acceptation a mis en évidence un point de vigilance méthodologique crucial pour le Sprint 2 :
  - **Évaluation de l'intervalle d'incertitude (`PICP`)** : il ne suffit pas d'afficher une fourchette basse et haute ; il faudra vérifier sur le jeu de test temporel quel pourcentage des prix réels tombe effectivement dans cette fourchette pour ne pas donner un faux sentiment de sécurité aux décideurs d'ONG ou de coopératives.

### 4. Ce que nous avons appris
- **Leçon AMOA / MIAGE** : Un bon indicateur de performance pour un modèle de prévision budgétaire n'est pas seulement l'erreur moyenne (`MAE`), mais aussi la **couverture de l'intervalle d'incertitude (`PICP`)**, car un acheteur de coopérative utilise la borne haute de la prévision pour provisionner sa trésorerie de sécurité.
- **Leçon Architecture Logicielle** : Découpler la donnée stockée (toujours en devise locale d'origine `XOF` ou `MAD`) de la donnée affichée (convertible à la volée dans l'API derrière un *Feature Flag*) garantit que les modèles de Machine Learning apprennent la vraie dynamique des marchés agricoles locaux et non les fluctuations spéculatives du dollar ou de l'euro.


---

## Révision de Rigueur Post-Phase 1 — Audit Approfondi et Application des 8 Corrections
**Date** : 3 novembre 2026

Suite à la revue critique d'Amine à la porte de validation de la Phase 1, nous avons mené un audit programmé complet sur les **324 040 lignes** des 5 fichiers WFP et les **9 884 observations dépivotées** des 2 fichiers FAOSTAT Maroc, et corrigé les documents `00-cadrage.md`, `01-etude-existant.md`, `02-sources-donnees.md`, `03-cahier-des-charges.md` et `04-backlog.md`. Voici pour chacune des 8 corrections **ce qui était faux**, **pourquoi**, et **ce qui change**.

---

### Correction 1 — Maroc : Fréquence (`MONTHLY` vs `ANNUAL`), Type de valeur (`PRICE` vs `INDEX`) et Interdiction des mois fictifs
- **Ce qui était faux ou imprécis** :
  1. Nous avions regroupé les données marocaines sous le terme générique de « 403 séries en devise `MAD` », en confondant le nombre de lignes du tableau large (*wide format*) avec le nombre d'observations dépivotées (*unpivoted*), et en laissant croire que l'IPC alimentaire était un prix en `MAD`.
  2. Nous avions écrit que l'ETL convertirait les colonnes d'années FAOSTAT en dates `YYYY-MM-15` pour toutes les données marocaines, y compris pour les prix producteurs agricoles qui sont pourtant **annuels**.
- **Pourquoi c'était une erreur** :
  - L'**IPC alimentaire (`Item Code = 23013`)** est un **indice sans unité monétaire (`base 2015 = 100`)** et non un prix en dirhams (`MAD`).
  - Les **prix producteurs agricoles (`Prices_E_Africa.csv`, `Element 5530` en `MAD/tonne`)** ne sont collectés qu'une fois par an (`Months = "Annual value"`). Inventer une date mensuelle (`YYYY-MM-15`) ou tenter de prédire à 1, 3 et 6 mois une série annuelle est un contresens statistique.
- **Ce qui change** :
  - **Distinction exacte vérifiée** : Pour le Maroc, `ConsumerPriceIndices_E_Africa_NOFLAG.csv` contient **3 séries mensuelles** (36 lignes larges = **942 observations mensuelles dépivotées**), dont la série **`23013` (IPC Alimentaire `2015=100`, 318 mois continus de 2000 à 2026)** qui est **la seule série marocaine éligible aux prévisions à 1, 3 et 6 mois**. Le fichier `Prices_E_Africa_NOFLAG.csv` contient **367 séries annuelles** (**8 942 observations annuelles dépivotées** en `MAD/tonne` ou indice producteur), stockées à l'année (`reference_year`, sans mois inventé) et réservées à la **consultation historique (`is_ml_eligible = FALSE`)**.
  - **Ajout au modèle de données** : Colonnes obligatoires `frequency` (`'MONTHLY'` | `'ANNUAL'`) et `value_type` (`'PRICE'` | `'INDEX'` | `'INFLATION_RATE'`) avec `unit` explicite (`'KG'`, `'100 KG'`, `'MAD/tonne'`, `'Index (2015=100)'`, `'%'`).
  - Mise à jour de `SMART-01`, `EF-02`, `EF-05`, `US-04`, `US-05`, `US-09`, des personas et du périmètre.

---

### Correction 2 — Éligibilité au Machine Learning : Pourquoi 36 mois ne suffisent pas et Règle de continuité sur 60 mois
- **Ce qui était faux ou imprécis** :
  - Nous avions fixé un critère naïf : « avoir $\ge 36$ observations au total dans l'historique ».
- **Pourquoi c'était une erreur** :
  1. **Arithmétiquement insuffisant** : Créer les variables de saisonnalité annuelle (`lag_12`) consomme 12 mois ; évaluer sans fuite temporelle sur un cycle annuel complet de validation (12 mois) et un cycle annuel complet de test (12 mois) consomme 24 mois. Sur 36 mois, il reste $36 - 12 - 24 = 0\text{ mois}$ d'entraînement ! Pour disposer d'au moins 2 cycles annuels d'entraînement effectif ($\ge 24\text{ mois}$), il faut au minimum $12 + 24 + 12 + 12 = \mathbf{60\text{ mois (5 ans)}}$.
  2. **Séries mortes ou hachées** : Notre audit sur les 5 pays UEMOA montre que sur les **1 718 séries** ayant $\ge 36$ observations n'importe quand depuis 1990, plus de **970 séries** sont arrêtées avant 2024 ou coupées par des trous de plusieurs années.
- **Ce qui change** :
  - **Nouvelle règle stricte (`EF-07`, `US-05`)** : `frequency = 'MONTHLY'`, `priceflag = 'actual'`, série active récemment ($\ge \text{janvier 2024}$), et **fenêtre continue récente d'au moins 60 mois observés avec au maximum 3 mois manquants consécutifs (`max_consecutive_missing <= 3`)**.
  - **Production du tableau de couverture réel dans `docs/02-sources-donnees.md`** : **745 séries UEMOA** (sur 184 marchés dans 4 pays : `SEN`=50, `MLI`=230, `BFA`=278, `NER`=187, `CIV`=0) + **1 série mensuelle IPC au Maroc** = **746 séries éligibles**.

---

### Correction 3 — Définition de la Clé d'une Série, Affichage `Retail` par défaut, Stratégie d'Entraînement et MLflow
- **Ce qui était faux ou imprécis** :
  - La clé de déduplication de `US-06` omettait l'unité (`unit`) et la devise (`currency`), et nous n'avions pas précisé comment entraîner 746 séries ni comment éviter de créer des milliers de runs dans MLflow.
- **Pourquoi c'était une erreur** :
  - Au Burkina Faso et au Niger, certains marchés relèvent à la fois le détail (`Retail` en `KG`) et le gros (`Wholesale` en `100 KG`). Sans `pricetype` et `unit` dans la clé de série, ces relevés entreraient en collision.
  - Entraîner un modèle lourd séparé et créer un run MLflow pour chacune des 746 séries ($\times 3$ horizons) saturerait la machine d'Amine et rendrait l'interface MLflow illisible.
- **Ce qui change** :
  - **Clé formelle d'une série** : `(country_iso3, market_id, commodity_id, pricetype, unit, currency_code, frequency, value_type)`. Ajoutée à `US-06`.
  - **Affichage par défaut** : `pricetype = 'Retail'` (qui représente par ailleurs 100 % des 745 séries UEMOA éligibles à la prévision).
  - **Stratégie d'entraînement rapide ($< 3\text{ min}$)** : Baseline statistique vectorisée (*Seasonal Naive* / *Drift*) + **Modèles ML globaux de panel par `(Pays, Produit, Horizon)`** (*Ridge* et *LightGBM / HistGradientBoosting*) + modèle statistique sur séries de référence.
  - **Stratégie MLflow propre** : **1 run MLflow par expérience globale `(model_family, horizon_months, granularity_level)`** contenant les métriques agrégées, et sauvegarde des métriques détaillées des 746 séries dans la table PostgreSQL `fact_model_metrics_by_series`.

---

### Correction 4 — Audit et Filtrage strict de `priceflag`
- **Ce qui était faux ou imprécis** :
  - Nous avions mentionné `priceflag` dans le schéma sans avoir compté ses valeurs exactes par pays ni exclu formellement les lignes non-`actual` de l'entraînement ML.
- **Pourquoi c'était une erreur** :
  - Entraîner un modèle sur des valeurs agrégées, lissées ou estimées (`priceflag != 'actual'`) revient à modéliser les artefacts d'un autre traitement statistique.
- **Ce qui change** :
  - **Audit complet documenté dans `docs/02-sources-donnees.md`** : sur les 324 040 lignes UEMOA, **319 986 (98,75 %) sont `actual`** (100 % au Sénégal, Mali, Burkina Faso et Niger) et **4 054 (1,25 %) sont `aggregate`**, concentrées intégralement en **Côte d'Ivoire (`CIV`, 37,49 % du fichier, couvrant toute la période d'avril 2020 à mai 2026)**.
  - Exclusion stricte de toute ligne `priceflag != 'actual'` de l'entraînement ML (`EF-03`, `EF-07`), ce qui explique scientifiquement pourquoi la Côte d'Ivoire est en mode « Consultation historique » avec 0 série prédictive active.

---

### Correction 5 — Sourçage des Chiffres, Honnêteté de la Matrice Comparative et État de FEWS NET
- **Ce qui était faux ou imprécis** :
  - La fourchette « 40 à 65 % du revenu » n'était pas sourcée par pays, les objectifs non encore réalisés (`< 30 s`, `70 % couverture`) n'étaient pas marqués comme *cibles*, le choc cité dans le pitch n'avait pas été vérifié dans le CSV, la ligne WFP disait « Pas d'API », et FEWS NET était décrit de façon trop générale.
- **Pourquoi c'était une erreur** :
  - Tout chiffre de contexte doit être sourcé ou qualifié d'objectif cible, et HDX fournit bel et bien une API CKAN et l'API REST HDX HAPI.
- **Ce qui change** :
  - **Sourçage exact (`docs/00-cadrage.md`)** : indicateur **FES (*Food Expenditure Share*) du PAM** et enquêtes nationales (**~49 % au Burkina Faso, ~53 % au Sénégal, $> 65\text{–}75\text{ \%}$ pour les ménages vulnérables au Sahel** selon le PAM ; **~35 à 40 % au Maroc** selon le **HCP**).
  - **Chocs réels vérifiés dans nos CSV pour le pitch et les tests** : **+88,0 % sur le mil à Ouagadougou (Sankaryaré) en août 2022** (`249` $\rightarrow$ `468 XOF/kg`), **+103,5 % sur le riz importé à Dakar (Tilène) en août 2008** (`215` $\rightarrow$ `437,5 XOF/kg`), **+58,9 % sur le mil à Maradi (Niger) en août 2008** (`113,94` $\rightarrow$ `181 XOF/kg`), et **+15,53 % d'inflation alimentaire au Maroc en décembre 2022**.
  - **Matrice comparative (`docs/01-etude-existant.md`)** : colonne renommée **« Cibles du projet »** avec mention explicite `Cible MVP (Sprint X)` / `Cible Bonus (Sprint 5)` ; correction de la ligne API de WFP/HDX (API CKAN + HDX HAPI pour l'historique, mais pas d'API de prévision) ; mise à jour de l'état 2025–2026 de **FEWS NET** (reprise mi-2025 après le gel USAID de début 2025, portail USGS et API FDW sous compte).

---

### Correction 6 — Cohérence MoSCoW, Découpage en 5 Sprints (MVP S1–S4 vs Bonus S5) et ADR Sur-dimensionnement
- **Ce qui était faux ou imprécis** :
  - Prometheus/Grafana et Kubernetes figuraient à la fois dans le « Cœur MVP » et en *Should Have*, et le plan en 4 sprints mélangeait la finalisation du MVP et les bonus DevOps/BI.
- **Pourquoi c'était une erreur** :
  - Si le temps manque, les briques de démonstration DevOps avancées (Kubernetes, Prometheus/Grafana, Metabase) ne doivent jamais compromettre la livraison propre du MVP sous Docker Compose.
- **Ce qui change** :
  - **Redéfinition claire** : **MVP (Sprints 1 à 4)** = ETL + Entrepôt + Modèles + Anomalies + API + Streamlit + CI + Automatisation mensuelle + Hébergement sous Docker Compose. **Bonus Post-MVP (Sprint 5 — *Could Have*)** = Prometheus/Grafana + Kubernetes (`k3s`/`kind`) + Metabase + Conversion active de devises.
  - **Découpage en 5 sprints** dans `docs/04-backlog.md` (S1 ETL/Entrepôt, S2 Prévisions/MLflow, S3 Anomalies/API, S4 Dashboard/Hébergement MVP, S5 Bonus DevOps & BI).
  - **ADR prévu en Phase 2** assumant explicitement que cette architecture multi-conteneurs est volontairement sur-dimensionnée pour ~333 000 lignes afin de démontrer les compétences DevOps et SI Décisionnel d'Amine.
  - **Disponibilité hebdomadaire demandée à Amine** avant de figer toute estimation d'effort par sprint.

---

### Correction 7 — Validation Scientifique des Anomalies et Méthode des Intervalles d'Incertitude
- **Ce qui était faux ou imprécis** :
  - Nous n'avions pas défini comment prouver que le détecteur d'anomalies fonctionne, ni quelle méthode mathématique utiliser pour calculer les intervalles d'incertitude.
- **Pourquoi c'était une erreur** :
  - Un détecteur non évalué sur de vraies crises connues peut soit rater les crises, soit sonner l'alarme en permanence. De même, un intervalle d'incertitude gaussien naïf sous-estime les queues de distribution des prix agricoles.
- **Ce qui change** :
  - **Validation des anomalies (`SMART-03`, `EF-11`, `US-10`)** : évaluation sur un jeu de référence de chocs historiques documentés (**crise 2007–2008 et crise 2022**) en mesurant le **taux de détection (*Recall*)** et le **taux de fausses alertes en période calme (2015–2018, cible $< 5\text{ \%}$)**.
  - **Intervalles par Prédiction Conforme (`EF-10`, `US-09` + ADR prévu en Phase 2)** : utilisation de la **Prédiction Conforme Temporelle (*Split Conformal Prediction* sur les quantiles des erreurs de validation par horizon)**, avec documentation de ses limites (hypothèse de stationnarité locale des résidus) et mesure du **PICP** sur le jeu de test.

---

### Correction 8 — Sécurité de la Démo Publique, Automatisation Mensuelle et Volumes Nommés sous Windows
- **Ce qui était faux ou imprécis** :
  - L'API partageait le même utilisateur PostgreSQL que l'ETL, n'avait ni limitation de débit (*Rate Limiting*) ni restriction *CORS* explicite, le rafraîchissement mensuel était manuel, et le stockage PostgreSQL sous Windows n'imposait pas un volume nommé Docker.
- **Pourquoi c'était une erreur** :
  - Une démo publique accessible par lien doit appliquer le principe du moindre privilège et se protéger contre les abus ; sous Windows/WSL2, monter un dossier NTFS dans PostgreSQL provoque des erreurs `chmod` et dégrade les performances.
- **Ce qui change** :
  - Ajout dans `ENF-01`, `ENF-04`, `ENF-05`, `EF-16`, `US-01`, `US-05`, `US-11` et `US-15` :
    1. **Volume nommé Docker (`pgdata`)** obligatoire pour PostgreSQL sous Windows.
    2. **Utilisateur PostgreSQL en lecture seule (`agriprix_readonly`)** pour l'API FastAPI (et Metabase).
    3. **Limitation de débit (*Rate Limiting*)** et **CORS restreint** sur l'API FastAPI.
    4. **Mise à jour mensuelle automatisée** (planificateur ETL + réentraînement dans Docker Compose au Sprint 4, puis `CronJob` Kubernetes au Sprint 5).


---

## Phase 2 — Analyse et conception (et intégration des 7 raffinements méthodologiques)
**Date** : 19 avril 2026

Suite au « Go pour la Phase 2 » d'Amine, nous avons réalisé la conception complète du système (`docs/05-conception.md`, 7 diagrammes Mermaid dans `docs/diagrams/01..07`, et 7 ADR dans `docs/adr/001..007`) et appliqué les mises à jour ciblées sur `docs/00-cadrage.md` (point 6) et `docs/04-backlog.md` (point 7 & calibrage de l'effort) :

1. **Règle de fraîcheur relative ($\le 3\text{ mois}$) et recomptage exact des séries (`docs/05-conception.md`, `docs/diagrams/05-activite-pipeline.md`)** :
   - Remplacement du seuil fixe `>= 2024-01-15` par la règle dynamique `last_obs_date >= max_date(country) - 3 mois`.
   - **Recomptage exact vérifié sur les fichiers CSV/ZIP** : **738 séries éligibles au ML** (**737 séries `Retail`** sur 183 marchés dans 4 pays UEMOA : `SEN` = 45, `MLI` = 230, `BFA` = 275, `NER` = 187, `CIV` = 0 + **1 série nationale d'IPC Alimentaire `23013`** au Maroc). Les 8 séries UEMOA arrêtées entre 2024 et début 2026 (5 au Sénégal, 3 au Burkina Faso) basculent proprement en consultation historique seule (`is_ml_eligible = FALSE`).
2. **Découpage chronologique par date de calendrier commune $T_{\text{cutoff}}$ (`ADR-003`, `docs/diagrams/02-processus-bpmn.md`)** :
   - Tous les marchés d'un même modèle global `(country_iso3, commodity_group, horizon)` partagent exactement la même date de coupure calendaire $T_{\text{cutoff}}$ et excluent la zone tampon où l'origine $t < T_{\text{cutoff}}$ mais la cible $t+h > T_{\text{cutoff}}$, éliminant toute fuite temporelle inter-marchés.
3. **Profondeur d'historique et évaluation *Rolling-Origin* multi-fenêtres (`ADR-003`)** :
   - Justification de l'entraînement sur le **segment continu `actual` récent plafonné à 10 ans (60 à 120 mois post-2015)** plutôt que sur les seuls 60 derniers mois (qui ne laisseraient que 24 mois d'entraînement effectif après création du `lag_12` et des fenêtres de validation/test).
   - Remplacement du test unique par un backtesting *Rolling-Origin* sur **3 fenêtres annuelles successives** : Fenêtre 1 (Choc 2022 : `2022-01..12`), Fenêtre 2 (Stabilisation : `2024-07..2025-06`), Fenêtre 3 (Récente : `2025-09..2026-08/09`).
4. **Intervalles conformes calibrés sur erreurs relatives par groupe et mesure du PICP en période de choc 2022 (`ADR-004`)** :
   - Calibration des quantiles empiriques $[q_{10}, q_{90}]$ sur les **erreurs relatives** $\frac{y - \hat{y}}{\hat{y}}$ regroupées par `(country_iso3, commodity_group, horizon_months)`.
   - Mesure et affichage séparés de `PICP_80_recent` et de `PICP_80_shock_2022`, avec explication de la rupture d'échangeabilité lors des chocs macroéconomiques inédits.
5. **Contrôle d'intégrité anti-troncature des fichiers téléchargés (`DQ-01`, `DQ-02`, `docs/diagrams/02-processus-bpmn.md`, `docs/diagrams/04-diagrammes-sequence.md`)** :
   - Suite au constat réel lors de l'audit où `wfp_NER.csv` était arrivé tronqué à 57 113 lignes (6,59 Mo) au lieu de 68 699 lignes (7,90 Mo), l'ETL interroge d'abord `package_show` sur l'API CKAN HDX et compare `expected_size` en octets, `hash` MD5 et le nombre de lignes avant d'autoriser toute lecture SQL (échec + retry avec backoff exponentiel si tronqué ou si challenge WAF `HTTP 202`).
6. **Sourçage FES avec liens et années, attribution exacte *Smith & Subandoro (2007)* et mise à jour du pitch (`docs/00-cadrage.md`)** :
   - Ajout des liens et années exacts pour chaque source FES (IFPRI 2007 `doi:10.2499/0896297675`, PAM CARI 2015/2021, ANSD Sénégal EHCVM II 2021/2022, INSD Burkina Faso EHCVM II 2021/2022, HCP Maroc ENCDM & notes 2022–2023).
   - Remplacement de « que j'ai validé » par une formulation d'objectif futur dans le pitch, et mention explicite des **4 pays d'Afrique de l'Ouest (`SEN`, `MLI`, `BFA`, `NER`) + l'IPC Alimentaire du Maroc (`MAR`)**.
7. **Comparatif d'hébergement (VPS x86 vs VM ARM64 Oracle Cloud) et CI Multi-Architecture (`ADR-007`, `docs/04-backlog.md`)** :
   - Comparaison entre Oracle Cloud Always Free (Ampere A1 `linux/arm64`, 4 OCPU / 24 Go RAM, 0 €) et un VPS étudiant/low-cost (`linux/amd64` ou `arm64`, ~3,80 €/mois), et ajout de la compilation **Docker Buildx multi-architecture (`linux/amd64,linux/arm64`)** dans `US-02`.
8. **Calibrage de l'effort des Sprints et Plan de délestage (`docs/04-backlog.md`)** :
   - Les valeurs `[X]` heures/semaine et `[date approximative]` du message d'Amine étant restées sous forme de balises génériques, nous avons produit une grille de calibrage complète (~52h pour le MVP Sprints 1 à 4 selon 3 rythmes : 10h/sem, 15h/sem, 25h/sem) assortie d'un plan de délestage gradué en 4 niveaux permettant de descendre jusqu'à ~41h sans sacrifier la qualité scientifique.


---

## Revue d'ingénierie de fin de Phase 2 — 8 corrections de conception appliquées
**Date** : 19 avril 2026

Avant d'ouvrir la Phase 3, nous avons appliqué 8 corrections de rigueur sur les diagrammes (`01` à `07`), la conception (`05-conception.md`) et les ADR (`002`, `003`, `004`) :

1. **Schéma de `fact_price_observation` et FK composites (`06-modele-donnees.md`, `ADR-002`)** :
   - **Ce qui posait problème** : `reference_year` et `reference_month` étaient dupliqués dans `fact_price_observation` (risque d'incohérence avec `dim_calendar`), et aucune contrainte SQL n'empêchait de lier une série `MONTHLY` à un `calendar_id` `ANNUAL`.
   - **Ce qui change** : Suppression de `reference_year/month` de `fact_price_observation`, ajout de `frequency` et des deux **FK composites** `(series_id, frequency) -> dim_series_catalog` et `(calendar_id, frequency) -> dim_calendar`, et contrainte `UNIQUE (series_id, calendar_id, source_flag)` sur des colonnes `NOT NULL`.
2. **Versionnement via `training_run`, `fact_conformal_quantiles` et tables d'audit ETL (`06-modele-donnees.md`, `03-diagramme-classes.md`, `ADR-004`)** :
   - **Ce qui manquait** : Les tables analytiques n'avaient pas de clé d'unicité versionnée, les quantiles conformes n'avaient pas de table dédiée, et `etl_run_audit` / `audit_rejected_rows` n'étaient pas dessinées dans le schéma ER.
   - **Ce qui change** : Ajout de `training_run (run_id, run_timestamp, max_data_date, git_sha, mlflow_parent_run_id, is_production_active)`, de `fact_conformal_quantiles`, des contraintes `UNIQUE` composites incluant `run_id` sur `fact_forecast`, `fact_anomaly`, `fact_model_metrics_by_series` et `fact_conformal_quantiles`, ainsi que de `etl_run_audit` et `audit_rejected_rows`.
3. **Suppression de la redondance pays (FK composite marché/pays), `ref_unit_conversion` et règle de collision (`06-modele-donnees.md`, `05-conception.md`)** :
   - **Ce qui change** : `dim_series_catalog` référence `dim_market` par la FK composite `(market_code, country_iso3)`. Ajout de `ref_unit_conversion` qui ne convertit que les unités métriques (`KG`, `100 KG`, `500 G`, `70 G`, `TONNE`, `L`) et laisse intactes les unités locales/non-pondérales (`Pile`, `Head`, `Day`, `Unit`). En cas de collision après normalisation vers une même unité canonique, priorité déterministe est donnée à l'unité canonique native (`raw_unit == canonical_unit`) et le doublon est tracé dans `audit_rejected_rows` (0 collision observée dans les CSV).
4. **Remplacement de `price_flag` par `source_flag` + `is_observed`, correction du Scénario 2 et retrait de `is_lean_season` du calendrier (`04-diagrammes-sequence.md`, `06-modele-donnees.md`)** :
   - **Ce qui était faux** : Le Scénario 2 filtrait sur `price_flag = 'actual'`, excluant l'IPC Maroc (`official_faostat`), et `is_lean_season_sahel` était dans `dim_calendar` alors que la saison de soudure dépend du pays.
   - **Ce qui change** : Ajout de `is_observed BOOLEAN` (`TRUE` pour `actual` et `official_faostat`, `FALSE` pour `aggregate`), filtre corrigé en `WHERE is_ml_eligible = TRUE AND is_observed = TRUE`, et déplacement de `lean_season_months` dans `dim_country`.
5. **Détection d'anomalies unifiée ($\ge 5\text{ ans}$, résidu log-tendance-saisonnalité, $\text{MAD} \times 1{,}4826$) et validation des chocs dans le pipeline (`02-processus-bpmn.md`, `05-activite-pipeline.md`, `05-conception.md`)** :
   - **Ce qui était fragile** : Calculer une médiane/MAD par mois sur 36 mois ne donnait que 3 points par mois calendaire, et deux formules de valeur attendue coexistaient.
   - **Ce qui change** : Seuil porté à $\ge 60\text{ mois}$ (5 ans), définition unique de la valeur attendue $\hat{P}_{\text{expected}, t} = \exp(\tilde{T}_t + \tilde{S}_m)$ sur les log-prix, résidu $r_t = \ln(P_t) - \ln(\hat{P}_{\text{expected}, t})$, échelle $\hat{\sigma}_{\text{MAD}, m} = 1{,}4826 \times \text{MAD}(r_{\cdot, m})$, et ajout dans le pipeline de l'étape de validation automatique sur les chocs 2007–2008 et 2022.
6. **Sélection du champion sur Fenêtres 1–2, rapport final sur Fenêtre 3, vrai `MASE` + `RelMAE_h`, et arrêt de l'imputation des trous (`ADR-003`, `02-processus-bpmn.md`, `05-activite-pipeline.md`)** :
   - **Ce qui change** : Les mois manquants ($\le 3$ consécutifs) sont laissés à `NaN` (aucune interpolation). Le modèle champion est choisi uniquement sur les Fenêtres de validation 1 (`2022`) et 2 (`2024–2025`), et le rapport final est évalué une seule fois sur la Fenêtre 3 (`2025–2026`). Le vrai `MASE` (dénominateur *in-sample* $|y_t - y_{t-12}|$) et le ratio `RelMAE_h` sont tous deux calculés.
7. **Chiffres exacts vérifiés par script (`ADR-003`, `05-conception.md`)** :
   - **19 groupes actifs `(country_iso3, commodity_group)`** (**18 UEMOA** car `MLI` et `NER` ont 0 série éligible pour `Beans` + **1 Maroc**), soit **57 modèles par famille** et **57 runs enfants MLflow + 1 run parent = 58 runs MLflow**.
   - **Séries testables par fenêtre** : **671 séries** ($\ge 24\text{m}$ pré-2022) ou **605 séries** ($\ge 36\text{m}$ pré-2022) sur la **Fenêtre 1 (Choc 2022, 18/19 groupes)** ; **738 / 738 séries (100 %, 19/19 groupes)** sur la **Fenêtre 2 (`2024–2025`)** et sur la **Fenêtre 3 (`2025–2026`)**.
8. **Alignement Activité/BPMN, base/rôle MLflow séparés, flèche GHCR, rôle générique C4, acteur Développeur Tiers et `UC-04`/`UC-11` (`01`, `05`, `07`)** :
   - Alignement des 2 passerelles d'intégrité (`DQ-01`/`DQ-02`) entre `05-activite-pipeline.md` et `02-processus-bpmn.md` ; séparation de `agriprix_dw` et `mlflow_db` (`mlflow_user`) dans PostgreSQL ; correction du sens des flèches `GHA -> GHCR <- AgriPrix` et remplacement de « Amine » par `Administrateur Data / MLOps` dans `07-architecture-c4.md` ; ajout de l'acteur `Développeur / Système Tiers` et séparation entre le calcul batch de `is_ml_eligible` (`UC-11` inclus dans `UC-09`/`UC-12`) et sa simple lecture temps réel (`UC-04`/`UC-05`) dans `01-cas-utilisation.md`.


---

## Phase 3 — Mise en place du socle technique (Git, Docker Compose, Makefile, DevContainer, Pre-commit, CI Multi-Arch)
**Date** : 19 avril 2026

### 1. Ce que nous avons construit et pourquoi
- **Dépôt Git & Hygiène (`LICENSE`, `.gitignore`, `.gitattributes`, `.env.example`)** :
  - Initialisation du dépôt Git sur la branche `main` avec des commits atomiques au format *Conventional Commits* (`docs:`, `build:`, `feat(core):`).
  - Ajout de `.gitattributes` forçant les fins de ligne `LF` (`eol=lf`) sur tous les scripts `.sql`, `.py`, `.yml` et `Makefile` pour éviter les bugs `CRLF` entre Windows et les conteneurs Linux sous WSL2.
  - Aucun secret versionné : seul `.env.example` est suivi par Git, et `docker-compose.yml` inclut des valeurs de repli locales (`${VAR:-default}`) pour que `docker compose up` fonctionne immédiatement après un `git clone`.
- **Cloisonnement PostgreSQL 16 (`docker/postgres/01-init.sql`)** :
  - Script SQL d'initialisation automatique créant **2 bases isolées** (`agriprix_dw` et `mlflow_db`) et **3 rôles à privilèges minimaux** :
    - `agriprix_etl_writer` : droits `SELECT, INSERT, UPDATE, DELETE` sur `agriprix_dw` (utilisé uniquement par `job-runner`).
    - `agriprix_api_readonly` : droit `SELECT` exclusivement sur `agriprix_dw` (utilisé par `api` FastAPI), avec interdiction de se connecter à `mlflow_db`.
    - `mlflow_user` : propriétaire exclusif de `mlflow_db` (utilisé par `mlflow`), avec interdiction de se connecter à `agriprix_dw`.
- **Conteneurisation légère & Budget RAM (`docker/Dockerfile`, `docker-compose.yml`)** :
  - Image unique `python:3.11-slim` exécutée sous utilisateur non-root `agriprix (UID 1000)` avec `libgomp1` (requis par LightGBM).
  - Limites strictes dans `docker-compose.yml` : `db` (`512m`), `mlflow` (`512m`), `api` (`512m`), `dashboard` (`512m`), et `job-runner` éphémère sous profil `jobs` (`1280m`), maintenant l'ensemble à **2,0 Go au repos et 3,25 Go en pic** (< 4 Go).
  - Volumes nommés `agriprix_pgdata` et `agriprix_mlflow_artifacts` pour la performance native Linux ext4 sous WSL2.
- **Outillage Développeur & CI/CD (`Makefile`, `.devcontainer/devcontainer.json`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`)** :
  - `Makefile` exposant `make up`, `down`, `ps`, `logs`, `lint`, `format`, `test`, `etl`, `train`, `clean` (100 % exécutés dans Docker).
  - Workflow GitHub Actions exécutant `ruff check`, `ruff format --check`, `pytest --cov=src --cov-fail-under=70`, le test de démarrage `docker compose up -d` + `/api/v1/health`, et la vérification du build multi-architecture (`linux/amd64,linux/arm64`) via QEMU et Docker Buildx.
- **Squelette applicatif & Smoke Tests (`src/`, `tests/test_smoke.py`, `README.md`)** :
  - Squelettes fonctionnels pour `src/config.py`, `src/api/main.py` (`/api/v1/health`), `src/dashboard/app.py`, `src/etl/cli.py`, `src/ml/cli.py` et suite de tests `tests/test_smoke.py` vérifiant notamment l'isolation des rôles SQL.

### 2. Ce qui a été exécuté et le blocage rencontré sur le démon Docker Desktop
- **Validation syntaxique** : `docker compose config -q` passe avec succès (`Exit code: 0`).
- **Blocage lors du démarrage du moteur Docker (`npipe:////./pipe/dockerDesktopLinuxEngine`)** :
  - Le service Windows `com.docker.service` est à l'état `Stopped (Manual)` et la distribution WSL `docker-desktop` est `Stopped`.
  - La commande `docker desktop start` lancée depuis le terminal isolé de l'agent ne peut pas maintenir le processus graphique `Docker Desktop.exe` actif ni élever les privilèges Windows (`UAC`) pour démarrer `com.docker.service`.
  - **Action requise** : Amine doit lancer **Docker Desktop** depuis sa session Windows (menu Démarrer) pour que nous puissions exécuter `docker compose up -d --build`, `make lint` et `make test` en conditions réelles avant de valider la Phase 3.
