# Protocole pré-enregistré — Prévision des prix céréaliers au Sahel lors des retournements de marché

> **Statut : VERSION 1.0, pré-enregistrée le 2026-11-17 après relecture par Ahmad.**
> Référence : tag Git `protocol-v1` (le hash du commit est cité dans le rapport et dans le dépôt OSF).
> À partir de cette version, **toute modification est une déviation**, consignée en §12 avec sa date et sa raison. Aucun résultat de l'étude n'a été calculé avant cette version.

---

## 0. Décisions d'Ahmad intégrées (2026-11-17)

Ahmad a retenu toutes les recommandations proposées le 2026-11-17 :

| Sujet | Décision |
| :--- | :--- |
| Sources | CHIRPS v3 (pluie), fiches pays GIEWS (récoltes, recoupées avec PREGEC), table manuelle des événements validée par Ahmad |
| Agent LLM | Après le 28/02/2027 ; hors de cette étude |
| Datation | Délais de publication fixes et prudents par source (§3) |
| Unité spatiale de la pluie | Disque de 25 km de rayon autour des coordonnées GPS du marché |
| H3 | Surcoût de largeur toléré : **+25 %** |
| Site d'ici le 28/02 | Dashboard actuel en ligne + page « Facteurs » |
| Rédaction du rapport | Introduction et discussion par Ahmad ; méthodes et résultats générés par l'assistant |
| Évaluation principale | Réentraînement mensuel à origine glissante ; le protocole figé de `v1.0-baseline` reste le lien avec les résultats publiés |
| W4 | Cibles à partir de 2026-11 |
| ARIMA | Pilote sur 20 séries ; si la durée projetée dépasse 3 h, ETS seul (documenté) |

## 1. Question et portée

**Question.** L'information disponible au moment de prévoir (pluie, estimations de récolte, mesures commerciales) améliore-t-elle les prévisions de prix céréaliers à 1, 3 et 6 mois et la fiabilité de leurs intervalles, en particulier lors des retournements de prix ? Et pourquoi des modèles globaux entraînés sur les prix seuls perdent-ils face à la persistance lors de ces retournements ?

**Portée.** Il s'agit d'une **étude de cas** sur peu d'épisodes de retournement : la hausse de 2022 et la baisse de 2025-26. Les marchés d'un même pays évoluent ensemble et ne sont pas des observations indépendantes. Les conclusions ne prétendent pas à une loi générale.

**Biais déclaré.** Les facteurs « récolte » et « mesures commerciales » ont été choisis **après** avoir vu la baisse de W3. W3 ne peut donc rien confirmer sur ces facteurs (§6).

## 2. Données

- **Prix** : entrepôt AgriPrix figé au tag `v1.0-baseline` (ETL `etl_run_id = 7`, dernières données 2026-10-01).
  - **Univers** : les 782 séries éligibles de la référence, dans 19 groupes (pays × produit).
  - **Étude des facteurs (H4)** : restreinte aux **séries WFP de marché des 4 pays sahéliens et du Sénégal** (18 groupes). Le Maroc, un indice national, et la Côte d'Ivoire, non éligible, en sont exclus.
- **Pluie** : CHIRPS **v3**, mensuel, Afrique.
  - Valeur d'un marché = moyenne des pixels dont le centre est à moins de 25 km de ses coordonnées WFP.
  - Marché sans coordonnées : variables de pluie manquantes (`NaN`), avec comptage publié.
- **Récoltes** : fiches pays GIEWS (CC BY 4.0), une ligne par fiche dans `data/external/harvest_giews.csv`, versionné. Colonnes :
  - pays ;
  - date de référence de la fiche ;
  - année de récolte ;
  - écart de production à la moyenne quinquennale en % si chiffré ;
  - direction (−1, 0, +1) ;
  - URL, page ;
  - validé par Ahmad (oui/non).

  Les avis PREGEC servent au recoupement : un désaccord de direction est signalé, jamais corrigé en silence.
- **Événements** : `data/external/events.csv`. Colonnes :
  - pays ;
  - type (`export_ban`, `border_closure`, `sanctions`) ;
  - produits ;
  - date de début et de fin si connue ;
  - **date de publication** du document source ;
  - URL ;
  - validé par Ahmad.

  Sources : GIEWS, FEWS NET, tracker IFPRI (depuis 2022). Seules les lignes validées sont utilisées.

## 3. Règle de datation (anti-fuite)

- **Origine t.** Mois du dernier prix observé de la série, comme dans la référence. La prévision faite à t ne peut utiliser qu'une information **publiée au plus tard le dernier jour du mois t**.
- **Pluie.** Le mois m n'est utilisable qu'à partir de l'origine t = m + 1 : la version définitive de CHIRPS paraît vers le milieu du mois suivant. En sensibilité, on teste t = m + 2.
- **Récoltes.** Une fiche GIEWS n'est utilisable que si sa date de référence est ≤ fin du mois t. On retient la dernière fiche disponible.
- **Événements.** Un événement est « actif à t » si sa date de publication est ≤ fin du mois t, et s'il n'a pas pris fin à une date publiée avant ou à t.
- **Climatologie de la pluie.** Elle est calculée uniquement sur les années strictement antérieures à l'année de la saison décrite, de manière expansive depuis 1981. Aucune normale qui inclut l'avenir.
- **Tests automatiques.** Un test unitaire modifie toutes les valeurs de facteurs publiées après l'origine et vérifie qu'aucune variable explicative ne change. Il échoue s'il détecte une fuite. Le test existant sur les prix est conservé.

## 4. Modèles

Hyperparamètres de LightGBM et de Ridge : **identiques à `v1.0-baseline`**. Aucun réglage n'est fait dans cette étude. Graine : 42.

| Famille | Description |
| :--- | :--- |
| `Naive` (persistance), `SeasonalNaive`, `Ridge_Seasonal`, `LightGBM_Global` | Comme `v1.0-baseline` : un modèle par (pays, groupe, horizon), cible = log-rendement à h mois |
| `ETS` | Par série, sur les log-prix. Erreur additive, tendance additive amortie, saisonnalité additive de période 12 si ≥ 36 mois consécutifs observés, sinon sans saisonnalité. Ajusté sur la plus longue suite récente sans mois manquant qui se termine à t (au moins 24 mois), sinon la série n'a pas d'ETS à cette origine (comptage publié). Aucune imputation. |
| `ARIMA` | Par série, SARIMAX sur les log-prix : d = 1, (p, q) ∈ {0,1,2}², composante saisonnière (P,0,0)₁₂ avec P ∈ {0,1}, ordre choisi par AICc minimal. Les mois manquants sont gérés par le filtre de Kalman. Soumis au pilote (§0). |
| `LightGBM_Global+F` | `LightGBM_Global` + les variables de facteurs (§5) |
| `ARIMAX` | ARIMA + pluie (R1) et récolte (H1f) comme régresseurs. Pour prévoir à h mois, les régresseurs sont **gelés à leur valeur connue à t** : aucune valeur future. |
| Ablation | `LightGBM_Global+F` sans pluie, sans récolte, sans événements |

## 5. Variables de facteurs (fixées a priori)

| Code | Définition |
| :--- | :--- |
| R1 | Anomalie standardisée du cumul de pluie de la dernière saison des pluies complète (juin → octobre) disponible à t, par rapport à la climatologie expansive |
| R2 | Anomalie standardisée du cumul des 3 derniers mois de pluie disponibles, par rapport aux mêmes mois de la climatologie |
| H1f | Écart (%) de la dernière estimation de production GIEWS à la moyenne quinquennale (`NaN` si la fiche ne chiffre pas) |
| H2f | Direction de cette estimation (−1, 0, +1) |
| H3f | Âge de cette estimation en mois |
| E1 | Interdiction d'exportation de céréales active dans le pays (0/1) |
| E2 | Fermeture de frontière ou sanctions actives (0/1) |

## 6. Plan d'évaluation

- **Origine glissante.** Pour chaque mois d'origine t de 2020-12 à 2026-07 :
  - les modèles globaux sont réentraînés chaque mois sur les couples dont le mois cible est ≤ t ;
  - l'historique est plafonné à 120 mois ;
  - les modèles par série sont réajustés à chaque origine.
- **Règle de coût fixée d'avance.** Si le réentraînement mensuel est projeté à plus de 8 h de calcul, les modèles globaux sont réentraînés tous les 3 mois. Les modèles par série restent mensuels.

**Ensembles d'évaluation, par mois cible :**

| Ensemble | Cibles | Statut |
| :--- | :--- | :--- |
| **DEV** | 2021-01 → 2025-08 | **Principal pour H1 à H4.** Ces périodes ont servi à concevoir la référence (W1 et W2 ont servi à la sélection) : ces résultats sont une preuve de développement, pas une confirmation. |
| **W3** | 2025-09 → 2026-08 | **A posteriori uniquement** : déjà consulté. Rapporté séparément, jamais utilisé pour confirmer. |
| **W4** | ≥ 2026-11, données publiées jusqu'au 2027-02-15 | **Confirmatoire.** Calculé **une seule fois**, avec un code figé par un tag posé avant le calcul. h = 1 et 3 sont principaux ; h = 6 est exploratoire, car très peu de cibles sont disponibles. Si W4 ne contient aucun retournement, H1 et H4 y sont déclarés « non testables ». |

- **Lien avec les résultats publiés.** Le protocole figé de `v1.0-baseline` est relancé tel quel. Ses chiffres doivent reproduire `docs/results/forecast-report.md`, sinon c'est une anomalie à rapporter.

## 7. Régimes et retournements

- **Variation connue à l'origine** : r(t) = ln P(t) − ln P(t−12). Elle n'est définie que si les deux mois sont observés ; sinon, régime « indéterminé », exclu et compté.
- **Régime à l'origine** :
  - **hausse** si r(t) > ln(1,10) ;
  - **baisse** si r(t) < ln(0,90) ;
  - **calme** sinon.

  **Justification** : environ 10 % sur un an, c'est l'ordre de grandeur d'une inflation alimentaire forte. Les épisodes étudiés vont de −27 % à +88 % (EDA, cadrage). **Sensibilité** : seuils de 5 % et de 15 %.
- **Variation réalisée** : dₕ(t) = ln P(t+h) − ln P(t).
- **Retournement à la baisse (H1)** : régime hausse et dₕ(t) < −0,05.
- **Retournement à la hausse (H1b)** : régime baisse et dₕ(t) > +0,05.

  Ces sous-ensembles utilisent l'avenir : ils servent **uniquement au diagnostic** (où l'erreur se produit), jamais comme variable de prévision.

## 8. Métriques

**Erreur ponctuelle :**
- **principale** : erreur absolue **mise à l'échelle (MASE)**. Le dénominateur est l'erreur moyenne de `SeasonalNaive` dans l'échantillon, **calculée jusqu'à l'origine t** ;
- secondaires : MAPE, gain relatif face à la persistance.

**Intervalles à 80 % :**
- couverture (PICP) ;
- largeur moyenne relative au prix prévu ;
- *interval score* de Winkler ;
- perte pinball aux quantiles 0,1 et 0,9 ;
- **CRPS approché** = moyenne des pertes pinball aux quantiles 0,1 à 0,9.

## 9. Intervalles

Les méthodes sont appliquées à chaque famille. Elles ne peuvent utiliser que les erreurs dont la cible est ≤ t, ce qui produit un retour d'erreur décalé de h mois.

| Méthode | Définition |
| :--- | :--- |
| `SCP-12` (référence) | Quantiles conformes des erreurs relatives des 12 derniers mois disponibles, par (pays, groupe, modèle, horizon), avec correction d'échantillon fini |
| `ACI` (Gibbs & Candès, 2021) | Niveau αₜ mis à jour à chaque origine avec toutes les erreurs arrivées à échéance : α ← α + γ(0,20 − taux de non-couverture observé). γ = 0,005 ; sensibilité 0,001, 0,01 et 0,05. αₜ est borné dans [0,01 ; 0,99], et chaque passage par une borne est compté. |
| `WCP` (pondération temporelle ; Barber et al., 2023) | Quantiles pondérés de toutes les erreurs passées (au plus 120 mois), poids 0,5^(âge/12) (demi-vie de 12 mois) ; sensibilité 6 et 24 mois |

## 10. Hypothèses et règles de décision (fixées a priori)

Statistique commune :
- la perte mise à l'échelle est moyennée par mois d'origine, horizon et ensemble ;
- elle donne une série mensuelle de différences de perte d(t) entre deux modèles ;
- test de **Diebold-Mariano** sur d(t), avec une variance robuste à l'autocorrélation (h − 1 décalages) et la correction de **Harvey-Leybourne-Newbold** (loi de Student) ;
- intervalle de confiance à 95 % par **bootstrap par blocs mobiles** (blocs de 6 mois, 2 000 tirages, graine 42) ;
- **correction de Holm** sur la famille de tests de chaque hypothèse, définie ci-dessous ;
- seuil 5 %.

| Hypothèse | Énoncé | Test et famille | Confirmée si |
| :--- | :--- | :--- | :--- |
| **H1** | La perte de `LightGBM_Global` face à `Naive` se concentre sur les retournements à la baisse | DM-HLN unilatéral sur les origines de retournement à la baisse, h ∈ {1,3,6} : famille de 3 tests | ≥ 2 horizons significatifs après Holm, **et** différence moyenne sur les origines calmes inférieure à celle des retournements, **et** part de l'excès de perte venant des retournements > part de ces origines |
| **H1b** | Idem pour les retournements à la hausse | Même structure, famille de 3 tests | Mêmes critères |
| **H2** | `LightGBM_Global` extrapole l'élan des 12 derniers mois | Pente β_pred de la régression du log-rendement prévu sur r(t), toutes origines DEV ; pente réalisée β_real sur les retournements ; IC par bootstrap par blocs | β_pred > 0 **et** β_real < β_pred, les deux avec un IC à 95 % qui exclut 0 pour β_pred et pour la différence |
| **H3** | ACI ou WCP rapprochent la couverture à 6 mois de 80 % pour un surcoût de largeur borné | Sur DEV à h = 6, globalement et sur les retournements | Pour au moins une méthode : \|PICP − 80\| < \|PICP_SCP-12 − 80\| **et** largeur moyenne ≤ 1,25 × celle de SCP-12 sur les mêmes origines |
| **H4** | Les facteurs réduisent la perte lors des retournements | DM-HLN unilatéral entre `LightGBM_Global+F` et `LightGBM_Global` sur les retournements DEV (bas + haut), h ∈ {1,3,6} : famille de 3 tests ; ablation descriptive | ≥ 2 horizons significatifs après Holm. Confirmation finale seulement si W4 va dans le même sens (sans exigence de significativité, vu la taille de W4) |

**Un résultat « non confirmé » est rapporté tel quel.** Aucun seuil, aucune fenêtre ni aucune variable n'est changé après avoir vu un résultat.

## 11. Reproductibilité

- Image Docker de recherche séparée (`agriprix-research`), avec des dépendances verrouillées dans un lock dédié. Les images du produit ne changent pas.
- **Tous les tableaux et toutes les figures** sont produits par `make research-report`, dont l'équivalent `docker compose` est documenté. Aucun chiffre n'est saisi à la main.
- Les fichiers de facteurs (`harvest_giews.csv`, `events.csv`) sont versionnés. Les fichiers CHIRPS bruts ne le sont pas : leur liste et leur somme de contrôle sont enregistrées.
- Branche `research/regime-shift` : tests existants verts, couverture ≥ 70 %.

## 12. Déviations

| Date | Changement | Raison | Avant / après avoir vu un résultat |
| :--- | :--- | :--- | :--- |
| — | aucune | — | — |

## 13. Utilisation d'outils d'IA

- L'étude est conduite par Ahmad avec l'assistance de Claude Code (Anthropic) pour :
  - la rédaction de ce protocole ;
  - le code ;
  - l'extraction proposée des chiffres de récolte et des événements.
- **Ahmad décide** des choix méthodologiques, **valide chaque fait** des tables de facteurs et rédige l'introduction et la discussion du rapport.
- Les références de la littérature citées par l'assistant sont vérifiées par Ahmad avant d'être citées.

## 14. Références (à vérifier par Ahmad)

- Barber, R. F., Candès, E. J., Ramdas, A., Tibshirani, R. J. (2023). *Conformal prediction beyond exchangeability*. Annals of Statistics.
- Diebold, F. X., Mariano, R. S. (1995). *Comparing predictive accuracy*. Journal of Business & Economic Statistics.
- Gibbs, I., Candès, E. (2021). *Adaptive conformal inference under distribution shift*. NeurIPS.
- Harvey, D., Leybourne, S., Newbold, P. (1997). *Testing the equality of prediction mean squared errors*. International Journal of Forecasting.
- Holm, S. (1979). *A simple sequentially rejective multiple test procedure*. Scandinavian Journal of Statistics.
- Hyndman, R. J., Koehler, A. B. (2006). *Another look at measures of forecast accuracy*. International Journal of Forecasting.
- Künsch, H. R. (1989). *The jackknife and the bootstrap for general stationary observations*. Annals of Statistics.
