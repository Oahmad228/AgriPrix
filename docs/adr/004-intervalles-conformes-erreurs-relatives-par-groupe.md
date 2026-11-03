# ADR-004 : Quantification de l'incertitude par Prédiction Conforme sur erreurs relatives par groupe et persistance dans `fact_conformal_quantiles`

- **Statut** : Accepté (Révisé en fin de Phase 2)
- **Date** : 2026-04-19
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `SMART-02`, `EF-08`, `EF-11`, `US-08`, `US-10`

---

## 1. Contexte et Problème

Pour fournir aux décideurs des intervalles de prédiction à 80 % ($[q_{10}, q_{90}]$) adaptés au niveau de prix de chaque marché (*hétéroscédasticité*) et à chaque horizon $h \in \{1, 3, 6\}$, nous calibrons nos intervalles par **Prédiction Conforme scindée (*Split Conformal Prediction*)** sur les **erreurs relatives** regroupées par `(country_iso3, commodity_group, horizon_months)` (soit $19 \text{ groupes} \times 3 \text{ horizons} = 57\text{ couples}$).

Afin de garantir une auditabilité complète et d'éviter que ces quantiles de calibration ne restent cachés en mémoire pendant l'exécution du script Python, ils doivent être **persistés et versionnés dans l'entrepôt PostgreSQL**.

---

## 2. Décision

### 2.1 Calcul des quantiles d'erreur relative par groupe
1. Sur les résidus hors-échantillon de la fenêtre de calibration du groupe $(c, p)$ à l'horizon $h$, nous calculons l'erreur relative signée :
   $$e_i = \frac{y_i - \hat{y}_i}{\hat{y}_i}$$
2. Nous extrayons les quantiles empiriques finis $\hat{q}_{\text{rel}, 10}^{(c, p, h)}$ et $\hat{q}_{\text{rel}, 90}^{(c, p, h)}$ (avec correction d'échantillon fini).
3. Pour toute prévision ponctuelle $\hat{y}_{m, t+h}$, l'intervalle conforme à 80 % est reconstruit par :
   $$\left[\hat{y}_{\text{low}, 80},\; \hat{y}_{\text{high}, 80}\right] = \left[\max\left(0,\; \hat{y}_{m, t+h} \cdot (1 + \hat{q}_{\text{rel}, 10}^{(c, p, h)})\right),\; \hat{y}_{m, t+h} \cdot (1 + \hat{q}_{\text{rel}, 90}^{(c, p, h)})\right]$$

### 2.2 Persistance dans la table `fact_conformal_quantiles` rattachée à `training_run`
Les quantiles calibrés sont sauvegardés dans la table dédiée **`fact_conformal_quantiles`** :
- **Clé étrangère** : `run_id REFERENCES training_run(run_id)`
- **Clé d'unicité** : `UNIQUE (run_id, country_iso3, commodity_group, model_name, horizon_months, eval_window)`
- **Attributs stockés** : `n_calibration_residuals`, `q_rel_10`, `q_rel_90`.

### 2.3 Mesure du PICP sur la Fenêtre 3 (Test final) ET sur la Fenêtre 1 (Choc 2022)
- Sur la **Fenêtre 3 (`TEST_W3_25_26` : 738 séries)** : les quantiles sont calibrés sur les résidus de la Fenêtre 2 (`2024-07..2025-06`) et évalués sans fuite sur `2025-09..2026-08/09` (cible : $75\% \le \text{PICP}_{80} \le 85\%$).
- Sur la **Fenêtre 1 (`VAL_W1_2022` : 605 séries ayant $\ge 36\text{ mois}$ avant fin 2021)** : les quantiles sont calibrés sur l'année pré-choc `2021-01..2021-12` et testés sur l'année de choc `2022-01..2022-12`.
- **Limite documentée et affichée** : Lors du choc inflationniste inédit de 2022 (+88 % sur le mil au Burkina Faso), la distribution des erreurs de test viole l'hypothèse d'**échangeabilité** avec l'année 2021, entraînant une sous-couverture temporaire du PICP en 2022. Documenter et afficher côte à côte `PICP_80 (Fenêtre 3 : régime récent)` et `PICP_80 (Fenêtre 1 : choc 2022)` justifie l'association entre intervalles conformes et détecteur d'anomalies.
