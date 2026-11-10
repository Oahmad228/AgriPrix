# 05 — Analyse et Conception Technique & Méthodologique (Phase 2 — Révisée)

> **Projet** : AgriPrix Observatory  
> **Phase** : Phase 2 — Analyse et conception (Version consolidée après revue d'ingénierie en Phase 3)  
> **Auteurs** : Amine & Ingénieur Logiciel/Data Junior  
> **Date de dernière mise à jour** : 2026-11-03  

---

## 0. Glossaire des nouveaux termes introduits en Phase 2 (en une phrase simple)

- **BPMN 2.0 (*Business Process Model and Notation*)** : La norme graphique internationale permettant de modéliser un processus métier étape par étape dans des couloirs attribués à chaque acteur ou composant logiciel.
- **Modèle C4 (*Context, Containers, Components, Code*)** : Une méthode de schématisation d'architecture logicielle fonctionnant par niveaux de zoom successifs (du contexte global jusqu'aux conteneurs Docker et au code).
- **MCD / MLD / MPD (Méthode Merise)** : Les trois niveaux successifs de conception d'une base de données : Conceptuel (entités métier), Logique (tables relationnelles et clés) et Physique (types SQL exacts, contraintes et index sous PostgreSQL).
- **Clé étrangère composite (*Composite Foreign Key*)** : Une contrainte relationnelle portant sur deux colonnes simultanément (ex. `(series_id, frequency)` ou `(market_code, country_iso3)`) qui garantit qu'une table enfant ne peut jamais associer un marché au mauvais pays ni une série mensuelle à une période annuelle.
- **Règle de fraîcheur relative (*Relative Freshness Rule*)** : Un critère d'éligibilité qui vérifie qu'une série a été observée dans les 3 derniers mois précédant la date maximale disponible dans le fichier source du pays ($\text{last\_obs} \ge \max(\text{date\_pays}) - 3\text{ mois}$).
- **MASE (*Mean Absolute Scaled Error*) vs `RelMAE` (*Relative MAE*)** : Deux métriques d'évaluation : le vrai **MASE** (Hyndman & Koehler) divise l'erreur de test par l'erreur saisonnière *in-sample* ($|y_t - y_{t-12}|$ sur l'entraînement), tandis que le **`RelMAE`** divise l'erreur de test du modèle à l'horizon $h$ par l'erreur de test de la baseline naïve saisonnière sur la même fenêtre.
- **Échangeabilité (*Exchangeability*)** : L'hypothèse statistique selon laquelle les erreurs futures se comportent comme les erreurs passées de la fenêtre de calibration — hypothèse rompue temporairement lors d'un choc inédit comme en 2022.
- **Facteur de consistance normale du MAD ($1{,}4826$)** : La constante mathématique par laquelle on multiplie l'écart absolu médian (**MAD**) pour qu'il soit directement comparable à un écart-type gaussien ($\sigma$) tout en restant insensible aux valeurs extrêmes passées.

---

## 1. Vue d'ensemble des livrables de la Phase 2

Conformément à la contrainte n°6, tous les diagrammes sont écrits en code **Mermaid** dans [`docs/diagrams/`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams) et accompagnés d'un guide **« Comment le lire »** et de **2 questions de recruteur avec réponses**. Les choix d'architecture et de modélisation sont justifiés dans 7 **ADR** sous [`docs/adr/`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/adr).

### 1.1 Répertoire des Diagrammes ([`docs/diagrams/`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams))

| Réf. | Fichier | Type de diagramme | Ce qu'il modélise |
| :---: | :--- | :--- | :--- |
| **D-01** | [`01-cas-utilisation.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/01-cas-utilisation.md) | UML Cas d'utilisation | Les 5 acteurs (Personas **Fatou**, **Youssef** et **Moussa**, **Développeur / Système Tiers**, Planificateur) et 13 cas d'utilisation (`UC-04` lisant le drapeau pré-calculé `is_ml_eligible` sans relancer `UC-11`). |
| **D-02** | [`02-processus-bpmn.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/02-processus-bpmn.md) | BPMN 2.0 (Couloirs Mermaid) | 3 processus métier : (1) ETL avec 2 passerelles d'intégrité (`DQ-01`/`DQ-02`) et `ref_unit_conversion`, (2) Prévision ML sur 19 groupes (sélection sur Fenêtres 1–2, rapport sur Fenêtre 3, sans imputation), (3) Anomalies ($\ge 5\text{ ans}$, résidu log-tendance-saisonnalité, $\text{MAD} \times 1{,}4826$ ; validation des chocs historiques déportée en test CI `pytest`). |
| **D-03** | [`03-diagramme-classes.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/03-diagramme-classes.md) | UML Classes du domaine | Le modèle objet aligné sur l'entrepôt : `RefUnitConversion`, `TrainingRun`, `ConformalQuantiles`, `EtlRunAudit`, `AuditRejectedRow`, `SourceFlag` + `is_observed`. |
| **D-04** | [`04-diagrammes-sequence.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/04-diagrammes-sequence.md) | UML Séquence (x3) | Chronologie exacte des appels pour : (1) `make etl`, (2) `make train` avec filtre `WHERE is_ml_eligible = TRUE AND is_observed = TRUE` (incluant l'IPC Maroc) et base `mlflow_db` isolée, (3) Requête client `Streamlit / Tiers -> FastAPI -> PostgreSQL RO`. |
| **D-05** | [`05-activite-pipeline.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/05-activite-pipeline.md) | UML Activité | Pipeline de bout en bout aligné sur le BPMN (2 passerelles d'intégrité, 5 portes d'éligibilité ML $\rightarrow$ 738 séries dans 19 groupes ; validation *a priori* des 5 crises historiques en test CI). |
| **D-06** | [`06-modele-donnees.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/06-modele-donnees.md) | Merise MCD/MLD & MPD Étoile | Schéma en étoile sous PostgreSQL 16 avec FK composites `(series_id, frequency)`, `(calendar_id, frequency)` et `(market_code, country_iso3)`, `ref_unit_conversion`, `training_run`, `fact_conformal_quantiles`, `etl_run_audit`, `audit_rejected_rows`. |
| **D-07** | [`07-architecture-c4.md`](file:///C:/Users/Oahma/.gemini/antigravity/scratch/agriprix-observatory/docs/diagrams/07-architecture-c4.md) | C4 (C1 Contexte + C2 Conteneurs) | Contexte (Personas `Fatou`, `Youssef`, `Moussa`, licences `CC BY-IGO 3.0` WFP / `CC BY 4.0` FAOSTAT, 366 marchés du panier dont 183 éligibles ML, flux `GHA -> GHCR <- AgriPrix`) et Conteneurs (séparation `agriprix_dw` vs `mlflow_db`, MVP $\le 3{,}25\text{ Go}$ RAM vs Bonus Sprint 5). |

---

## 2. Modèle de Données, Normalisation des Unités et Périmètre ML

### 2.1 Règles d'intégrité du schéma en étoile (`agriprix_dw`)
1. **Suppression de la redondance temporelle et FK composites sur `fact_price_observation`** :
   - `reference_year` et `reference_month` (`NULL` si `ANNUAL`) n'existent que dans `dim_calendar` (`calendar_id = YYYYMM` si mensuel, `YYYY00` si annuel).
   - `fact_price_observation` porte `frequency` et deux **clés étrangères composites** : `(series_id, frequency) -> dim_series_catalog` et `(calendar_id, frequency) -> dim_calendar`, avec unicité `UNIQUE (series_id, calendar_id, source_flag)`.
   - `lean_season_months` est rattaché à `dim_country` et retiré de `dim_calendar`.
2. **Suppression de la redondance géographique** :
   - `dim_series_catalog` référence `dim_market` par la **FK composite `(market_code, country_iso3)`**.
3. **Remplacement de `price_flag` par `source_flag` + `is_observed`** :
   - `source_flag` vaut `'actual'`, `'official_faostat'` ou `'aggregate'`.
   - `is_observed` vaut `TRUE` pour `'actual'` et `'official_faostat'` (et `FALSE` pour `'aggregate'`), permettant au filtre `WHERE is_ml_eligible = TRUE AND is_observed = TRUE` de retenir les 737 séries UEMOA **et** l'IPC du Maroc.
4. **Table `ref_unit_conversion` et règle de collision après normalisation** :
   - **Unités métriques convertibles (`is_metric_convertible = TRUE`)** : `'KG'` ($\times 1{,}0$), `'100 KG'` ($\times 0{,}01 \rightarrow \text{'KG'}$), `'500 G'` ($\times 2{,}0 \rightarrow \text{'KG'}$), `'70 G'` ($\times 14{,}285714 \rightarrow \text{'KG'}$), `'TONNE'` ($\times 0{,}001 \rightarrow \text{'KG'}$ ou conservé en `'TONNE'` pour les séries annuelles producteur), `'L'` ($\times 1{,}0$).
   - **Unités locales ou non-pondérales (`is_metric_convertible = FALSE`, non converties)** : `'Pile'` (546 lignes), `'Head'` (6 144 lignes), `'Day'` (4 036 lignes), `'Unit'` (1 212 lignes) conservent `canonical_unit = raw_unit`.
   - **Règle en cas de collision après normalisation** : si deux relevés d'un même `(series_id, calendar_id, source_flag)` proviennent d'unités brutes différentes (ex. `'KG'` et `'100 KG'`), l'ETL conserve en priorité le relevé exprimé dans l'unité canonique native (`raw_unit == canonical_unit`) et verse le doublon dans `audit_rejected_rows` (`reason_code = 'UNIT_NORMALIZATION_COLLISION'`). *(Audit empirique : 0 collision sur les 324 040 lignes WFP).*
5. **Versionnement via `training_run`, `fact_conformal_quantiles` et tables d'audit ETL** :
   - Toute campagne ML est enregistrée dans `training_run (run_id, run_timestamp, max_data_date, git_sha, mlflow_parent_run_id, is_production_active)`.
   - Clés d'unicité explicites :
     - `fact_forecast` : `UNIQUE (run_id, series_id, origin_calendar_id, horizon_months)`
     - `fact_anomaly` : `UNIQUE (run_id, series_id, calendar_id)`
     - `fact_model_metrics_by_series` : `UNIQUE (run_id, series_id, model_name, horizon_months, eval_window)`
     - `fact_conformal_quantiles` : `UNIQUE (run_id, country_iso3, commodity_group, model_name, horizon_months, eval_window)`
   - Les tables `etl_run_audit` et `audit_rejected_rows` font partie intégrante du schéma.

---

### 2.2 Chiffres exacts vérifiés : 738 séries éligibles, 19 groupes, 58 runs MLflow et séries testables par fenêtre

> **Mise à jour Sprint 1 (2026-11-10)** : les 738 séries de ce tableau sont **reproduites à l'unité** par l'ETL sur les fichiers de l'audit (`make reconcile`). Sur les fichiers HDX mis à jour au 2026-11-10, le même code trouve **782 séries** (BFA 278, MLI 264, NER 196, SEN 43, MAR 1). La série IPC Maroc `23013` compte 234 mois observés (2007–2026) : les valeurs imputées de 2000–2006 sont exclues ([`ADR-009`](adr/009-drapeaux-qualite-sources-et-tracabilite-des-versions.md)).


Avec nos critères stricts (`frequency = 'MONTHLY'`, `is_observed = TRUE`, panier sécurité alimentaire en `Retail` ou IPC `23013` Maroc, fraîcheur relative $\text{last\_obs} \ge \max(\text{date\_pays}) - 3\text{ mois}$, segment continu $\ge 60\text{ mois}$ avec au plus 3 mois manquants consécutifs **laissés à `NaN`**) :

| Pays | Groupes actifs `(country_iso3, commodity_group)` | Total Séries Éligibles | Testables sur **Fenêtre 1 (`VAL_W1_2022` : $T=\text{2021-12-15}$)** ($\ge 24\text{m}$ / $\ge 36\text{m}$ pré-2022) | Testables sur **Fenêtre 2 (`VAL_W2_24_25` : $T=\text{2024-06-15}$)** | Testables sur **Fenêtre 3 (`TEST_W3_25_26` : $T=\text{2025-08-15}$)** |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Sénégal (`SEN`)** | **5 groupes** : `Rice` (18), `Maize` (8), `Millet` (8), `Beans` (8), `Sorghum` (3) | **45** | **28** ($\ge 24\text{m}$) / **22** ($\ge 36\text{m}$) *(les 8 séries `Beans` démarrent en `2020-07`)* | **45 / 45** | **45 / 45** |
| **Mali (`MLI`)** | **4 groupes** : `Rice` (77), `Millet` (53), `Maize` (50), `Sorghum` (50) | **230** | **223** ($\ge 24\text{m}$) / **173** ($\ge 36\text{m}$) | **230 / 230** | **230 / 230** |
| **Burkina Faso (`BFA`)** | **5 groupes** : `Rice` (58), `Beans` (58), `Millet` (55), `Sorghum` (54), `Maize` (50) | **275** | **247** ($\ge 24\text{m}$) / **247** ($\ge 36\text{m}$) | **275 / 275** | **275 / 275** |
| **Niger (`NER`)** | **4 groupes** : `Rice` (52), `Millet` (48), `Sorghum` (45), `Maize` (42) | **187** | **172** ($\ge 24\text{m}$) / **162** ($\ge 36\text{m}$) | **187 / 187** | **187 / 187** |
| **Côte d'Ivoire (`CIV`)** | **0 groupe actif** *(37,5 % `aggregate` en 2020–2026 $\rightarrow$ consultation seule)* | **0** | 0 | 0 | 0 |
| **Maroc (`MAR`)** | **1 groupe** : `CPI_Food` (`Item 23013`, indice `2015=100`, 318 mois continus) | **1** | **1** ($\ge 24\text{m}$) / **1** ($\ge 36\text{m}$) | **1 / 1** | **1 / 1** |
| **TOTAL EXACT** | **19 groupes actifs** *(18 UEMOA + 1 Maroc)* | **738 séries** | **671 séries** ($\ge 24\text{m}$) / **605 séries** ($\ge 36\text{m}$) *(18/19 groupes)* | **738 / 738 séries (100 %, 19/19 groupes)** | **738 / 738 séries (100 %, 19/19 groupes)** |

- **Nombre exact de runs MLflow par campagne (`make train`)** :
  - **1 run parent** (`training_campaign`, lié à `training_run.mlflow_parent_run_id`).
  - **$19 \text{ groupes} \times 3 \text{ familles de modèles } (\text{SeasonalNaive}, \text{Ridge\_Seasonal}, \text{LightGBM\_Global}) = \mathbf{57\text{ runs enfants}}$**.
  - **Total = 58 runs MLflow** stockés dans la base dédiée `mlflow_db` (rôle `mlflow_user`).

---

## 3. Conception Méthodologique ML et Détection d'Anomalies

### 3.1 Protocole ML : Zéro Imputation (`NaN`), Sélection sur Fenêtres 1–2, Rapport Final sur Fenêtre 3
1. **Pas d'imputation des mois manquants** : Les rares mois manquants ($\le 3$ mois consécutifs) dans le segment continu (60 à 120 mois post-2015) sont **laissés à `NaN`**. Aucune interpolation linéaire n'est appliquée.
2. **Découpage par date calendaire commune $T_{\text{cutoff}}$** : Identique pour tous les marchés d'un groupe, avec exclusion de la zone tampon $t < T_{\text{cutoff}} < t+h$.
3. **Séparation stricte Validation (Fenêtres 1–2) vs Test Final (Fenêtre 3)** :
   - Le choix du modèle champion pour chaque couple `(groupe, horizon)` est effectué **uniquement sur les Fenêtres de Validation 1 (`2022`) et 2 (`2024-2025`)** à l'aide de deux métriques définies sans ambiguïté :
     - Le **vrai `MASE`** (Hyndman & Koehler 2006), dont le dénominateur est l'erreur saisonnière *in-sample* $\frac{1}{N_{\text{train}}} \sum_{t \le T_{\text{cutoff}}} |y_t - y_{t-12}|$.
     - Le **`RelMAE_h`** ($\frac{\text{MAE}_{\text{modèle}}(h)}{\text{MAE}_{\text{SeasonalNaive}}(h)}$ sur la fenêtre d'évaluation), qui doit être $< 1{,}0$.
   - Le **rapport final de performance hors-échantillon** est mesuré **une seule fois sans retouche sur la Fenêtre 3 (`2025-09` $\rightarrow$ `2026-08/09`, 738 séries)**.
4. **Intervalles conformes relatifs (`fact_conformal_quantiles`)** :
   - Calibrés sur les erreurs relatives $e_i = \frac{y_i - \hat{y}_i}{\hat{y}_i}$ par `(country_iso3, commodity_group, model_name, horizon_months, eval_window)`.
   - Le **PICP à 80 %** est mesuré et affiché à la fois sur la **Fenêtre 3 (régime récent)** et sur la **Fenêtre 1 (choc 2022)**.

---

### 3.2 Détection d'anomalies : Définition unique sur $\ge 5\text{ ans}$ ($\text{MAD} \times 1{,}4826$) et Protocole de validation *a priori* en CI
1. **Périmètre** : Séries mensuelles (`frequency = 'MONTHLY'`, `is_observed = TRUE`) disposant d'au moins **60 mois (5 ans)** d'observations (afin d'avoir au minimum 5 points par mois calendaire $m \in \{1..12\}$).
2. **Définition mathématique unique de la valeur attendue ($\hat{P}_{\text{expected}, t}$)** :
   - Soit $L_t = \ln(P_t)$ le logarithme népérien du prix (ou de l'indice) observé au mois $t = (y, m)$.
   - Le **niveau tendanciel local passé** est la médiane des log-prix sur les 12 mois précédents :
     $$\tilde{T}_t = \text{median}\left(\{L_{t-12}, L_{t-11}, \dots, L_{t-1}\} \setminus \{\text{NaN}\}\right)$$
   - L'**effet saisonnier typique du mois calendaire $m$** est la médiane historique des écarts à la tendance pour ce mois $m$ :
     $$\tilde{S}_m = \text{median}_{y'}\left(L_{y', m} - \tilde{T}_{y', m}\right)$$
   - La **valeur attendue unique** en niveau est :
     $$\hat{P}_{\text{expected}, t} = \exp\left(\tilde{T}_t + \tilde{S}_m\right)$$
3. **Résidu à la tendance-saisonnalité et $Z$-score robuste ($\text{MAD} \times 1{,}4826$)** :
   - Le résidu en log vaut $r_t = \ln(P_t) - \ln(\hat{P}_{\text{expected}, t}) = (L_t - \tilde{T}_t) - \tilde{S}_m$.
   - L'échelle normale robuste du mois calendaire $m$ est :
     $$\hat{\sigma}_{\text{MAD}, m} = 1{,}4826 \times \text{median}_{y'}\left(\left|r_{y', m} - \text{median}(r_{\cdot, m})\right|\right)$$
   - Le score d'anomalie robuste est :
     $$z_{\text{robust}, t} = \frac{r_t}{\max(\hat{\sigma}_{\text{MAD}, m},\; 0{,}02)}$$
   - **Seuils** : $|z_{\text{robust}, t}| \ge 2{,}5 \rightarrow \text{'WARNING'}$ ; $|z_{\text{robust}, t}| \ge 3{,}5 \rightarrow \text{'CRITICAL'}$.
4. **Protocole de validation *a priori* déplacé en test automatique CI (`pytest`), liens vérifiables et règle d'intégrité scientifique** :
   - **Autocritique statistique** : 4 chocs choisis *après coup* constituent un échantillon trop restreint ($N=4$, borne inférieure de Clopper-Pearson à $95\,\% = 39{,}8\,\%$) et sujet au biais de sélection pour parler d'un rappel général de « 100 % ».
   - **Catalogue élargi fixé *a priori* à partir de sources externes vérifiables (5 crises majeures)** :
     1. **`SHOCK-01` (2008-03..2008-09) — Crise alimentaire mondiale 2007–2008** (`SEN` Riz importé, `NER` Mil/Sorgho — *Source vérifiable : FAO SOFI 2008*, https://www.fao.org/4/i0291e/i0291e00.pdf).
     2. **`SHOCK-02` (2012-03..2012-09) — Crise alimentaire et pastorale sahélienne de 2012** (`MLI`, `NER`, `BFA` Mil/Sorgho — *Source vérifiable : FEWS NET & CILSS 2012*, https://reliefweb.int/report/mali/joint-special-report-grain-market-outlook-west-africa).
     3. **`SHOCK-03` (2020-04..2020-08) — Choc pandémique COVID-19 et fermetures de frontières** (`SEN`, `MLI`, `BFA`, `NER` Céréales — *Source vérifiable : WFP RBD & CILSS 2021*, https://reliefweb.int/report/burkina-faso/west-and-central-africa-market-situation-2020-and-2021-outlooks-march-2021).
     4. **`SHOCK-04` (2022-03..2022-11) — Choc inflationniste mondial et guerre en Ukraine** (`BFA`, `MLI`, `SEN` Céréales ; `MAR` IPC Alimentaire `23013` — *Sources vérifiables : FAO-WFP Hunger Hotspots juin 2022*, https://www.fao.org/3/cb9236en/cb9236en.pdf ; *HCP Maroc IPC*, https://www.hcp.ma/L-Indice-des-prix-a-la-consommation-IPC-du-mois-d-Aout-2022_a3575.html).
     5. **`SHOCK-05` (2023-08..2024-03) — Crise des sanctions CEDEAO et fermeture des frontières au Niger** (`NER` Riz importé, Maïs, Mil — *Sources vérifiables : WFP Niger 12 août 2023*, https://reliefweb.int/report/niger/niger-preliminary-analysis-impacts-political-crisis-and-sanctions-food-security-and-markets-12-august-2023 ; *FEWS NET Niger Price Bulletin août 2023*, https://reliefweb.int/report/niger/niger-price-bulletin-august-2023).
   - **Règle d'intégrité scientifique (*Zéro retouche opportuniste des seuils*)** : un épisode du catalogue non détecté au seuil fixé *a priori* ($|z_{\text{robust}, t}| \ge 2{,}5$) est **un résultat empirique à rapporter et expliquer tel quel**, et **jamais un motif pour abaisser ou ajuster les seuils après coup**.
   - **Exécution dans la CI et retour au seuil hors-choc de $\le 5\,\%$** : un test automatique (`tests/unit/test_anomaly_reference_shocks.py`) génère le **rapport de rappel événement par événement** et vérifie le seuil documenté (et un taux d'alertes hors crise **$\le 5\,\%$**, cohérent avec la borne de spécificité de `KPI-M4` sous $|Z| \ge 2{,}5$).

---

## 4. Stratégie de Qualité des Données et de Tests Logiciels

### 4.1 Règles de contrôle qualité ETL (`DQ-01` à `DQ-07`)

| Code | Niveau | Contrôle exécuté | Seuil / Action |
| :---: | :---: | :--- | :--- |
| **`DQ-01`** | Fichier (Bloquant) | **Anti-WAF** : Vérifie `HTTP 200` et `Content-Length > 0` (absence de challenge `HTTP 202` AWS WAF). | 100 % conforme (Retry backoff 3x, sinon `Exit 1`). |
| **`DQ-02`** | Fichier (Bloquant) | **Anti-Troncature HDX** : Vérifie `size == expected_size`, hash `MD5` et nombre de lignes (`fs_check_info` de l'API CKAN `package_show`). | Écart = 0 octet. Protège contre la troncature observée sur `wfp_NER.csv`. |
| **`DQ-03`** | Schéma (Bloquant) | Vérifie la présence de toutes les colonnes obligatoires et ignore la ligne HXL `#date+...`. | 0 colonne manquante. |
| **`DQ-04`** | Ligne (Quarantaine) | Vérifie `observed_value > 0`, dates valides et coordonnées GPS valides (ou `NULL` si `NATIONAL`). | Taux de rejet $< 1\%$ (isolé dans `audit_rejected_rows`). |
| **`DQ-05`** | Série (Bloquant) | Application de `ref_unit_conversion`, résolution déterministe de collision d'unité (priorité `raw_unit == canonical_unit`) et unicité `UNIQUE (series_id, calendar_id, source_flag)`. | 0 doublon en base. |
| **`DQ-06`** | Série (Méthodo) | Vérifie qu'aucune série `ANNUAL` ou `is_observed = FALSE` (`aggregate`) n'a `is_ml_eligible = TRUE`. | 0 série non conforme. |
| **`DQ-07`** | Catalogue (Alerte) | Vérifie que le nombre de séries `is_ml_eligible = TRUE` reste stable autour de **738 séries** (19 groupes). | Alerte si baisse $> 5\%$. |

### 4.2 Stratégie de Tests (`pytest`, couverture $\ge 70\%$)
1. **Tests unitaires ETL (`tests/unit/test_etl.py`)** : Détection de fichier tronqué / WAF (`DQ-01`/`DQ-02`), `ref_unit_conversion` (conversion de `100 KG`/`500 G` vs non-conversion de `Pile`/`Head`), résolution de collision d'unité, calcul de `is_ml_eligible` sans imputation.
2. **Tests unitaires ML & Anomalies (`tests/unit/test_ml.py` & `tests/unit/test_anomaly_reference_shocks.py`)** : Absence de fuite inter-marchés sur $T_{\text{cutoff}}$, gestion des `NaN`, calcul du vrai `MASE` et du `RelMAE_h`, sélection sur Fenêtres 1–2 vs rapport sur Fenêtre 3, rapport événement par événement et vérification du seuil ($\ge 80\%$) sur le catalogue élargi de 5 crises historiques (`2008`, `2012`, `2020`, `2022`, `2023–2024`).
3. **Tests d'intégration (`tests/integration/test_api.py`)** : Vérification des FK composites SQL, isolation des permissions (`agriprix_api_readonly` vs `agriprix_etl_writer` vs `mlflow_user`), et tests des endpoints FastAPI.
