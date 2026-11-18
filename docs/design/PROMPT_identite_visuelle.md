# Mission : identité visuelle d'AgriPrix (maquette v2 + logo)

Tu reprends AgriPrix Observatory après la phase A (commit `82f1764` sur `ux/quick-wins`, non fusionné). Cette mission porte sur l'intégration graphique : appliquer la maquette v2 validée, intégrer le nouveau logo, et en tirer une charte cohérente. Le fond (données, modèles, API) ne change pas, sauf pour les deux points listés à l'étape 5.

Travaille en autonomie. Si une demande est impossible avec Streamlit, dis-le en une phrase, propose la meilleure approximation, puis continue. Arrête-toi seulement avant une action irréversible : fusionner dans `main`, toucher Neon ou publier.

## 0. Point de départ et branche

- Réponse à ta question de fin de phase A : **ne fusionne pas encore.** Crée `ux/identite-visuelle` à partir de `ux/quick-wins`. On fusionnera les deux ensemble quand j'aurai validé les captures de cette mission.
- Lis avant de coder :
  - `docs/design/maquette-v2/export/SPEC.md` : la spécification ;
  - `accueil.png`, `fiche-marche.png`, `mobile.png` : la cible visuelle ;
  - les `.html` du même dossier : mesures, espacements et textes exacts ;
  - `DESIGN.md`, `PRODUCT.md` ;
  - `docs/design/captures/apres-*.jpg` : l'état actuel.
- Ajoute `docs/design/maquette-v2/` au dépôt dans cette branche : c'est maintenant la référence.

## 1. Écart entre l'état actuel et la maquette (avant de coder)

Écris `docs/design/ECART_MAQUETTE.md` : un tableau `élément | maquette | actuel | faisable en Streamlit ? | comment`. Couvre au moins :

- l'en-tête : barre haute avec logo et onglets, au lieu de la barre latérale vert foncé ;
- les filtres : puces pays / produit / horizon en haut, au lieu des menus de la barre latérale ;
- l'accueil « Ce mois-ci » : phrase-réponse, carte et liste d'alertes, sans clic ;
- la fiche marché : phrase, badge, biais, graphique, tableau des horizons, facteurs « [à intégrer] » ;
- le mobile à 390 px ;
- la typographie : Public Sans auto-hébergée, chiffres tabulaires, échelle de la SPEC ;
- les formes : rayons 8/6/999 px, bordure 1 px, aucune ombre ni dégradé.

Vérifie la version de Streamlit installée et ce qu'elle permet : `st.pills`, `st.segmented_control`, `st.logo`, `on_select` sur les graphiques Plotly, thème dans `.streamlit/config.toml`, CSS injecté. Ensuite, réalise tout ce qui est faisable. Note ce qui ne l'est pas pour la phase B (React + MapLibre), sans la commencer.

## 2. Le logo

J'ai placé l'image source ici : **`docs/design/logo/agriprix-logo-source.png`** (2048 × 2048 px, fond blanc). C'est un œil aux paupières à motifs africains, entouré d'épis, avec un iris en radar et une ligne de prévision verte. Elle a été générée avec Gemini puis retouchée (yeux plissés). C'est le logo retenu : **ne le redessine pas et ne change pas sa forme.**

Produis dans `docs/design/logo/`, avec un script reproductible `scripts/build_logo_assets.py` (Pillow / OpenCV) :

1. **`agriprix-logo.png`** : fond rendu transparent **seulement à l'extérieur**. Remplis depuis les bords de l'image ; le blanc à l'intérieur de l'œil reste blanc. Recadre au plus près avec une marge de 4 %. Exporte aussi en 1024, 512 et 256 px.
2. **`agriprix-logo-horizontal.png`** : le logo à gauche, puis « AgriPrix » en Public Sans 700, et en dessous « Observatoire des prix agricoles » en 400, plus petit.
3. **Favicon et icône d'application.** Les motifs fins disparaissent sous 64 px. Fais une version simplifiée : **l'iris seul** (disque bleu nuit, anneau ocre, point vert au centre), recadré en cercle, éventuellement avec le point orange. Exporte `favicon-16/32/48.png`, `favicon.ico`, `icon-192.png` et `icon-512.png`. Montre-moi les deux options (logo complet réduit, iris seul) côte à côte en 16, 32 et 48 px dans une capture, et choisis la plus lisible.
4. **`LOGO.md`** :
   - versions et usages ;
   - zone de protection : la hauteur de l'iris ÷ 4 ;
   - taille minimale : 96 px pour le logo complet, en dessous l'iris seul ;
   - ce qu'il ne faut pas faire : déformer, recolorer, poser sur une photo chargée ;
   - origine : généré avec Gemini, retouché, pas de vérification d'antériorité de marque.

Intégration :
- `st.set_page_config(page_icon=...)` avec le favicon ;
- le logo horizontal dans l'en-tête, avec `st.logo` ou du HTML ;
- le logo en haut du `README.md` ;
- la page de l'API (`/docs`) si c'est simple.

## 3. Charte : harmoniser la maquette avec le logo

Mesure les couleurs réelles du logo par échantillonnage : nuages de pixels, k-means, sans deviner. Je m'attends à peu près à :

| Élément du logo | Couleur |
| --- | --- |
| Bleu nuit de l'iris | `#22264F` |
| Bleu-vert de l'iris | `#2C6E7A` |
| Rouille des paupières | `#A9441F` |
| Ocre des épis | `#E0A13A` |
| Vert feuille et ligne | `#6FA83A` |
| Point orange | `#F26B3A` |

Puis mets à jour les jetons de couleur, **dans DESIGN.md et dans le code au même endroit** (un seul fichier de jetons) :

- **En-tête clair** : fond blanc ou crème très léger, logo en couleur. On abandonne le vert foncé en aplat : je le trouve triste à côté du logo.
- **Rôles proposés** :
  - Encre : bleu nuit du logo, ou garder `#1E2B24` si le contraste est meilleur.
  - Sélection et onglet actif : vert feuille foncé.
  - Prévision et intervalle : bleu-vert de l'iris. Il remplace `#2A6F97`, sauf si le contraste baisse.
  - Période de soudure : ocre des épis, à faible opacité.
  - Accent de marque : rouille, uniquement pour des détails (filet sous l'en-tête, puce active). Jamais pour une alerte.
- **États d'alerte inchangés dans leur logique.** Hausse = rouge `#B3261E` + ▲ + mot ; baisse = gris ardoise + ▼ + mot.
  - Vérifie que le rouge d'alerte reste **nettement différent** de la rouille de marque (ΔE ≥ 20).
  - Sinon, ajuste la rouille, pas le rouge.
- **Contraste vérifié par un script** : WCAG AA, 4,5:1 pour le texte et 3:1 pour les éléments graphiques, sur fond blanc et sur fond doux. Ajoute un test qui échoue si un jeton passe sous le seuil.
- **Contrôle daltonisme** : les états restent lisibles en deutéranopie, ce qui est garanti par le symbole et le mot. Fais une capture simulée.

## 4. Appliquer la maquette

Reproduis les écrans de la maquette avec **les vraies données de l'API** (aucun chiffre de la maquette ne doit survivre) :

- Accueil bureau.
- Fiche marché bureau.
- Mobile à 390 px : les puces passent sur une ligne défilante ; la carte prend toute la largeur ; les alertes viennent sous la carte ; les boutons font au moins 44 px.
- Garde tout ce que la phase A a construit : carte réelle, survol et clic, URL partageable, badge de fiabilité, biais, choix de période, onglet Méthode.

## 5. Deux points de fond liés à l'interface

1. **Changer de pays depuis la carte.** Je veux pouvoir passer d'un pays à l'autre sur la carte elle-même, pas seulement dans un menu.
   - Proposition : une vue « Afrique de l'Ouest » qui montre les contours réels (geoBoundaries, déjà en place) de tous les pays couverts. Un clic sur un pays met à jour `?pays=` et zoome sur ce pays.
   - Si le clic sur un polygone ne marche pas bien dans Streamlit avec Plotly, utilise des puces de pays juste au-dessus de la carte, avec le zoom automatique. Dis-moi lequel tu as fait.
   - **Uniquement de vraies cartes :** fond OpenStreetMap, vraies frontières, marchés aux coordonnées du WFP. Aucune forme dessinée à la main.
2. **Cache après mise à jour mensuelle.** Aujourd'hui, le site peut afficher d'anciennes prévisions pendant une heure. Fais dépendre la clé de cache de l'identifiant du dernier run, lu par une requête légère, pour que les nouveaux chiffres apparaissent dès la publication.

## 5 bis. Mode sombre

La maquette existe aussi en sombre : `docs/design/maquette-v2/export/accueil-sombre.png`, `fiche-marche-sombre.png` et `mobile-sombre.png`, avec leurs `.html` et les sources `*Sombre.dc.html`. Les jetons sombres sont dans `SPEC.md`, section « Mode sombre ».

- Reproduis-le comme second thème.
- Ajoute un bouton clair/sombre dans l'en-tête, avec un vrai bouton, un libellé et une cible de 44 px.
- Garde le choix dans l'URL (`&theme=sombre`). Par défaut, suis la préférence du système (`prefers-color-scheme`).
- Fais suivre la carte : un fond OpenStreetMap sombre si la licence et les tuiles le permettent (par exemple CARTO Dark Matter, avec son attribution). Sinon, garde le fond clair et dis-le.
- Fais suivre le graphique Plotly (`template`) et la légende.
- Le logo a un fond blanc à l'intérieur de l'œil. Vérifie son rendu sur fond sombre et propose une pastille claire derrière si besoin.
- Les contrôles de contraste et de daltonisme de l'étape 3 s'appliquent aux deux thèmes. Prends les captures de l'étape 6 dans les deux thèmes.

## 6. Vérification (obligatoire, dans le navigateur)

- Captures après la mission dans `docs/design/captures/v2-*` :
  - accueil et fiche, en bureau et sur téléphone ;
  - favicon dans l'onglet ;
  - comparaison des favicons ;
  - simulation daltonisme.
- Pour chaque écran, une capture côte à côte « maquette | réalisé ». Liste les écarts restants et leur cause.
- Les 3 marchés témoins (Ouagadougou-Sankaryare, Ouahigouya, Dori) : les chiffres affichés égalent la base, comme en phase A.
- Tests, lint et couverture : rien ne baisse ; les nouveaux tests passent (jetons et contraste, script du logo, changement de pays).
- Recherche de secrets avant le commit. `data/external/` reste hors du commit.
- Mets à jour `DESIGN.md` (nouvelle charte, logo, en-tête clair) et le `CHANGELOG`.

## 7. Compte rendu attendu

En français simple, court :
1. ce qui est fait, vérifié dans le navigateur ;
2. les écarts avec la maquette et pourquoi ;
3. les couleurs finales avec leurs rôles et leurs contrastes ;
4. le favicon choisi et le rendu du logo en sombre ;
5. la méthode retenue pour changer de pays ;
6. ce qui reste pour la phase B.

Puis demande-moi si tu fusionnes `ux/quick-wins` + `ux/identite-visuelle` dans `main`.
