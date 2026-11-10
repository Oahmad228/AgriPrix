# Résultats des prévisions (rapport généré)

> Généré par `python -m src.ml.report` depuis la campagne active `training_run.run_id = 2` (données ETL `etl_run_id = 5`, dernières données 2026-10-01, commit `1f5812b`, run MLflow parent `113755889dff4d868df1d59a15495686`). Aucun chiffre n'est saisi à la main.

## 1. Test final hors échantillon — fenêtre W3 (cibles 2025-09 → 2026-08)

Modèles champions choisis **uniquement** sur W1 + W2, puis évalués une seule fois sur W3.

| horizon | séries | MAPE (%) | MASE médian | RelMAE médian vs SeasonalNaive | gain vs Naive (%) | gain vs SeasonalNaive (%) | PICP 80 % (%) |
|---|---|---|---|---|---|---|---|
| 1 mois | 781 | 5.9 | 0.35 | 0.19 | -12.2 | 78.8 | 80.3 |
| 3 mois | 781 | 12.7 | 0.74 | 0.42 | -11.4 | 56.2 | 75.3 |
| 6 mois | 782 | 22.8 | 1.31 | 0.75 | -19.7 | 23.7 | 51.3 |

## 2. Choc de 2022 — fenêtre W1 (cibles 2022-01 → 2022-12)

| horizon | séries | MAPE (%) | MASE médian | RelMAE médian vs SeasonalNaive | gain vs Naive (%) | gain vs SeasonalNaive (%) | PICP 80 % (%) |
|---|---|---|---|---|---|---|---|
| 1 mois | 741 | 6.2 | 0.61 | 0.25 | 4.6 | 75.3 | 72.4 |
| 3 mois | 741 | 11.7 | 1.17 | 0.49 | 9.7 | 53.1 | 62.5 |
| 6 mois | 741 | 16.5 | 1.69 | 0.69 | 8.7 | 32.4 | 54.1 |

## 3. Gain de chaque famille de modèles face à la persistance (Naive), en %

Valeur positive = erreur absolue totale plus faible que « le prix restera le dernier prix connu ».

**Fenêtre de sélection W1 (2022) :**

| horizon | LightGBM_Global | Naive | Ridge_Seasonal | SeasonalNaive |
|---|---|---|---|---|
| 1 mois | 4.1 | 0.0 | -4.1 | -286.7 |
| 3 mois | 9.9 | 0.0 | 6.9 | -92.5 |
| 6 mois | 7.9 | 0.0 | 8.0 | -35.0 |

**Fenêtre de sélection W2 (2024-07 → 2025-06) :**

| horizon | LightGBM_Global | Naive | Ridge_Seasonal | SeasonalNaive |
|---|---|---|---|---|
| 1 mois | 5.3 | 0.0 | -8.5 | -159.5 |
| 3 mois | 15.9 | 0.0 | 5.5 | -33.2 |
| 6 mois | 13.2 | 0.0 | 10.9 | -3.1 |

**Fenêtre de test W3 :**

| horizon | LightGBM_Global | Naive | Ridge_Seasonal | SeasonalNaive |
|---|---|---|---|---|
| 1 mois | -10.7 | 0.0 | -16.3 | -430.2 |
| 3 mois | -10.7 | 0.0 | -12.8 | -154.5 |
| 6 mois | -18.2 | 0.0 | -17.0 | -56.9 |

## 4. Modèles champions par horizon (19 groupes pays × produit)

| horizon | LightGBM_Global | Ridge_Seasonal | SeasonalNaive |
|---|---|---|---|
| 1 mois | 16 | 3 | 0 |
| 3 mois | 16 | 3 | 0 |
| 6 mois | 11 | 7 | 1 |

Définitions : MAPE = erreur absolue moyenne en % du prix réel ; MASE = erreur rapportée à la variation saisonnière moyenne de la série sur l'entraînement (< 1 = mieux que cette variation) ; RelMAE = erreur du modèle / erreur de SeasonalNaive ; PICP = part des prix réels tombés dans l'intervalle à 80 %.
