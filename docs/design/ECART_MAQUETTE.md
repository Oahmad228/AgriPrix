# Écart entre la maquette v2 et le tableau de bord Streamlit

Référence : `docs/design/maquette-v2/export/` (SPEC.md, accueil.png, fiche-marche.png, mobile.png). État mesuré le 2026-11-18 sur la branche `ux/identite-visuelle`, Streamlit 1.67.0, Plotly 5.24.1. Comparaisons côte à côte : `docs/design/captures/v2-comparaison-{accueil,fiche,mobile}.png`.

## Ce que Streamlit 1.67 permet (vérifié dans le conteneur)

| Fonction | Disponible | Utilisée pour |
| --- | --- | --- |
| `st.navigation(position="top")` | oui | barre de navigation en haut, au lieu de la barre latérale |
| `st.logo` | oui | logo complet + « AgriPrix » dans l'en-tête |
| `st.pills` | oui | puces Pays |
| `st.segmented_control` | oui | horizon 1/3/6 mois, période 1 an/5 ans/tout |
| `on_select` sur `st.plotly_chart` | oui, points **et** zones de pays (`choroplethmap`) | clic sur un marché → fiche ; clic sur un pays → choix du pays |
| Thème `.streamlit/config.toml` | oui (couleurs, police, rayons, tailles de titres) | jetons de couleur, Public Sans |
| CSS injecté (`st.markdown`) | oui, via les classes `st-key-*` et `data-testid` | fond des filtres, puces arrondies, filet de l'en-tête, rayons 8 px |
| `st.context.url`, `st.query_params` | oui | adresse partageable |

## Tableau des écarts

| Élément | Maquette | Avant (phase A) | Faisable en Streamlit ? | Comment / état |
| --- | --- | --- | --- | --- |
| En-tête | barre vert foncé, logo, onglets, recherche | barre latérale vert foncé | oui, sauf la recherche | Fait : en-tête **clair** (décision d'Ahmad), logo complet, 5 onglets (`st.navigation` en haut), filet rouille. Recherche « Chercher un marché » : non faite (pas de champ de recherche dans la barre de navigation Streamlit) → phase B ; la liste « Marché » de la fiche en tient lieu. |
| Onglet actif | fond paille | — | partiellement | Style natif de Streamlit (fond léger + texte en gras) ; le thème ne permet pas de fixer sa couleur de fond. |
| Filtres | puces Pays + liste Produit sur fond doux | listes dans la barre latérale | oui | Fait : `st.pills` + `st.selectbox` dans un bloc crème. |
| « Recevoir les alertes » | bouton | — | non (pas de service d'envoi) | Non affiché (phase B : architecture SMS / e-mail à proposer). |
| « Partager cette vue » | bouton qui copie l'URL | — | oui (approché) | Fait : menu qui affiche l'adresse avec un bouton de copie (Streamlit ne copie pas directement dans le presse-papiers). |
| Accueil « Ce mois-ci » | phrase-question, carte 2/3, alertes 1/3, sans clic | carte + liste de boutons | oui | Fait, avec les vraies données. |
| Carte | réelle (exigence), symboles ▲ ▼ ○ | réelle | oui, sauf les triangles | Fait : OSM, marchés WFP, contours geoBoundaries, pays cliquables, vue « Tous », Maroc teinté avec son étiquette, Côte d'Ivoire « consultation seule ». Les marqueurs restent des disques (MapLibre dans Plotly n'a ni triangles colorables ni glyphes ▲ ▼) → l'état est porté par la couleur, le mot et le signe sur la carte, le symbole dans la légende, le survol et la liste. Triangles : phase B (MapLibre GL). |
| Alertes | bloc par alerte, phrase « X, alors qu'environ Y étaient attendus », soudure, gravité, lien | boutons pleine largeur | oui | Fait. |
| « Ce qui pèse sur les prix » | 4 blocs | absent | oui | Fait, valeurs « [à intégrer] » (aucun chiffre inventé). |
| « Plus fortes variations attendues » | tableau à barres + badge | onglet séparé | oui (HTML) | Fait ; liste complète dans un volet dépliable. |
| Fil d'Ariane | Pays › Produit › Marché | absent | oui | Fait (liens). |
| Phrase-résumé | en gras sur l'écart et le niveau prévu | phrase simple | oui | Fait. |
| Actions de la fiche | Suivre, Comparer, CSV, lien | absent | CSV et lien : oui ; Suivre et Comparer : non | CSV et lien faits. Suivre / Comparer → phase B (comptes utilisateurs). |
| Bloc « Prix et prévision » | sélecteurs, graphique, panneau latéral | graphique + badge | oui | Fait, avec le tableau des horizons sous le graphique. |
| « Pourquoi cette prévision ? » | facteurs et contributions | absent | oui | Fait, « [contribution à calculer] » / « [à intégrer] » (SHAP en phase B). |
| « Ce qui s'est passé » | chronologie sourcée | absent | oui | Fait avec les alertes AgriPrix de la série ; événements GIEWS/PREGEC « [à intégrer] » (tables non encore validées par Ahmad). |
| « Marchés voisins » | 4 marchés proches | absent | oui | Fait : 4 plus proches à vol d'oiseau (coordonnées WFP), même produit, dernier prix et distance. |
| Mobile 390 px | listes Pays/Produit, alertes en blocs, barre de navigation en bas | colonnes empilées | partiellement | Fait : puces sur une ligne défilante, carte pleine largeur, alertes sous la carte, liens ≥ 44 px, titre réduit. Barre de navigation **en bas** : impossible (Streamlit la met en haut ou dans un menu) → phase B. Hauteur de carte fixe (470 px) au lieu de 60 % de l'écran. |
| Typographie | Public Sans, échelle 32/22/18/15-16/13-14 | Public Sans, 28/22/18 | oui | Fait (thème + CSS mobile). |
| Formes | rayons 8/6/999, bordure 1 px, ni ombre ni dégradé | 6 px partout | oui | Fait par CSS (rayon des blocs et des puces). |
| Couleurs | vert foncé + paille | vert foncé + paille | oui | Remplacées par la charte tirée du logo (DESIGN.md). |

## Mode sombre (maquette `*-sombre.png`, refait le 2026-11-18)

| Élément | Maquette sombre | Réalisé | Écart restant et cause |
| --- | --- | --- | --- |
| Couleurs | SPEC « Mode sombre » | identiques, aucune retouche (toutes AA mesurées) | — |
| En-tête | `#16211C`, filet `#2B3A32`, onglet actif paille | identique | Barre de navigation de Streamlit : la recherche n'y est pas (phase B). |
| Barre pays/produit, puces | fond doux, puce active verte pleine | identique | Libellé « Pays » au-dessus des puces, pas à gauche (mise en page des widgets Streamlit). |
| Blocs, tableaux, menus | `#18231E`, bordures `#33423A` | identique | Menus déroulants et tableaux interactifs : couleurs du thème Streamlit (mêmes valeurs). |
| Carte | sombre (schéma dans la maquette) | vraie carte CARTO Dark Matter, crédit visible | La maquette dessine un pays schématique ; la vraie carte montre aussi les pays voisins. |
| Marqueurs | anneaux gris, triangles ▲ ▼ | anneau gris creux / point plein coloré deux fois plus gros | Pas de triangles : la carte Plotly n'en dessine pas (phase B). Symbole et mot dans la légende, le survol et la liste. |
| Graphique | fond du bloc, soudure paille 13 % | identique | — |
| Bouton clair/sombre | (non dessiné dans la maquette) | dans l'en-tête, 44 px | Épinglé par CSS dans la bande de l'en-tête (pas d'emplacement prévu par Streamlit). |
| Choix du thème | — | adresse, puis dernier choix du bouton, puis système | Repose sur la clé interne `stActiveTheme-<page>-v2` de Streamlit 1.67 : à revérifier à chaque mise à jour de Streamlit. |

## Reste pour la phase B (React + MapLibre), non commencée

- Marqueurs triangulaires ▲ ▼ sur la carte et ajustement exact aux limites du pays, quelle que soit la largeur.
- Barre de navigation en bas sur téléphone, recherche de marché dans l'en-tête.
- Suivre un marché, comparer, alertes SMS / e-mail.
- Mise en page au pixel près (onglet actif paille, carte à 60 % de la hauteur d'écran).
- Facteurs, contributions (SHAP) et chronologie avec les vraies données externes.
