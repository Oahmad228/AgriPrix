# Correctifs : mode sombre refait à l'identique + problèmes vus dans le navigateur

**Ne fusionne rien dans `main`.** Si la fusion est déjà faite, ne publie rien de plus en ligne tant que cette mission n'est pas validée par moi sur captures.

## 1. Refaire le mode sombre à l'identique de la maquette

Le mode sombre actuel ne respecte pas la maquette. Tu as dérivé un fond bleu nuit `#13162B` du logo, alors que je veux **exactement** la maquette sombre que j'ai validée.

**Supprime le thème sombre actuel** : jetons, CSS et réglages de la carte et de Plotly. Refais-le en partant de zéro sur cette base :

**Références visuelles.** À reproduire au plus près, mêmes couleurs, même mise en page :
- `docs/design/maquette-v2/export/accueil-sombre.png`
- `docs/design/maquette-v2/export/fiche-marche-sombre.png`
- `docs/design/maquette-v2/export/mobile-sombre.png`
- les `.html` à côté (valeurs exactes) et les sources `docs/design/maquette-v2/*Sombre.dc.html`

**Couleurs.** Celles de la section « Mode sombre » de `docs/design/maquette-v2/export/SPEC.md`, **telles quelles** :

| Rôle | Valeur |
| --- | --- |
| Fond de page | `#111A16` |
| Fond des blocs | `#18231E` |
| Fond doux | `#1E2B25` |
| En-tête | `#16211C` + filet bas `#2B3A32` |
| Encre | `#E6EDE9` |
| Texte secondaire | `#AEBAB3` / `#9AA79F` |
| Bordures / grilles | `#33423A` / `#27342D` |
| Sélection | `#2E7D62`, bordure `#3F8F70` |
| Paille (onglet actif, badge soudure) | `#E9C46A` avec texte `#1E2B24` |
| Soudure sur graphique | `#E9C46A` à 13 % |
| Prévision | `#62AEDB` |
| Liens | `#86C6EC`, survol `#B3DCF3` |
| Hausse | `#F0837B` + ▲ + mot |
| Baisse | `#A9B6C9` + ▼ + mot |

Seule exception autorisée : si un contraste mesuré est sous le seuil WCAG AA, ajuste **la luminosité de cette couleur seulement**, et signale-le.

**Chaque partie de la page doit être sombre** : en-tête, onglets, barre pays/produit, puces, menus déroulants, blocs, tableaux, carte, légende de la carte, graphique Plotly et sa légende, boutons, pied de page.

- **Carte** : fond CARTO Dark Matter, avec l'attribution « © OpenStreetMap contributors © CARTO » visible.
- **Logo** : version sombre (œil blanc) dans l'en-tête et le favicon sombre.

Le thème clair ne change pas.

## 2. Une seule source de vérité pour le thème

Dans mon Chrome, la page est un mélange :
- **en sombre** : le fond de page et le menu « Maïs » ;
- **en clair** : l'en-tête, la barre des pays, la carte et la légende ;
- **conséquences** : onglets blancs sur blanc, textes gris illisibles, bouton de thème disparu.

L'URL n'avait pas de `theme`. Cause probable : le thème mémorisé par Streamlit dans le navigateur contredit tes couleurs.

1. **Le thème se décide à un seul endroit**, dans cet ordre :
   1. le paramètre `theme` de l'URL ;
   2. sinon, le dernier choix fait avec le bouton ;
   3. sinon, la préférence du système.

   Streamlit, tes CSS, la carte, Plotly et le logo lisent tous **ce même choix**. Le réglage de thème du menu ⋮ de Streamlit ne doit plus pouvoir créer de mélange : synchronise-le ou masque-le.
2. **Reproduis d'abord le bug** : mémoire Streamlit sur sombre avec `theme=clair` dans l'URL, puis l'inverse. Ensuite corrige.
3. **Teste toutes les combinaisons**, dans un profil Chrome neuf **et** dans Edge :
   - système clair ou sombre ;
   - URL sans `theme`, avec `theme=clair` ou avec `theme=sombre` ;
   - mémoire Streamlit vide, sur clair ou sur sombre.

   Pour chaque cas, un script vérifie dans la page que l'en-tête, la barre des pays, la carte, le graphique, le logo et le bouton sont dans le même thème, et que le bouton est visible.
4. **Contraste mesuré sur les couleurs réellement affichées** (styles calculés dans le navigateur), pas seulement sur les jetons : au moins 4,5:1 pour le texte, 3:1 pour les éléments graphiques, dans les deux thèmes.

## 3. Problèmes vus dans le navigateur (dans les deux thèmes)

1. **Cadrage de la carte.** Elle cadre automatiquement sur le pays choisi (marge d'environ 5 %), pour que le pays remplisse la carte. Aujourd'hui, le Burkina n'en occupe qu'un tiers.
2. **Étiquettes de la carte.** Décale-les pour qu'elles ne couvrent pas les autres points, avec un contour ou un halo pour la lisibilité. Aujourd'hui, « Ouahigouya baisse −25 % » est écrit sur les autres marchés.
3. **Marché normal ou en alerte.** Ils doivent se distinguer d'un coup d'œil :
   - marché normal : point gris neutre et creux ;
   - marché en alerte : point plein, plus gros, dans la couleur de l'état.

   Le symbole et le mot restent.
4. **Espace sous l'en-tête.** Réduis l'espace vide entre l'en-tête et le titre de la page.
5. **Marchés voisins.** Si le dernier relevé a plus de 6 mois, grise la carte du marché et écris « relevé ancien ». Exemple : Markoye affiche juillet 2025 à côté de prix de septembre 2026.
6. **« Ce qui s'est passé ».** Si la dernière alerte a plus de 12 mois, ajoute une phrase : « Aucune alerte depuis [mois année] ». Exemple : Dori n'affiche que des alertes de 2022.
7. **Sahara occidental.** Mon choix n'est pas encore fait. Ne change pas la frontière pour l'instant. Ajoute seulement sous la carte : « Les frontières affichées n'impliquent aucune prise de position. » Je te donnerai la décision séparément.

## 4. Vérification

- **Captures** dans `docs/design/captures/v3-*`, dans les deux thèmes :
  - accueil et fiche marché (Dori), en bureau et sur téléphone ;
  - côte à côte « maquette sombre | réalisé » pour les trois écrans sombres.
- **Une capture par combinaison** de l'étape 2.3, rassemblées en une planche.
- **Les 3 marchés témoins** (Ouagadougou-Sankaryare, Ouahigouya, Dori) : les chiffres égalent la base.
- **Tests** : rien ne baisse. Ajoute des tests pour :
  - la cohérence du thème (combinaisons) ;
  - les contrastes calculés ;
  - le badge « relevé ancien » ;
  - la phrase « Aucune alerte depuis ».
- Recherche de secrets avant commit. `data/external/` reste hors du commit.
- Mets à jour `DESIGN.md`, la section « Mode sombre » de `SPEC.md` (seulement si un ajustement de contraste a été nécessaire) et le `CHANGELOG`.

## 5. Compte rendu

En français simple, court :
1. ce qui est fait et vérifié dans le navigateur ;
2. la cause exacte du mélange de thèmes et comment tu l'as réglée ;
3. les couleurs ajustées pour le contraste, s'il y en a ;
4. les écarts restants avec la maquette sombre et pourquoi.

Puis demande-moi l'accord avant toute fusion dans `main`.
