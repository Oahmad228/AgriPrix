# Phase 0 — Audit et Sélection des Sources de Données (Version révisée)

> **Note pédagogique (Lexique intégré)** : Chaque terme technique ou sigle utilisé pour la première fois est accompagné d'une explication simple en une phrase.

---

## 1. Démarche d'audit : vérification réelle avant engagement

Conformément à notre règle d'ingénierie (*« Ne jamais deviner, vérifier la disponibilité, la licence et le schéma avant de s'engager »*), nous avons interrogé directement en ligne de commande les serveurs de **HDX** (*Humanitarian Data Exchange*, portail de données ouvertes humanitaires de l'ONU propulsé par le logiciel de catalogue **CKAN** — *Comprehensive Knowledge Archive Network*) et de **FAOSTAT** (*base statistique de la FAO*), puis analysé l'intégralité des fichiers téléchargés à l'aide d'un script d'audit.

### 1.1 Commandes exécutées et découvertes techniques majeures

1. **Vérification des jeux de données WFP sur HDX et comportement du pare-feu AWS WAF** :
   - `wfp-food-prices-for-morocco` $\rightarrow$ **Introuvable (`HTTP 404`)**. Le PAM ne publie pas de relevés par marché local pour le Maroc.
   - `wfp-food-prices-for-senegal`, `mali`, `burkina-faso`, `niger`, `cote-d-ivoire` $\rightarrow$ **Disponibles (`HTTP 200 OK`)**, totalisant exactement **324 040 lignes**.
   - **Constat d'exploitation important (AWS WAF)** : Au-delà de 6 à 7 téléchargements massifs de fichiers CSV en moins de 3 minutes depuis la même adresse IP, la route `/download/` de `data.humdata.org` renvoie un code **`HTTP 202 Accepted` vide (`Content-Length: 0`) avec l'en-tête `x-amzn-waf-action: challenge`** (*mécanisme anti-robot d'Amazon Web Services qui bloque temporairement les téléchargements en rafale*). En revanche, espacer les 5 téléchargements de 2 secondes en utilisant un cache local fonctionne sans blocage, et l'API **HDX HAPI** (`https://hapi.humdata.org/api/v1/food/food-price`) reste accessible sans restriction pour les données récentes (2017–2026).
2. **Vérification des sources FAOSTAT pour le Maroc (Séparation Mensuel/Indice vs Annuel/Prix)** :
   - L'API directe `fenixservices.fao.org` a renvoyé une **erreur `521`** (serveur d'origine indisponible derrière Cloudflare).
   - Les archives officielles sur **Amazon S3** (`https://bulks-faostat.fao.org/production/`) ont répondu immédiatement (`HTTP 200 OK`) :
     - `ConsumerPriceIndices_E_Africa.zip` (370 Ko) : contient `ConsumerPriceIndices_E_Africa_NOFLAG.csv`, où le Maroc (`Area Code = 143`) compte **36 lignes larges** correspondant à **3 indicateurs mensuels × 12 mois**, soit exactement **942 observations mensuelles dépivotées** (2000–2026).
     - `Prices_E_Africa.zip` (1,46 Mo) : contient `Prices_E_Africa_NOFLAG.csv`, où le Maroc compte **367 lignes larges (séries annuelles)**, soit **8 942 observations annuelles dépivotées** (1991–2025).

---

## 2. Architecture de sources : Modélisation Multi-Grains, Multi-Fréquences et Multi-Types

Pour empêcher toute confusion méthodologique entre un prix mensuel de marché en franc CFA, un indice mensuel national sans devise et un prix producteur annuel en dirham par tonne, notre modèle de données impose **trois colonnes discriminantes obligatoires** sur chaque série et chaque observation :

1. **`granularity_level`** (*niveau de détail géographique*) : `'MARKET'` (marché local) ou `'NATIONAL'` (pays entier).
2. **`frequency`** (*fréquence temporelle de collecte*) : `'MONTHLY'` (mensuelle) ou `'ANNUAL'` (annuelle). **Aucun mois fictif (`YYYY-MM-15`) n'est jamais inventé pour une donnée annuelle** (qui est rattachée à son année `reference_year`).
3. **`value_type`** (*nature mathématique de la valeur*) : `'PRICE'` (prix monétaire exprimé dans une devise et une unité physique, ex. `XOF/KG` ou `MAD/tonne`), `'INDEX'` (indice sans devise par rapport à une année de base, ex. `Index (2015=100)`), ou `'INFLATION_RATE'` (taux de variation en `%`).

| Caractéristique | Source n°1 : WFP sur HDX (Afrique de l'Ouest) | Source n°2A : FAOSTAT IPC (Maroc Mensuel) | Source n°2B : FAOSTAT Prix Producteurs (Maroc Annuel) |
| :--- | :--- | :--- | :--- |
| **Pays couverts** | **5 pays UEMOA** : `SEN`, `MLI`, `BFA`, `NER`, `CIV` | **Maroc (`MAR`)** | **Maroc (`MAR`)** |
| **`granularity_level`** | **`'MARKET'`** | **`'NATIONAL'`** | **`'NATIONAL'`** |
| **`frequency`** | **`'MONTHLY'`** (date `YYYY-MM-15`) | **`'MONTHLY'`** (année + mois `January..December`) | **`'ANNUAL'`** (année `reference_year` seule, sans mois inventé) |
| **`value_type`** | **`'PRICE'`** | **`'INDEX'`** (et `'INFLATION_RATE'`) | **`'PRICE'`** (et `'INDEX'` producteur) |
| **Unité & Devise (`unit` / `currency_code`)** | `KG`, `100 KG`, `L` en **`XOF`** | `'Index (2015=100)'` (devise `NULL`, sans unité monétaire) | `'MAD/tonne'` en **`MAD`** (`LCU/tonne`) |
| **Éligibilité Prévisions 1, 3 et 6 mois** | **OUI** (uniquement si `priceflag='actual'` et continuité stricte $\ge 60$ mois) | **OUI** (série `23013` : *Food Indices 2015=100*, 318 mois continus) | **NON (`is_ml_eligible = FALSE`)** : consultable en historique uniquement |

---

## 3. Audit détaillé de la Source n°1 : WFP Food Prices (Afrique de l'Ouest)

### 3.1 Volumétrie exacte et audit de la colonne `priceflag` (Point 4)
Le champ `priceflag` indique comment le prix a été obtenu par le PAM (`actual` = relevé réel sur le marché, `aggregate` = moyenne calculée à partir de plusieurs relevés ou sous-marchés). Afin de **ne jamais entraîner un modèle de prévision sur la sortie d'une agrégation ou d'un autre modèle**, nous avons audité les valeurs exactes de `priceflag` et de `pricetype` sur les **324 040 lignes** :

| Pays | Code ISO3 | Lignes totales | `priceflag = 'actual'` | `priceflag = 'aggregate'` | Autres `priceflag` (`estimate`/`forecast`) | Répartition `pricetype` (`Retail` vs `Wholesale`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Sénégal** | `SEN` | **54 039** | 54 039 (**100,00 %**) | 0 (0,00 %) | 0 | `Retail`: 54 039 (100 %) |
| **Mali** | `MLI` | **132 286** | 132 286 (**100,00 %**) | 0 (0,00 %) | 0 | `Retail`: 132 286 (100 %) |
| **Burkina Faso** | `BFA` | **58 203** | 58 203 (**100,00 %**) | 0 (0,00 %) | 0 | `Retail`: 53 781 (92,4 %) / `Wholesale`: 4 422 (7,6 %) |
| **Niger** | `NER` | **68 699** | 68 699 (**100,00 %**) | 0 (0,00 %) | 0 | `Retail`: 65 308 (95,1 %) / `Wholesale`: 3 391 (4,9 %) |
| **Côte d'Ivoire** | `CIV` | **10 813** | 6 759 (**62,51 %**) | **4 054 (37,49 %)** | 0 | `Retail`: 10 813 (100 %) |
| **TOTAL UEMOA** | **5 pays** | **324 040** | **319 986 (98,75 %)** | **4 054 (1,25 %)** | **0 (0,00 %)** | **`Retail`: 316 227 (97,6 %) / `Wholesale`: 7 813 (2,4 %)** |

> **Constat critique sur la Côte d'Ivoire (`CIV`) et règle d'exclusion** :
> En Côte d'Ivoire, le PAM a étiqueté ses relevés en `actual` de janvier 2005 à mars 2020 (puis de juin à septembre 2026), mais a basculé l'intégralité des relevés entre **avril 2020 et mai 2026** sous l'étiquette **`priceflag = 'aggregate'`** (4 054 lignes).
> Conformément à notre règle d'hygiène scientifique (**exclure de l'entraînement toute valeur `priceflag != 'actual'`**), ces 4 054 lignes `aggregate` sont chargées dans l'entrepôt pour la consultation historique (avec un badge d'avertissement) mais **exclues du Machine Learning**. Cela crée un trou d'observations `actual` entre avril 2020 et mai 2026 pour la Côte d'Ivoire, qui ne compte donc **0 série éligible aux prévisions ML** sous notre règle de continuité récente. Ce fait réel est assumé et documenté dans l'interface.

---

## 4. Audit détaillé de la Source n°2 : FAOSTAT (Maroc — Grain National)

L'inspection complète des deux archives FAOSTAT pour `Area = "Morocco"` (`Area Code = 143`) donne la répartition exacte suivante entre **séries (lignes larges)** et **observations (lignes dépivotées)** :

| Archive FAOSTAT | Fichier CSV inspecté | Indicateur (`Item Code` / `Element Code`) | `frequency` | `value_type` | `unit` | Séries (lignes larges) | Observations dépivotées | Éligible Prévision 1/3/6 mois ? |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `ConsumerPriceIndices_E_Africa.zip` | `ConsumerPriceIndices_E_Africa_NOFLAG.csv` | **`23013` — Consumer Prices, Food Indices (2015 = 100)** | `'MONTHLY'` | `'INDEX'` | `'Index (2015=100)'` | **1 série** (12 lignes mois) | **318 mois** (`2000-01` à `2026-06`, 0 trou) | **OUI (Unique série ML du Maroc)** |
| `ConsumerPriceIndices_E_Africa.zip` | `ConsumerPriceIndices_E_Africa_NOFLAG.csv` | `23012` — Consumer Prices, General Indices (2015 = 100) | `'MONTHLY'` | `'INDEX'` | `'Index (2015=100)'` | 1 série (12 lignes mois) | 318 mois (`2000-01` à `2026-06`) | Non (contexte macro général) |
| `ConsumerPriceIndices_E_Africa.zip` | `ConsumerPriceIndices_E_Africa_NOFLAG.csv` | `23014` — Food price inflation | `'MONTHLY'` | `'INFLATION_RATE'` | `'%'` | 1 série (12 lignes mois) | 306 mois (`2001-01` à `2026-06`) | Non (dérivé de l'indice `23013`) |
| `Prices_E_Africa.zip` | `Prices_E_Africa_NOFLAG.csv` | `5530` — Producer Price (`LCU/tonne` = `MAD/tonne`) + `5531`/`5532`/`5539` | **`'ANNUAL'`** | `'PRICE'` (`MAD/tonne`) & `'INDEX'` | `'MAD/tonne'` / `'Index'` | **367 séries annuelles** | **8 942 observations annuelles** (`1991`–`2025`) | **NON (Annuel : consultation seule)** |

---

## 5. Définition d'une Série, Justification du Seuil de 60 Mois et Couverture Réelle (Points 2 & 3)

### 5.1 Définition formelle de la clé d'une série temporelle
Une **série temporelle unique** dans AgriPrix Observatory est identifiée par la clé composite à 6 attributs métier (complétée par `frequency` et `value_type`) :
$$\text{Clé Série} = (\texttt{country\_iso3}, \texttt{market\_id}, \texttt{commodity\_id}, \texttt{pricetype}, \texttt{unit}, \texttt{currency\_code})$$
- **Pourquoi inclure `pricetype` (`Retail` vs `Wholesale`) et `unit` (`KG` vs `100 KG`) dans la clé ?** Parce qu'au Burkina Faso et au Niger, un même marché (ex. Sankaryaré à Ouagadougou) relève le même mois le prix du mil au détail (`Retail` en `KG`) et en gros (`Wholesale` en `100 KG`). Ne pas les inclure dans la clé de série et de déduplication fusionnerait un sac de 100 kg avec 1 kg !
- **Affichage par défaut** : Le dashboard Streamlit filtre par défaut sur **`pricetype = 'Retail'`** (prix de détail payé par les ménages).

### 5.2 Pourquoi 36 mois ne suffisent pas, et justification du seuil de 60 mois continus récents
Dans notre version initiale, nous avions proposé un seuil naïf de « $\ge 36$ observations au total ». Ce seuil présente **deux failles rédhibitoires** :
1. **Insuffisance mathématique pour combiner saisonnalité annuelle + horizon 6 mois + validation chronologique** :
   - La construction des variables saisonnières (`lag_12`, moyenne glissante sur 12 mois) consomme les **12 premiers mois** de la série.
   - La cible à l'horizon $h = 6\text{ mois}$ ($y_{t+6}$) consomme **6 mois** supplémentaires.
   - Une évaluation sérieuse sans fuite du futur exige au moins **12 mois de validation chronologique** (1 cycle saisonnier complet pour choisir les hyperparamètres et calibrer les intervalles d'incertitude) et **12 mois de test final hors-échantillon** (1 cycle saisonnier complet pour mesurer l'erreur sur les 4 saisons).
   - **Bilan arithmétique** : Avec 36 mois au total, une fois retirés $12\text{ mois (lags)} + 12\text{ mois (validation)} + 12\text{ mois (test)}$, il reste **$36 - 36 = 0\text{ mois}$ pour entraîner le modèle** ! Pour que le modèle dispose d'au moins **2 cycles saisonniers complets d'entraînement effectif ($\ge 24\text{ mois}$)** après création du `lag_12`, il faut au minimum :
     $$12\text{ (lags)} + 24\text{ (entraînement : 2 ans)} + 12\text{ (validation : 1 an)} + 12\text{ (test : 1 an)} = \mathbf{60\text{ mois (5 ans)}}$$
2. **Absence de garantie de continuité récente** :
   - Sur les 1 718 séries du panier ayant $\ge 36$ observations n'importe quand depuis 1990, près de **970 séries sont soit arrêtées depuis plusieurs années** (parfois dès 2014), soit coupées par des interruptions de collecte de 1 à 5 ans !

### 5.3 Règle stricte d'éligibilité au Machine Learning (`is_ml_eligible = TRUE`)

> **Mise à jour Sprint 1 (2026-11-10)** : la règle d'éligibilité de la section 5.3 (seuil fixe « ≥ janvier 2024 » et interpolation des trous) a été **remplacée** en Phase 2 par la règle de fraîcheur relative, **sans aucune interpolation** ([`05-conception.md`](05-conception.md) §2.2), qui est celle implémentée dans `src/etl/eligibility.py`. Le comptage de 746 séries ci-dessous correspond à l'ancienne règle.

Une série est marquée `is_ml_eligible = TRUE` si et seulement si elle vérifie simultanément les **5 critères stricts** suivants :
1. `frequency == 'MONTHLY'` (exclut les séries annuelles FAOSTAT du Maroc) ;
2. `priceflag == 'actual'` uniquement (exclut toute ligne `aggregate`, estimée ou imputée) ;
3. Produit appartenant au panier de sécurité alimentaire (ou `Item 23013` IPC Alimentaire pour le Maroc) ;
4. **Série active récemment** : dernière observation valide datée d'**au moins janvier 2024** ($\ge \text{2024-01-15}$) ;
5. **Fenêtre continue récente d'au moins 60 mois observés** au sein de laquelle le **nombre maximal de mois manquants consécutifs est $\le 3$ mois (`max_consecutive_missing_months <= 3`)** (les trous isolés de 1 à 3 mois à l'intérieur de la fenêtre passée sont comblés par interpolation linéaire causale uniquement sur le passé connu, jamais à cheval sur la coupure train/test).

### 5.4 Tableau de couverture réel vérifié par Pays, Marchés et Produits
Voici le résultat exact du programme d'audit exécuté sur les **324 040 lignes WFP** et les **9 884 observations FAOSTAT Maroc** :

| Pays | Famille de Produit / Indicateur | Marchés totaux (Panier) | Séries totales (`actual`) | Ancienne règle naïve ($\ge 36$ obs. n'importe quand) | Règle stricte $\ge 60$ mois (`gap <= 2`, actif $\ge 2024$) | **Règle stricte retenue $\ge 60$ mois (`gap <= 3`, actif $\ge 2024`)** | Dont `Retail` (Détail) éligibles |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Sénégal (`SEN`)** | Riz (*Rice*) | 67 | 221 | 131 | 15 | **20** | **20** |
| **Sénégal (`SEN`)** | Maïs (*Maize*) | — | 125 | 85 | 8 | **9** | **9** |
| **Sénégal (`SEN`)** | Mil (*Millet*) | — | 67 | 55 | 8 | **9** | **9** |
| **Sénégal (`SEN`)** | Sorgho (*Sorghum*) | — | 111 | 62 | 0 | **3** | **3** |
| **Sénégal (`SEN`)** | Niébé (*Beans*) | — | 58 | 43 | 6 | **9** | **9** |
| *Sous-total `SEN`* | *5 familles actives (9 marchés éligibles)* | *67* | *582* | *376* | *37* | ***50*** | ***50*** |
| **Mali (`MLI`)** | Riz (*Rice*) | 137 | 341 | 187 | 65 | **77** | **77** |
| **Mali (`MLI`)** | Mil (*Millet*) | — | 136 | 105 | 45 | **53** | **53** |
| **Mali (`MLI`)** | Maïs (*Maize*) | — | 123 | 67 | 47 | **50** | **50** |
| **Mali (`MLI`)** | Sorgho (*Sorghum*) | — | 126 | 80 | 46 | **50** | **50** |
| **Mali (`MLI`)** | Niébé, Blé, Sucre, Huile *(arrêtés $< 2024$ ou trou $> 3$ mois)* | — | 575 | 170 | 0 | **0** | **0** |
| *Sous-total `MLI`* | *4 céréales actives (65 marchés éligibles)* | *137* | *1 301* | *609* | *203* | ***230*** | ***230*** |
| **Burkina Faso (`BFA`)** | Riz (*Rice*) | 66 | 89 | 79 | 58 | **61** | **61** |
| **Burkina Faso (`BFA`)** | Niébé (*Beans*) | — | 64 | 63 | 57 | **58** | **58** |
| **Burkina Faso (`BFA`)** | Mil (*Millet*) | — | 72 | 70 | 54 | **55** | **55** |
| **Burkina Faso (`BFA`)** | Sorgho (*Sorghum*) | — | 72 | 69 | 54 | **54** | **54** |
| **Burkina Faso (`BFA`)** | Maïs (*Maize*) | — | 58 | 54 | 48 | **50** | **50** |
| *Sous-total `BFA`* | *5 familles actives (60 marchés éligibles)* | *66* | *355* | *335* | *271* | ***278*** | ***278*** |
| **Niger (`NER`)** | Riz (*Rice*) | 79 | 121 | 85 | 49 | **52** | **52** |
| **Niger (`NER`)** | Mil (*Millet*) | — | 85 | 74 | 45 | **48** | **48** |
| **Niger (`NER`)** | Sorgho (*Sorghum*) | — | 84 | 72 | 42 | **45** | **45** |
| **Niger (`NER`)** | Maïs (*Maize*) | — | 77 | 66 | 38 | **42** | **42** |
| **Niger (`NER`)** | Niébé, Blé, Huile *(trous $> 3$ mois)* | — | 146 | 60 | 0 | **0** | **0** |
| *Sous-total `NER`* | *4 céréales actives (50 marchés éligibles)* | *79* | *513* | *357* | *174* | ***187*** | ***187*** |
| **Côte d'Ivoire (`CIV`)** | Maïs, Riz, Huile, Niébé *(basculés en `aggregate` de 2020 à mai 2026)* | 17 | 90 | 41 | 0 | **0** *(Consultation historique)* | **0** |
| **Maroc (`MAR`)** | **IPC Alimentaire (`23013`, base 2015=100, Mensuel)** | National (1) | 1 | 1 | 1 (318 mois, 0 trou) | **1** | N/A (`INDEX`) |
| **Maroc (`MAR`)** | Prix producteurs agricoles (`5530`, `MAD/tonne`, Annuel) | National (1) | 367 (annuelles) | N/A (Annuel) | 0 | **0** *(Consultation historique)* | N/A (`ANNUAL`) |
| **TOTAL PROJET** | **Panier Sécurité Alimentaire + IPC Maroc** | **366 marchés + 1 national** | **2 842 mensuelles (+ 367 annuelles)** | **1 719** | **686** | **746 séries éligibles ML** | **745 `Retail` UEMOA + 1 `INDEX` Maroc** |

> **Enseignement majeur de ce tableau réel** :
> 1. Sur les **745 séries UEMOA éligibles** à la prévision, **100 % sont des séries de prix de détail (`pricetype = 'Retail'`) en `KG` et en `XOF`** (les séries `Wholesale` au Burkina Faso et au Niger comportent des interruptions de collecte supérieures à 3 mois et restent donc en consultation historique).
> 2. Les produits qui passent le filtre de continuité stricte sur le terrain ouest-africain sont les **5 piliers céréaliers et protéiques** : **Riz (`210 séries`), Mil (`165 séries`), Maïs (`151 séries`), Sorgho (`152 séries`) et Niébé (`67 séries`)**, tandis que le Blé, le Sucre et l'Huile restent consultables en historique mais trop discontinus récemment pour être prévus sérieusement à 6 mois.

---

## 6. Analyse juridique des licences et droits de valorisation

| Source | Licence officielle exacte | Usage public (GitHub / Démo en ligne) | Usage commercial (Mission ONG, SaaS, Concours) | Conditions obligatoires à respecter dans AgriPrix Observatory |
| :--- | :--- | :---: | :---: | :--- |
| **WFP sur HDX** (`wfp-food-prices-for-*`) | **CC BY-IGO 3.0** (*Creative Commons Attribution for Intergovernmental Organisations*) | **Autorisé** | **Autorisé** | 1. **Attribution** : Mentionner *« Source : World Food Programme (WFP) via Humanitarian Data Exchange (HDX), sous licence CC BY-IGO 3.0 »*.<br>2. **Modifications** : Indiquer que les nettoyages, anomalies et prévisions sont calculés par *AgriPrix Observatory*.<br>3. **Pas de parrainage implicite** : Ne pas suggérer que l'ONU certifie nos prévisions. |
| **FAOSTAT** (`bulks-faostat.fao.org`) | **CC BY 4.0** (*Creative Commons Attribution 4.0 International*) | **Autorisé** | **Autorisé** | 1. **Attribution** : Mentionner *« Source : FAOSTAT, FAO, sous licence CC BY 4.0 »*.<br>2. **Lien vers la licence** et mention des transformations effectuées. |
| **Code source d'AgriPrix Observatory** | **MIT License** | **Autorisé** | **Autorisé** | Conservation de la notice de droit d'auteur d'Amine dans le fichier `LICENSE`. |
