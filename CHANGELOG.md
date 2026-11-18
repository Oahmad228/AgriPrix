# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les dates sont celles de la fusion dans `main`.

## [Non publié] — branche `ux/quick-wins` (phase A)

### Corrigé
- Intervalles de prévision à 80 % : la fourchette est maintenant symétrique sur l'échelle logarithmique (rayon = ⌈(n+1)×0,8⌉-ième plus petite valeur de |ln(prix réel / prévision)|), donc toujours positive et contenant sa prévision. Avant, 365 prévisions sur 2 346 tombaient hors de leur propre fourchette (7 groupes, tous à 6 mois). Détails : ADR-004 §3 et `docs/results/interval-methods-comparison.md`.
### Ajouté
- Carte réelle des marchés (fond OpenStreetMap, contours geoBoundaries, positions WFP uniquement ; les marchés sans coordonnées sont nommés sous la carte). Survol : dernier prix, mois, écart à la normale, prévision à 3 mois avec sa fiabilité. Clic : ouvre la fiche du marché.
- Fiche marché : phrase de synthèse, badge de fiabilité en mots (correcte ≥ 70 %, moyenne 50-69 %, faible < 50 %) et phrase de biais quand l'erreur médiane récente dépasse ±10 %.
- Choix de la période du graphique (1 an, 5 ans, tout) et une étiquette par année (par trimestre sur un an).
- Adresse partageable : pays, produit, marché, horizon et période sont dans l'URL.
- API : champ `last_value` sur `/series`, champs `recent_bias_pct` et `interval_method` sur `/forecasts`.

### Modifié
- Alertes récentes : liste de boutons pleine largeur (cible tactile ≥ 44 px) au lieu d'un tableau avec case à cocher.
- Onglet « Méthode & qualité » : modèles renommés en français courant, phrase d'explication au-dessus du graphique.
- DESIGN.md : la règle « pas de cartes » devient « blocs encadrés sobres » ; ajout de la carte, de la liste d'alertes et des seuils de fiabilité.

## [v1.0-baseline] — 2026-11

Première version complète : ETL WFP/FAOSTAT, prévisions à 1, 3 et 6 mois, alertes, API FastAPI, tableau de bord Streamlit. Voir `docs/JOURNAL.md`.
