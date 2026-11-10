# ADR-010 : Protocole de prévision mis en œuvre, baseline de persistance et nouvelle règle de sélection du champion

- **Statut** : Accepté
- **Date** : 2026-11-10
- **Décideurs** : Ahmad (choix de la règle) & assistant IA (Claude Code)
- **Exigences liées** : `SMART-02`, `EF-08`, `EF-09`, `EF-10`, `KPI-M2`, `KPI-M3`, `US-07`, `US-08`, `US-09`
- **Remplace** : la règle de sélection de [`ADR-003`](./003-strategie-ml-globale-fenetre-historique-rolling-origin.md) §2.4 ; **précise** `ADR-003` §2.2 et [`ADR-004`](./004-intervalles-conformes-erreurs-relatives-par-groupe.md)

---

## 1. Ce qui a été implémenté (Sprint 2)

| Élément | Choix | Pourquoi |
| :--- | :--- | :--- |
| Cible | variation logarithmique `ln P[t+h] − ln P[t]`, prévision directe pour h = 1, 3, 6 | l'EDA montre des log-prix non stationnaires (ADF rejeté pour 27 % des séries) mais des variations stationnaires (97 %) ; des marchés aux niveaux différents deviennent comparables |
| Modèles globaux | un modèle par (pays, groupe de produits, horizon) : 19 × 3 | assez de données par modèle, temps de calcul maîtrisé |
| Familles | `Naive` (persistance), `SeasonalNaive`, `Ridge_Seasonal`, `LightGBM_Global` | 2 références simples et 2 modèles appris |
| Mois manquants | laissés à `NaN` ; LightGBM les gère nativement ; Ridge reçoit 0 + une colonne indicatrice « manquant » | aucune valeur de prix n'est inventée |
| Fenêtres | `CAL_W0_2021` (calibration des intervalles de W1), `VAL_W1_2022`, `VAL_W2_24_25`, `TEST_W3_25_26` | une fenêtre de calibration avant 2022 est nécessaire pour mesurer le PICP pendant le choc (`ADR-004` §2.3) |
| Anti-fuite | entraînement sur les couples dont le mois **cible** est ≤ T (zone tampon exclue) ; historique plafonné à 120 mois ; test unitaire : modifier tous les prix futurs ne change aucune variable explicative | |
| Séries évaluées par fenêtre | au moins 24 mois observés avant T | |
| Intervalles 80 % | quantiles conformes des erreurs relatives par (pays, groupe, modèle, horizon), avec correction d'échantillon fini ; W1 calibré sur `CAL_W0_2021`, W3 sur W2, production sur W3 | |
| Suivi | 1 run MLflow parent + 1 run enfant par (pays, groupe, famille) = 76 runs enfants ; détail par série dans PostgreSQL | |

## 2. Problème découvert : la référence de comparaison

`ADR-003` comparait les modèles uniquement à `SeasonalNaive`, qui prévoit le prix du même mois l'an passé. À 1 mois d'horizon, cette référence utilise donc un prix vieux de 11 mois et elle est très faible. Elle fait en moyenne **287 % d'erreur en plus** que la persistance (« le prix restera le dernier prix connu ») sur W1. Battre `SeasonalNaive` de 79 % ne prouvait donc presque rien.

Sur les fenêtres de **sélection** (W1, W2), sans regarder le test, l'ancienne règle choisissait ainsi :
- `Ridge_Seasonal` comme champion à 1 mois dans 3 groupes, alors qu'il fait globalement 4 % à 8 % moins bien que la persistance ;
- `SeasonalNaive` comme champion d'un groupe à 6 mois, 35 % moins bon que la persistance sur W1.

## 3. Décision (option retenue par Ahmad)

1. La persistance `Naive` est ajoutée comme famille de référence, dans les métriques **et** parmi les candidats.
2. **Nouvelle règle** : pour chaque (pays, groupe, horizon), le champion est la famille de **MASE médian minimal sur W1 + W2**, les deux références comprises. Un modèle appris n'est donc servi que s'il bat la meilleure référence simple.
3. Le gain du KPI-M2 est publié **contre les deux références**, celle du cahier des charges (`SeasonalNaive`) et la persistance, plus exigeante.

## 4. Intégrité du test final (point important pour l'entretien)

- La fenêtre W3 avait déjà été consultée (run 2, ancienne règle) quand la règle a été changée. Le changement est justifié **uniquement** par les fenêtres W1/W2, mais le W3 du run 3 n'est plus un test parfaitement vierge.
- Les deux rapports sont donc conservés :
  - [`forecast-report-run2-regle-adr003.md`](../results/forecast-report-run2-regle-adr003.md) : W3 vierge, ancienne règle ;
  - [`forecast-report.md`](../results/forecast-report.md) : run actif, nouvelle règle.
- **Aucun modèle, hyperparamètre ou seuil n'a été modifié après consultation de W3.**
- Le prochain test réellement vierge sera constitué des mois postérieurs à 2026-09, au fil des mises à jour mensuelles (Sprint 4).

## 5. Résultats et limites (runs 2 et 3, données ETL `etl_run_id = 5`)

- **W3 (2025-09 → 2026-08)** : les champions battent `SeasonalNaive` (+80 %, +57 %, +25 % à 1/3/6 mois), mais **pas la persistance** (−4,7 %, −10,1 %, −18,5 %). La couverture des intervalles à 80 % est de 81 %, 76 % et 52 %.
- **Explication** : l'EDA montre un retournement de marché. Les prix montaient pendant W2 (+20 % sur un an au Burkina, +14 % au Mali) et chutent pendant W3 (−25 %, −17 %, −27 % au Niger). Les modèles appris prolongent la dynamique apprise. L'hypothèse d'échangeabilité des intervalles conformes est rompue, comme en 2022 (W1 : PICP 73 %, 63 %, 54 %).
- **KPI-M3** (PICP entre 70 % et 90 %) : atteint à 1 et 3 mois sur W3, **non atteint à 6 mois**. Aucun seuil n'est modifié.
- **Temps d'exécution** : 3 min 34 s (objectif `US-08` < 3 min, non atteint ; 158 s pour le backtest de 4 fenêtres × 4 familles × 57 modèles).

## 6. Pistes (à évaluer sur des données futures, jamais sur W3)

1. Intervalles **conformes adaptatifs** (ACI : la largeur s'ajuste chaque mois selon les erreurs récentes), pour mieux suivre les changements de régime.
2. Combinaison persistance + modèle appris, avec des poids appris sur les fenêtres de validation.
3. Ajout de variables exogènes (cours mondiaux, taux de change, indicateurs de récolte), hors périmètre actuel.
