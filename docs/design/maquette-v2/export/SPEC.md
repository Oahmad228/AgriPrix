# AgriPrix v2 : spécification de l'interface

Export de la maquette validée par Ahmad le 18/11/2026. Source : canevas « AgriPrix Observatory, maquette v2 ».

## Fichiers

| Fichier | Contenu |
| --- | --- |
| `accueil.html` + `accueil.png` | Accueil « Ce mois-ci », bureau (1440 px) |
| `fiche-marche.html` + `fiche-marche.png` | Fiche marché, bureau (1440 px) |
| `mobile.html` + `mobile.png` | Accueil, téléphone (390 × 844) |
| `../Accueil.dc.html`, `../FicheMarche.dc.html`, `../Mobile.dc.html` | Sources d'origine (format de l'outil de maquettage, avec l'interaction 1/3/6 mois) |

Les pages HTML s'ouvrent directement dans un navigateur. Ce sont des **spécifications visuelles**, pas du code de production.

## Ce qui est illustratif (à remplacer par du réel)

- **Les chiffres** sont des exemples tirés de l'API au 18/11/2026 (maïs, Burkina Faso). En production, **tout chiffre vient de l'API**, avec sa date et sa source.
- **La carte de l'accueil est schématique** (forme inventée, points posés à la main). En production : **vraie carte**, voir plus bas.
- **Le graphique de la fiche marché est un tracé illustratif.** En production : graphique Plotly réel, avec la période de soudure, les alertes et l'intervalle.
- **Les facteurs « [à intégrer] »** restent ainsi tant que les données externes ne sont pas dans l'entrepôt. On ne les remplace jamais par un chiffre inventé.

## Charte (reprise de DESIGN.md)

| Rôle | Valeur |
| --- | --- |
| Encre | `#1E2B24` |
| Texte secondaire | `#4E5A53` (notes), `#5B6660` (axes) |
| Fond | `#FFFFFF`, fond doux `#F1F4F1` |
| Bordures | `#D6DDD8`, grilles `#E6EBE7` |
| Vert saison des pluies (en-tête, sélection) | `#24453A`, variantes `#2F5649`, `#3E6658` |
| Paille de mil (onglet actif, soudure) | `#E9C46A` (28 % d'opacité sur les graphiques) |
| Prévision | `#2A6F97` (intervalle à 16 %) |
| Liens | `#1F5A7A` |
| Hausse anormale | `#B3261E` + ▲ + mot « Hausse » |
| Baisse anormale | `#4A5568` + ▼ + mot « Baisse » |

**Police :** Public Sans, auto-hébergée, chiffres tabulaires dans les tableaux.

**Échelle de texte :**
- titre de page 32 px / 700 ;
- titre de section 22 px / 650 ;
- titre de bloc 18 px / 600 ;
- texte 15–16 px ;
- notes 13–14 px.

**Formes :**
- rayon 8 px pour les blocs, 6 px pour les boutons, 999 px pour les puces de filtre ;
- bordure 1 px `#D6DDD8` ;
- aucune ombre, aucun dégradé.

**Mise à jour de DESIGN.md :** la règle « pas de cartes » est remplacée par « blocs encadrés sobres (bordure 1 px, sans ombre) ». La règle « pas de tuiles KPI » reste.

## Principes UX (non négociables)

1. **La réponse avant les filtres.** L'accueil répond à « Où les prix sont-ils anormaux ce mois-ci ? » sans aucun clic.
2. **Une phrase avant un chiffre.** Chaque fiche commence par un résumé en français simple, calculé à partir des données.
3. **La fiabilité en mots.** Badge correcte / moyenne / faible ; les seuils sont proposés par Claude Code et validés par Ahmad. Le détail s'affiche au survol et dans « Comment lire cette prévision ? ».
4. **Le biais n'est pas caché.** Sous la prévision, quand |biais récent| ≥ 10 % : « Ces derniers mois, ce modèle a surestimé (ou sous-estimé) le prix de X % en moyenne à N mois. »
5. **Tout est partageable.** L'URL porte l'état : `?pays=BFA&produit=mais&marche=<id>&h=3`.
6. **Accessible.**
   - Cibles tactiles ≥ 44 px, contraste AA.
   - Jamais la couleur seule : ▲ ▼ ● toujours accompagnés de mots.
   - Vrais `<button>`, `<a>` et `<label>`.
7. **Rien d'inventé.**

## Écran 1 : Accueil « Ce mois-ci »

Ordre de haut en bas :

1. **En-tête vert.**
   - Logo, puis la navigation : Ce mois-ci (actif, fond paille), Marchés, Facteurs, Fiabilité, Données & API.
   - Recherche « Chercher un marché, un produit… ».
2. **Titre-question et date des données**, plus deux boutons : « Recevoir les alertes » (Phase B) et « Partager cette vue » (copie l'URL).
3. **Barre de filtres** sur fond doux :
   - puces Pays : Tous, Burkina Faso, Mali, Niger, Sénégal, Côte d'Ivoire, Maroc ;
   - liste Produit.
4. **Carte réelle (2/3 de la largeur)** et **liste des alertes (1/3)**. Sur téléphone, la liste passe sous la carte.
   - Chaque alerte : marché, ▼/▲ et écart, phrase « X XOF/kg, alors qu'environ Y étaient attendus », mois, étiquette de saison (paille), gravité, lien « Voir la fiche du marché → ».
5. **« Ce qui pèse sur les prix »** : 4 blocs de facteurs (pluie, récolte, carburant, exportations), chacun avec sa source. Afficher « [à intégrer] » tant que la donnée manque.
6. **« Plus fortes variations attendues dans 3 mois »** :
   - un tableau avec barre horizontale de variation, triée par valeur absolue ;
   - le badge de fiabilité à droite du titre ;
   - le nom du marché est un lien vers sa fiche.
7. **Pied de page** : attributions WFP/FAO obligatoires, mention « sans validation du WFP ni de la FAO », liens API et Méthode.

## La carte réelle (exigence d'Ahmad)

**Fond :**
- Fond OpenStreetMap réel (frontières, villes, routes), attribution « © contributeurs OpenStreetMap » visible.
- Aucune clé payante.
- Phase A : Plotly `scatter_map` (MapLibre, déjà installé). Phase B : MapLibre GL.

**Marchés :**
- Placés uniquement à leurs **coordonnées GPS WFP**.
- Un marché sans coordonnées n'apparaît pas ; leur nombre est écrit sous la carte.

**Symboles :**
- ▲ rouge : hausse anormale ;
- ▼ ardoise : baisse anormale ;
- ● cercle blanc à bord gris : normal ;
- la légende en mots est toujours visible.

**Passer d'un pays à l'autre :**
- Cliquer une puce Pays recentre la carte sur ce pays (ajustement aux limites du pays). Cliquer un pays sur la carte sélectionne la puce. Les deux restent synchronisés.
- « Tous » montre l'ensemble des pays suivis.
- **Maroc** : pas de marchés (indice national FAOSTAT). Le pays est coloré en entier, avec l'étiquette « Indice national des prix alimentaires ».
- **Côte d'Ivoire** : marchés affichés avec la mention « consultation seule, pas de prévision » (valeurs agrégées WFP).

**Contours :** contours des pays, et si c'est simple, régions administratives, depuis une source ouverte et citée (par exemple geoBoundaries, CC BY 4.0).

**Interactions :**
- *Au survol* : nom du marché, dernier prix en XOF/kg, mois du relevé, écart à la normale, prévision à 3 mois et badge de fiabilité.
- *Au clic* : ouvre la fiche du marché (sous la carte en Phase A, page dédiée en Phase B) et met à jour l'URL.

**Mobile :** la carte occupe environ 60 % de la hauteur d'écran, déplacement et zoom au doigt, filtres au-dessus.

**Contrôle :** vérifier à la main Ouagadougou, Ouahigouya et Dori (position et valeurs).

## Écran 2 : Fiche marché

1. **Fil d'Ariane** : Pays › Produit › Marché.
2. **Titre** « Produit à Marché » et **phrase-résumé** calculée. Exemple : « Le prix est 25 % sous son niveau habituel pour la saison (220 XOF/kg en juillet 2026). Dans 3 mois, il devrait rester autour de 220 XOF/kg. » Puis le dernier relevé et la source.
3. **Actions** :
   - Suivre ce marché (Phase B) ;
   - Comparer (Phase B) ;
   - Télécharger (CSV) ;
   - Copier le lien (bouton icône avec `aria-label`).
4. **Bloc « Prix et prévision »** :
   - sélecteur d'horizon 1 / 3 / 6 mois ;
   - sélecteur de période 1 an / 5 ans / tout ;
   - graphique avec années sur l'axe, soudure, alertes, prévision en pointillé et intervalle ;
   - panneau latéral : prévision, fourchette, badge de fiabilité, note de biais, lien « Comment lire cette prévision ? ».
5. **« Pourquoi cette prévision ? »** : liste des facteurs avec leur contribution (Phase B, valeurs SHAP). Afficher « [à calculer] » ou « [à intégrer] » d'ici là.
6. **« Ce qui s'est passé »** : chronologie d'événements sourcés (date, texte, source), aussi placés sur le graphique.
7. **« Marchés voisins »** : 4 marchés proches, même produit, avec leur dernier prix, pour voir si le mouvement est local ou général.

## Écran 3 : Mobile

- En-tête compact avec bouton de recherche.
- Titre-question.
- Deux listes Pays et Produit côte à côte.
- Alertes en blocs cliquables.
- Bouton « Recevoir ces alertes » (Phase B).
- Barre de navigation en bas : Ce mois-ci, Carte, Marchés, Suivis.

## Ce qui va en Phase A (Streamlit) et en Phase B (nouveau site)

| Élément | Phase A | Phase B |
| --- | --- | --- |
| Carte réelle, passage d'un pays à l'autre, survol | oui | oui (MapLibre) |
| Phrase-résumé, badge de fiabilité, note de biais | oui | oui |
| URL partageable | oui (`st.query_params`) | oui |
| Axe des années, choix de période | oui | oui |
| En-tête vert avec navigation, mise en page exacte | au plus près possible dans Streamlit | exact |
| Facteurs, « Pourquoi », chronologie | blocs « [à intégrer] » | avec les vraies données |
| Suivre, comparer, alertes SMS / e-mail | non | oui (architecture à proposer) |

Si Streamlit empêche de reproduire un élément proprement, le signaler à Ahmad plutôt que de bricoler.

## Mode sombre

Fichiers : `accueil-sombre.html/.png`, `fiche-marche-sombre.html/.png`, `mobile-sombre.html/.png`, sources `../MainSombre.dc.html`, `../MarcheSombre.dc.html`, `../MobileSombre.dc.html`. Même contenu et même mise en page que le thème clair, seules les couleurs changent.

| Rôle | Clair | Sombre |
| --- | --- | --- |
| Fond de page | `#FFFFFF` | `#111A16` |
| Fond des blocs | `#FFFFFF` | `#18231E` |
| Fond doux | `#F1F4F1` | `#1E2B25` |
| En-tête | `#24453A` | `#16211C` + filet `#2B3A32` |
| Encre | `#1E2B24` | `#E6EDE9` |
| Texte secondaire | `#4E5A53` / `#5B6660` | `#AEBAB3` / `#9AA79F` |
| Bordures / grilles | `#D6DDD8` / `#E6EBE7` | `#33423A` / `#27342D` |
| Sélection (puces, bouton principal) | `#24453A` | `#2E7D62`, bordure `#3F8F70` |
| Paille (onglet actif, soudure) | `#E9C46A`, texte `#1E2B24` | identique ; soudure à 13 % d'opacité au lieu de 28 % |
| Prévision | `#2A6F97` | `#62AEDB` |
| Liens | `#1F5A7A` | `#86C6EC` (survol `#B3DCF3`) |
| Hausse anormale | `#B3261E` + ▲ + mot | `#F0837B` + ▲ + mot |
| Baisse anormale | `#4A5568` + ▼ + mot | `#A9B6C9` + ▼ + mot |

Ces valeurs viennent de la maquette. Elles seront harmonisées avec les couleurs du logo et vérifiées au contraste (WCAG AA) lors de l'intégration.
