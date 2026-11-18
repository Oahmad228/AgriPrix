# ADR-004 : Quantification de l'incertitude par Prédiction Conforme sur erreurs relatives par groupe et persistance dans `fact_conformal_quantiles`

- **Statut** : Accepté (Révisé en fin de Phase 2)
- **Date** : 2026-11-03
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

---

## 3. Mise à jour du 2026-11-18 : intervalles log-symétriques et biais affiché (décision d'Ahmad, option B)

### 3.1 Problème constaté
Sur la démo en ligne, la prévision à 6 mois du maïs blanc à Ouahigouya (202 XOF/kg) sortait de sa propre fourchette (131–189).
- **Cause, vérifiée dans la base Neon** : les quantiles de production sont calibrés sur la fenêtre W3, pendant laquelle les prix ont chuté. À 6 mois, le modèle a presque toujours surestimé : même le 90ᵉ centile des erreurs relatives était négatif (q90 = −0,065 pour ce groupe). La fourchette prévision × (1 + q10) … prévision × (1 + q90) était donc entièrement sous la prévision.
- **Ampleur** : 7 groupes, tous à 6 mois. **365 prévisions servies sur 2 346 (15,6 %)** étaient hors de leur fourchette, toutes par le haut.
- Ce n'est pas une erreur d'arithmétique, mais une conséquence du retournement de marché étudié par l'hypothèse H3 de la recherche.

### 3.2 Décision
1. **Fourchette symétrique sur l'échelle logarithmique** :
   - rayon r = 80ᵉ centile de |ln(prix réel / prévision)| par (pays, groupe, modèle, horizon), avec la correction d'échantillon fini habituelle de la prédiction conforme (rang ⌈(n+1)·0,8⌉) ;
   - fourchette = prévision × e^(−r) … prévision × e^(+r).

   La prévision est toujours au centre (en échelle log) et les bornes restent positives. C'est la prédiction conforme « split » classique, avec un score en valeur absolue appliqué aux log-prix.
2. **Le biais n'est pas caché** : le biais médian récent, e^(médiane de ln(réel / prévision)) − 1, est calculé sur la même fenêtre de calibration. Il est stocké (`median_log_error`) et servi par l'API (`recent_bias_pct`). Le tableau de bord l'affiche en une phrase quand |biais| ≥ 10 % (seuil proposé). **Le chiffre de prévision servi n'est jamais corrigé**, pour rester celui qui a été évalué.
3. **Traçabilité** : la colonne `interval_method` (`signed_relative` ou `log_symmetric`) est ajoutée par la migration `V005`. Les campagnes antérieures restent lisibles telles quelles.
4. **`v1.0-baseline` et le protocole de recherche ne changent pas** : la méthode signée reste la référence figée (fonction `apply_interval` conservée).

### 3.3 Circularité de la couverture affichée (vérifiée dans le code)
La « couverture mesurée en test » (`test_picp_80`) est mesurée sur W3 avec des fourchettes calibrées sur W2 : **la calibration et la mesure sont séparées, ce n'est pas circulaire**. En revanche, la fourchette servie en production est recalibrée sur W3. Le chiffre affiché décrit donc la qualité **de la méthode** hors échantillon, pas exactement celle de cette fourchette-là. Le texte de l'API le précise désormais.

### 3.4 Résultats (rapport généré [`interval-methods-comparison.md`](../results/interval-methods-comparison.md), modèles champions)

| Fenêtre (calibrée sur) | Horizon | Couverture v1 | Couverture log-sym. | Largeur médiane v1 → log-sym. | Prévisions hors de leur fourchette v1 |
| :--- | :--- | ---: | ---: | :--- | ---: |
| W1 2022 (2021) | 6 mois | 54,3 % | 59,0 % | 34,6 % → 37,2 % | 27,3 % |
| W3 2025-26 (W2) | 1 mois | 81,0 % | 81,9 % | 19,1 % → 20,8 % | 0,0 % |
| W3 2025-26 (W2) | 3 mois | 75,8 % | 77,7 % | 34,9 % → 39,8 % | 0,0 % |
| W3 2025-26 (W2) | 6 mois | 51,8 % | **61,4 %** | 48,5 % → 47,5 % | 0,0 % |

- **Contrôle** : les couvertures v1 recalculées sont identiques à celles publiées dans `forecast-report.md`, qui n'est pas modifié.
- **Lecture honnête** : la nouvelle méthode couvre mieux partout. À 6 mois, elle reste pourtant loin de 80 % lors des retournements de marché. C'est la question H3 de la recherche, qui n'est pas résolue ici.
