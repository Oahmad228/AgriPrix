# ADR-003 : Stratégie ML globale (19 groupes), absence d'imputation (`NaN`), sélection sur Fenêtres 1–2, test final sur Fenêtre 3, métriques `MASE` / `RelMAE` et validation CI du détecteur d'anomalies

- **Statut** : Accepté (Révisé en Phase 3)
- **Date** : 2026-11-03
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `SMART-02`, `SMART-03`, `EF-07`, `EF-08`, `EF-09`, `EF-11`, `EF-12`, `EF-13`, `ENF-01`, `ENF-03`

---

## 1. Contexte et Chiffres Exacts Vérifiés

L'application de nos 5 critères d'éligibilité (`frequency == 'MONTHLY'`, `is_observed == TRUE`, panier sécurité alimentaire en `Retail` ou IPC Maroc `23013`, fraîcheur relative $\text{last\_obs} \ge \max(\text{date\_pays}) - 3\text{ mois}$, segment continu récent $\ge 60\text{ mois}$ avec au plus 3 mois manquants consécutifs) sélectionne exactement **738 séries éligibles** réparties dans **19 groupes `(country_iso3, commodity_group)`** :
- **Sénégal (`SEN`, 45 séries)** : **5 groupes** (`Rice` : 18, `Maize` : 8, `Millet` : 8, `Beans` : 8, `Sorghum` : 3).
- **Mali (`MLI`, 230 séries)** : **4 groupes** (`Rice` : 77, `Millet` : 53, `Maize` : 50, `Sorghum` : 50 — *0 série éligible pour `Beans`*).
- **Burkina Faso (`BFA`, 275 séries)** : **5 groupes** (`Rice` : 58, `Beans` : 58, `Millet` : 55, `Sorghum` : 54, `Maize` : 50).
- **Niger (`NER`, 187 séries)** : **4 groupes** (`Rice` : 52, `Millet` : 48, `Sorghum` : 45, `Maize` : 42 — *0 série éligible pour `Beans`*).
- **Maroc (`MAR`, 1 série)** : **1 groupe** (`CPI_Food` : série `23013` en base `2015 = 100`).
- **Total exact** : **$5 + 4 + 5 + 4 + 1 = \mathbf{19\text{ groupes}}$** ($\times 3\text{ horizons } h \in \{1, 3, 6\} = \mathbf{57\text{ modèles globaux}}$ par famille).

---

## 2. Décisions Méthodologiques

### 2.1 Zéro imputation des mois manquants (Conserver `NaN`)
- **Pourquoi ne pas imputer ?** Toute interpolation linéaire utilise des points voisins et modifie artificiellement la variance locale et les pentes de la série.
- **Décision** : Dans le segment continu récent (60 à 120 mois post-2015, où les trous ne dépassent jamais 3 mois consécutifs), **les mois manquants sont laissés à `NaN`**.
  - Les moyennes glissantes causales sont calculées avec `min_periods=1` sur les observations réellement présentes dans la fenêtre passée.
  - `LightGBM` gère nativement les `NaN` dans les *lags* lors du partitionnement des nœuds d'arbres.
  - Pour les modèles linéaires (`Ridge_Seasonal`), seules les dates où les *lags* requis et la cible $y_{t+h}$ sont observés (`not NaN`) entrent dans la matrice d'ajustement.

### 2.2 Découpage calendaire commun ($T_{\text{cutoff}}$) et Séries testables par fenêtre
Tous les marchés d'un groupe sont découpés sur la **même date de calendrier $T_{\text{cutoff}}$** (avec exclusion de la zone tampon où $t < T_{\text{cutoff}} < t+h$) :

| Fenêtre | Rôle méthodologique | Date de coupure $T_{\text{cutoff}}$ | Période cible (12 mois) | Nombre exact de séries testables (sur 738) | Groupes couverts |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Fenêtre 1 (`VAL_W1_2022`)** | **Validation 1 (Choc 2022)** — Choix du champion & hyperparamètres | `2021-12-15` | `2022-01` $\rightarrow$ `2022-12` | **671 séries** ($\ge 24\text{m}$ continus pré-2022) / **605 séries** ($\ge 36\text{m}$ pré-2022) | **18 / 19 groupes** *(hors `SEN Beans` démarré en `2020-07`)* |
| **Fenêtre 2 (`VAL_W2_24_25`)** | **Validation 2 (Stabilisation)** — Choix du champion & hyperparamètres | `2024-06-15` | `2024-07` $\rightarrow$ `2025-06` | **738 / 738 séries (100 %)** | **19 / 19 groupes** |
| **Fenêtre 3 (`TEST_W3_25_26`)** | **Test Final *Hold-out*** — Rapport final de performance hors-échantillon | `2025-08-15` | `2025-09` $\rightarrow$ `2026-08/09` | **738 / 738 séries (100 %)** | **19 / 19 groupes** |

### 2.3 Sélection du modèle champion sur les Fenêtres 1–2 et Rapport final sur la Fenêtre 3
Pour éliminer tout biais de sélection sur le jeu de test (*Test Set Snooping*) :
1. **Choix du modèle champion** (entre `LightGBM_Global`, `Ridge_Seasonal` / `SARIMA` et `SeasonalNaive`) pour chaque `(groupe, horizon)` : effectué **exclusivement sur les performances agrégées des Fenêtres de Validation 1 et 2**.
2. **Rapport final de performance** : mesuré **une seule fois sans retouche sur la Fenêtre 3 (`2025-09..2026-08/09`)** sur les 738 séries.

### 2.4 Formules exactes du `MASE` et du `RelMAE_h`
Nous distinguons et calculons explicitement deux métriques complémentaires :
1. **Le vrai `MASE` (*Mean Absolute Scaled Error*, Hyndman & Koehler 2006)**, dont le dénominateur est l'erreur absolue moyenne saisonnière **sur l'échantillon d'entraînement (*in-sample*, $t \le T_{\text{cutoff}}$)** :
   $$\text{MASE}_{s, h} = \frac{\frac{1}{|W_{\text{eval}}|} \sum_{t \in W_{\text{eval}}} |y_{s, t+h} - \hat{y}_{s, t+h}|}{\frac{1}{N_{\text{train}, s}} \sum_{t \le T_{\text{cutoff}}} |y_{s, t} - y_{s, t-12}|}$$
2. **Le ratio d'erreur relative face à la baseline sur la fenêtre d'évaluation (`RelMAE_h`)** :
   $$\text{RelMAE}_{s, h} = \frac{\text{MAE}_{\text{modèle}}(s, h, W_{\text{eval}})}{\text{MAE}_{\text{SeasonalNaive}}(s, h, W_{\text{eval}})}$$
   Un modèle ML n'est promu champion sur `(groupe, h)` que si sa médiane sur les Fenêtres 1–2 vérifie **`RelMAE_h < 1.0` ET `MASE` minimal** parmi les familles candidates.

### 2.5 Nombre exact de runs MLflow et table `training_run`
- Chaque exécution de `make train` ouvre **1 run parent MLflow** (lié à `training_run.run_id` et `git_sha`) et exactement **$19 \text{ groupes} \times 3 \text{ familles de modèles} = \mathbf{57\text{ runs enfants MLflow}}$** (**58 runs au total** dans la base isolée `mlflow_db`).
- Les métriques détaillées par série (`MASE`, `RelMAE_h`, `MAPE`, `RMSE`, `PICP_80`) sont enregistrées dans `fact_model_metrics_by_series` avec la contrainte `UNIQUE (run_id, series_id, model_name, horizon_months, eval_window)`.

### 2.6 Validation *a priori* du détecteur d'anomalies en CI (et reconnaissance des limites d'un petit échantillon)
- **Autocritique méthodologique (Pourquoi 4 chocs choisis après coup ne permettent pas de parler de « 100 % de rappel »)** :
  1. Choisir 4 épisodes historiques *après* avoir inspecté les courbes crée un **biais de sélection (*cherry-picking* post-hoc)**.
  2. D'un point de vue statistique, un échantillon de $N = 4$ événements est beaucoup trop petit pour affirmer un rappel général de « 100 % » (selon l'intervalle de confiance exact de Clopper-Pearson à 95 %, observer $4/4$ succès est compatible avec un rappel réel aussi bas que $39,8\%$).
- **Protocole corrigé retenu** :
  1. **Liste de chocs de référence fixée *a priori* à partir de la littérature externe avec liens vérifiables** (avant d'inspecter la sortie du détecteur) et élargie à **5 crises majeures documentées (déclinées en 9 couples Épisode × Pays/Produit)** :
     - **`SHOCK-01` (2008-03 à 2008-09) — Crise alimentaire mondiale 2007–2008** : flambée du riz importé au Sénégal (`SEN`) et du mil/sorgho au Niger (`NER`) — *Source vérifiable : FAO (2008), The State of Food Insecurity in the World 2008: High food prices and food security – threats and opportunities, Rome, ISBN 978-92-5-106049-0* (https://www.fao.org/4/i0291e/i0291e00.pdf).
     - **`SHOCK-02` (2012-03 à 2012-09) — Crise alimentaire et pastorale sahélienne de 2012** : flambée du mil et du sorgho au Mali (`MLI`), au Niger (`NER`) et au Burkina Faso (`BFA`) suite à la sécheresse 2011/2012 et au conflit au Nord-Mali — *Source vérifiable : FEWS NET & CILSS (2012), Joint Special Report: Grain Market Outlook for West Africa, ReliefWeb* (https://reliefweb.int/report/mali/joint-special-report-grain-market-outlook-west-africa).
     - **`SHOCK-03` (2020-04 à 2020-08) — Choc pandémique COVID-19 et fermetures de frontières** : tensions sur le riz et les céréales sèches (`SEN`, `MLI`, `BFA`, `NER`) lors des restrictions de circulation du printemps-été 2020 — *Source vérifiable : WFP Regional Bureau for Western Africa & CILSS (mars 2021), West and Central Africa: Market situation in 2020 and 2021 outlooks, ReliefWeb* (https://reliefweb.int/report/burkina-faso/west-and-central-africa-market-situation-2020-and-2021-outlooks-march-2021).
     - **`SHOCK-04` (2022-03 à 2022-11) — Choc inflationniste mondial et guerre en Ukraine** : flambée des céréales au Burkina Faso (`BFA`), au Mali (`MLI`) et au Sénégal (`SEN`), et pic d'inflation de l'IPC Alimentaire au Maroc (`MAR`, série `23013`) — *Sources vérifiables : FAO & WFP (juin 2022), Hunger Hotspots: FAO-WFP early warnings on acute food insecurity: June to September 2022 Outlook* (https://www.fao.org/3/cb9236en/cb9236en.pdf) ; *Haut-Commissariat au Plan (HCP Maroc, 2022), L’Indice des prix à la consommation (IPC) du mois d’août 2022 — hausse de 1,5 % sur un mois de l’indice des produits alimentaires* (https://www.hcp.ma/L-Indice-des-prix-a-la-consommation-IPC-du-mois-d-Aout-2022_a3575.html).
     - **`SHOCK-05` (2023-08 à 2024-03) — Crise politique, sanctions CEDEAO et fermeture des frontières au Niger** : hausse brutale du riz importé et des céréales locales au Niger (`NER`) après juillet 2023 — *Sources vérifiables : WFP (12 août 2023), Niger: Preliminary Analysis on the Impacts of the Political Crisis and Sanctions on Food Security and Markets* (https://reliefweb.int/report/niger/niger-preliminary-analysis-impacts-political-crisis-and-sanctions-food-security-and-markets-12-august-2023) ; *FEWS NET (août 2023), Niger Price Bulletin* (https://reliefweb.int/report/niger/niger-price-bulletin-august-2023).
  2. **Règle d'intégrité scientifique (*Zéro ajustement opportuniste des seuils*) et Rapport événement par événement** :
     - Le seuil d'alerte est fixé *a priori* à $|Z_{\text{rob}}| \ge 2{,}5$ (`WARNING`) et $|Z_{\text{rob}}| \ge 3{,}5$ (`CRITICAL`). **Si un épisode du catalogue de référence n'est pas détecté à ce seuil, il s'agit d'un résultat empirique à rapporter et expliquer en toute transparence** (ex. lissage du choc par des subventions publiques ou absorption progressive dans la médiane mobile de 12 mois), **et en aucun cas d'un motif pour abaisser ou retoucher le seuil après coup (*post-hoc tuning*)**.
     - Le rapport d'évaluation affiche une table détaillée **événement par événement** (statut détecté `OUI/NON`, $|Z_{\text{rob}}|$ maximal atteint, part des marchés en alerte dans le groupe, et taux d'alerte hors période de crise), suivie du rappel global sur le catalogue ($K / N$ épisodes détectés).
  3. **Justification du retour au seuil hors-choc de $\le 5\,\%$ (et non $10\,\%$) et déplacement en test automatique de la CI (`pytest`)** :
     - **Pourquoi $\le 5\,\%$ en période calme (retour à la cible stricte de `KPI-M4`)** : Sous une loi normale standard, $|Z| \ge 2{,}5$ correspond théoriquement à $1{,}24\,\%$ des observations dans les deux queues ($0{,}62\,\%$ en queue haute). Même en tenant compte du caractère leptokurtique (queues épaisses) des séries de prix agricoles sahéliennes, exiger un taux d'alerte hors crise majeure **$\le 5\,\%$** (soit au plus ~0,6 mois d'alerte par an en régime normal) garantit que le détecteur ne noie pas les décideurs sous de fausses alertes, tandis qu'un relâchement à $10\,\%$ (plus d'un mois sur dix en alerte hors crise) dégraderait la spécificité opérationnelle.
     - **Exécution en CI (`make test`)** : Vérifier des chocs passés figés (2008, 2012, 2020, 2022, 2023) comme porte bloquante à chaque exécution mensuelle en production (`make train`) n'a pas de sens opérationnel. Cette validation est donc exécutée dans un **test automatique de la CI (`pytest`)** qui génère le rapport événement par événement et vérifie la non-régression de l'algorithme sans jamais modifier les seuils.
