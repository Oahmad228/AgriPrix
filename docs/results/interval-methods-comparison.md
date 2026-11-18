# Comparaison des deux méthodes d'intervalles à 80 % (rapport généré)

> Généré par `python -m src.ml.intervals_report` (entrepôt local, données jusqu’à 2026-10). Aucun chiffre n'est saisi à la main.
> Les deux méthodes sont calibrées sur la même fenêtre et mesurées sur la fenêtre suivante, jamais sur celle qui a servi à les calibrer. Seuls les modèles champions sont évalués.

- **v1 (`signed_relative`)** : quantiles 10 % et 90 % des erreurs relatives signées (ADR-004 §1-2, référence figée `v1.0-baseline`).
- **log-symétrique (`log_symmetric`)** : rayon = 80ᵉ centile corrigé de |ln(réel / prévision)|, fourchette = prévision × exp(±rayon) (ADR-004 §3).

|  | fenêtre | calibrée sur | horizon | prévisions | couverture v1 (%) | couverture log-sym. (%) | largeur médiane v1 (% de la prévision) | largeur médiane log-sym. (%) | prévisions hors de leur fourchette v1 (%) | biais médian de calibration (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | VAL_W1_2022 | CAL_W0_2021 | 1 mois | 8617 | 72.6 | 76.1 | 17.0 | 18.7 | 0.0 | 0.6 |
| 1 | VAL_W1_2022 | CAL_W0_2021 | 3 mois | 8626 | 62.9 | 66.9 | 28.1 | 30.7 | 0.0 | 2.4 |
| 2 | VAL_W1_2022 | CAL_W0_2021 | 6 mois | 8626 | 54.3 | 59.0 | 34.6 | 37.2 | 27.3 | 6.6 |
| 3 | TEST_W3_25_26 | VAL_W2_24_25 | 1 mois | 8559 | 81.0 | 81.9 | 19.1 | 20.8 | 0.0 | -0.3 |
| 4 | TEST_W3_25_26 | VAL_W2_24_25 | 3 mois | 8462 | 75.8 | 77.7 | 34.9 | 39.8 | 0.0 | -0.3 |
| 5 | TEST_W3_25_26 | VAL_W2_24_25 | 6 mois | 8485 | 51.8 | 61.4 | 48.5 | 47.5 | 0.0 | 0.2 |

Lecture : la couverture est la part des prix réels tombés dans la fourchette (objectif 80 %) ; « hors de leur fourchette » compte les prévisions que la méthode v1 plaçait en dehors de leur propre fourchette (impossible avec la méthode log-symétrique) ; un biais négatif signifie que le modèle surestimait le prix pendant la fenêtre de calibration.
