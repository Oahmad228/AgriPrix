---
name: AgriPrix Observatory
description: Staple food prices of the Sahel and Morocco, read against the farming calendar.
colors:
  ink: "#21254A"
  text-muted: "#4F536B"
  axis: "#5D6175"
  surface: "#FFFFFF"
  surface-soft: "#F6F4EE"
  border: "#D9D6CC"
  grid: "#ECEAE3"
  select: "#3F6A1F"
  forecast: "#1E5066"
  forecast-fan: "rgba(82, 148, 146, 0.22)"
  link: "#1E5066"
  season: "#DA9435"
  season-tag: "#F6E2BC"
  brand: "#97570D"
  alert-up: "#B3261E"
  alert-down: "#4A5568"
  normal: "#6B7085"
typography:
  body:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  heading-1:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
  heading-2:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 650
  heading-3:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
  note:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 400
rounded:
  block: "8px"
  button: "6px"
  pill: "999px"
  tag: "4px"
components:
  header:
    backgroundColor: "{colors.surface}"
    borderBottom: "2px solid {colors.brand}"
  filter-bar:
    backgroundColor: "{colors.surface-soft}"
    rounded: "{rounded.block}"
  pill-active:
    backgroundColor: "{colors.select}"
    rounded: "{rounded.pill}"
  season-tag:
    backgroundColor: "{colors.season-tag}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tag}"
---

# Design System: AgriPrix Observatory

> Charte v2 du 2026-11-18 : maquette v2 (`docs/design/maquette-v2/export/SPEC.md`) appliquée dans Streamlit, couleurs mesurées sur le logo. **Source unique des couleurs dans le code : `src/dashboard/tokens.py`** ; `.streamlit/config.toml` les répète (le TOML ne peut pas importer Python) et `tests/unit/test_tokens.py` échoue si les deux divergent ou si un jeton passe sous son seuil de contraste.

## Overview

"Calendrier des saisons", habillé par le logo : une surface Operate où chaque prix se lit contre le calendrier agricole du Sahel. En-tête clair avec le logo complet, puces de filtre, blocs encadrés sobres. Le geste signature reste la bande de soudure (juin-septembre) sur chaque graphique, maintenant en ocre des épis.

## Logo

Voir `docs/design/logo/LOGO.md`. **Le logo est toujours montré entier** (décision d'Ahmad du 2026-11-18) : en-tête (logo + « AgriPrix », 44 px de haut), favicon, icônes d'application, README. On ne le découpe pas, on ne le redessine pas, on ne le recolore pas.

## Colors

Couleurs du logo mesurées par k-means sur ses pixels (`docs/design/logo/palette-mesuree.json`), puis rôles :

| Rôle | Jeton | Valeur | Contraste sur blanc / fond doux |
| --- | --- | --- | --- |
| Encre (texte, ligne des prix) | `INK` | `#21254A` bleu nuit de l'iris | 14,70 / 13,37 |
| Texte secondaire | `TEXT_MUTED` | `#4F536B` | 7,55 / 6,86 |
| Axes, légendes | `AXIS` | `#5D6175` | 6,12 / 5,56 |
| Sélection, puce et onglet actifs | `SELECT` | `#3F6A1F` vert feuille foncé (texte blanc 6,38) | 6,38 / 5,80 |
| Prévision (ligne), liens | `FORECAST`, `LINK` | `#1E5066` bleu-vert de l'iris | 8,77 / 7,97 |
| Intervalle à 80 % | `FORECAST_FAN` | bleu-vert clair `#529492` à 22 % | — |
| Période de soudure | `SEASON` | `#DA9435` ocre des épis, 22 % d'opacité | — |
| Étiquette « soudure » | `SEASON_TAG_BG` | `#F6E2BC` (encre dessus : 11,57) | — |
| Accent de marque (filet de l'en-tête) | `BRAND` | `#97570D` | 5,7 / 5,2 |
| Hausse anormale | `ALERT_UP` | `#B3261E` + ▲ + « Hausse » | 6,54 / 5,94 |
| Baisse anormale | `ALERT_DOWN` | `#4A5568` + ▼ + « Baisse » | 7,53 / 6,84 |
| Marché normal | `NORMAL` | disque blanc à bord `#6B7085` + ○ + mot | 4,90 / 4,46 |

Fond `#FFFFFF`, fond doux crème `#F6F4EE`, bordures `#D9D6CC`, grilles `#ECEAE3`.

### Named Rules
- **La rouille de marque n'est jamais une alerte.** La rouille du logo `#A53F12` est trop proche du rouge d'alerte (CIEDE2000 = 8,6 < 20). L'accent est `#97570D`, la couleur la plus proche de cette rouille qui respecte ΔE2000 ≥ 20 avec le rouge d'alerte et 4,5:1 sur blanc (recherche exhaustive). Le rouge d'alerte n'a pas changé.
- **Un état = couleur + symbole + mot.** Rouge `#B3261E` + ▲ + « Hausse », ardoise `#4A5568` + ▼ + « Baisse ». En deutéranopie simulée, le rouge devient kaki et l'ardoise reste foncée : les états restent distincts, et surtout portés par le symbole et le mot (`docs/design/captures/v2-daltonisme-deuteranopie.png`). Sur la carte, les polices de MapLibre ne savent pas dessiner ▲ / ▼ : l'étiquette porte le mot et le signe (« Dori : hausse +32 % »), la légende, le survol et la liste portent le symbole.
- **La fiabilité en mots** : « ● Fiabilité correcte » (≥ 70 %), « ◐ moyenne » (50-69 %), « ○ faible » (< 50 %), toujours suivie de « la fourchette a été juste N fois sur 100 en test ». Un biais médian récent de 10 % ou plus ajoute une phrase sous la prévision ; la prévision servie n'est jamais corrigée.
- **Contraste vérifié par test** : WCAG AA, 4,5:1 pour le texte et 3:1 pour les éléments graphiques, sur blanc et sur fond doux.

## Typography

Public Sans (OFL, auto-hébergée dans `src/dashboard/static/fonts`) partout. Échelle de la SPEC : titre de page 32 px / 700 (26 px sous 640 px de large), section 22 px / 650, bloc 18 px / 600, texte 15-16 px, notes 13-14 px. Chiffres tabulaires dans les tableaux. Espace insécable avant « ? » et trait d'union insécable dans les titres (« mois‑ci ? » ne se coupe pas).

## Layout

En-tête clair (logo complet + navigation : Ce mois-ci, Marchés, Facteurs, Fiabilité, Données & API) souligné d'un filet rouille de 2 px. Chaque page commence par sa réponse, puis une barre de filtres sur fond doux : puces Pays (Tous + 6 pays, une seule ligne défilante sur téléphone) et liste Produit (et Marché sur une fiche). L'adresse porte l'état : `?pays=BFA&produit=mais&marche=<id>&h=3&periode=5ans`.

- **Accueil** : titre-question et date, carte réelle (2/3) et alertes (1/3, sous la carte sur téléphone), « Ce qui pèse sur les prix » (4 blocs « [à intégrer] »), « Plus fortes variations attendues dans 3 mois » (tableau à barres, badge de fiabilité), pied de page avec les attributions.
- **Fiche marché** : fil d'Ariane, titre, phrase-résumé, dernier relevé et source, actions (CSV, lien), bloc « Prix et prévision » (horizon 1/3/6 mois, période 1 an/5 ans/tout, graphique, panneau latéral, tableau des horizons), « Pourquoi cette prévision ? », « Ce qui s'est passé », « Marchés voisins ».

## Elevation & Depth

Plat : aucune ombre, aucun dégradé. Blocs encadrés sobres (bordure 1 px `#D9D6CC`, rayon 8 px, sans fond) pour un objet chacun ; jamais imbriqués, jamais en tuiles KPI.

## Shapes

Rayons : 8 px blocs, 6 px boutons et champs, 999 px puces, 4 px étiquette de saison. Bordure 1 px.

## Components

### Market map
Plotly `Scattermap` + `Choroplethmap` (MapLibre) sur tuiles OpenStreetMap, sans clé : marchés aux seules coordonnées WFP (les marchés sans coordonnées sont nommés sous la carte), pays couverts en zones cliquables (un clic choisit le pays et zoome dessus ; les puces restent synchronisées), contour du pays choisi 2,2 px encre et régions du Burkina 0,8 px gris (geoBoundaries), Maroc teinté avec l'étiquette « Indice national des prix alimentaires ». Marché normal : disque blanc à bord gris. Zoom par boutons + / − ou pincement ; la molette fait défiler la page. Mention « © contributeurs OpenStreetMap » visible.

### Alert list
Un bloc par marché en alerte : nom, symbole et écart, « X XOF/kg, alors qu'environ Y étaient attendus pour la saison », mois, étiquette « en période de soudure », gravité, lien « Voir la fiche du marché → » (vrai `<a>`, cible ≥ 44 px). Le plus fort écart d'abord.

### Season chart (signature)
Prix relevés en ligne encre 2 px ; valeurs agrégées en cercles creux « non mesurée » ; alertes ▲ / ▼ ; prévision en tirets bleu-vert avec son éventail à 80 % ; ligne pointillée à l'origine ; bandes ocre de soudure ; axe des années (trimestres en vue 1 an, mois en français).

## Do's and Don'ts

### Do:
- Montrer le logo entier.
- Dessiner la soudure sur chaque graphique d'une série sahélienne.
- Donner la date et la source à côté de chaque donnée, et la fiabilité mesurée à côté de chaque prévision.
- Calculer chaque phrase à partir des nombres qu'elle décrit.

### Don't:
- Découper, déformer ou recolorer le logo.
- Utiliser la couleur seule pour un état, ou une paire rouge/vert ; utiliser l'accent rouille pour une alerte.
- Ajouter des tuiles KPI, cartes décoratives, cadres imbriqués, ombres, dégradés ou animations décoratives.
- Écrire une affirmation que l'API ne peut pas soutenir.
