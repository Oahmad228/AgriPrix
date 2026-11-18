# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les dates sont celles de la fusion dans `main`.

## [Non publié] — branche `ux/identite-visuelle` (identité visuelle)

### Ajouté
- Logo : versions transparente, carrées, horizontale, en-tête, favicons et icônes, toutes tirées du logo complet, utilisé tel quel (transparence d'origine), par `scripts/build_logo_assets.py` ; `docs/design/logo/LOGO.md`.
- Charte de couleurs mesurée sur le logo, dans un seul fichier de jetons (`src/dashboard/tokens.py`), avec tests de contraste WCAG AA et d'écart entre l'accent de marque et le rouge d'alerte.
- Site en pages : Ce mois-ci, Marchés (fiche), Facteurs, Fiabilité, Données & API, avec un en-tête clair et le logo.
- Accueil selon la maquette v2 : puces de pays, carte et alertes côte à côte, facteurs « [à intégrer] », plus fortes variations attendues.
- Fiche marché selon la maquette v2 : fil d'Ariane, actions CSV et lien, panneau de prévision, facteurs, chronologie, marchés voisins.
- Changer de pays en cliquant sur la carte ; vue « Tous » avec tous les pays suivis ; Maroc (indice national) et Côte d'Ivoire (consultation seule) signalés.
- Écart maquette / réalisé : `docs/design/ECART_MAQUETTE.md` et captures `docs/design/captures/v2-*`.

### Ajouté (mode sombre)
- Mode sombre automatique (suit le système) et bouton « Mode sombre » / « Mode clair » dans l'en-tête ; le choix est gardé dans l'adresse (`&theme=sombre`).
- Palette sombre tirée du logo (bleu nuit, crème, feuille, bleu-vert de l'iris, ocre), contrastes AA vérifiés par test dans les deux modes ; carte CARTO Dark Matter ; logo à œil blanc en mode sombre.

### Modifié
- Le cache du tableau de bord dépend de l'identifiant du run publié : les nouveaux chiffres s'affichent moins d'une minute après une mise à jour, au lieu d'une heure.
- La molette ne zoome plus la carte (elle faisait défiler la carte au lieu de la page) : boutons + / − et pincement.
- Adresse : `h=` remplace `horizon=` et le produit est en français (`produit=mais`) ; les anciennes adresses restent comprises.

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
