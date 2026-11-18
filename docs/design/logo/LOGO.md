# Logo AgriPrix

Un œil aux paupières à motifs africains, entouré d'épis, avec un iris en radar et une ligne de prévision verte qui se termine par un point orange.

## Versions

Toutes produites par `scripts/build_logo_assets.py`, sans redessiner :

```bash
docker compose --profile jobs run --rm job-runner python scripts/build_logo_assets.py
```

| Fichier | Usage |
| --- | --- |
| `agriprix-logo-source.png` | Source (2000 × 2000 px), à ne pas modifier |
| `agriprix-logo.png` | Logo tel quel (transparence d'origine), recadré avec 4 % de marge |
| `agriprix-logo-1024.png`, `-512.png`, `-256.png` | Mêmes, en carré |
| `agriprix-logo-horizontal.png` | Logo + « AgriPrix » (Public Sans 700) + « Observatoire des prix agricoles » (400) : README, documents |
| `agriprix-lockup.png` | Logo + « AgriPrix », sans sous-titre : en-tête du site (44 px de haut) |
| `favicon-16/32/48.png`, `favicon.ico` | Icône d'onglet : le logo complet réduit |
| `icon-192.png`, `icon-512.png` | Icônes d'application |
| `palette-mesuree.json` | Couleurs mesurées par k-means sur les pixels du logo |

## Règle principale

**Le logo est toujours montré entier.** Ahmad a refusé, le 2026-11-18, une version simplifiée (l'iris seul découpé) : en-tête, favicon et icônes utilisent le logo complet. En dessous de 32 px, les motifs fins des paupières ne se lisent plus, mais la silhouette (œil, iris bleu, épis) reste reconnaissable (`docs/design/captures/v2-favicon.png`).

## Transparence

**Le logo est utilisé directement, tel qu'Ahmad l'a fourni** (décision du 2026-11-18) : le fichier source est déjà transparent, y compris à l'intérieur de l'œil, et le script ne fait que le recadrer et le redimensionner. Une première version remettait du blanc dans l'œil ; elle faisait une tache blanche sur un onglet sombre et a été abandonnée. Le script garde une méthode de détourage (`transparent_logo`) pour le cas d'une source sur fond blanc.

## Zone de protection et taille

- Zone de protection : un espace libre égal à la hauteur de l'iris ÷ 4 autour du logo.
- Taille conseillée : 96 px ou plus pour lire les motifs ; jusqu'à 16 px, le logo reste entier (règle ci-dessus).

## Ce qu'il ne faut pas faire

- Le découper, le déformer, l'étirer ou le faire pivoter.
- Le recolorer ou changer ses couleurs.
- Le poser sur une photo chargée ou un fond qui couvre les motifs.
- Ajouter une ombre, un contour ou un effet.

## Origine

Généré avec Gemini, puis retouché (yeux plissés), et retenu par Ahmad. **Aucune vérification d'antériorité de marque n'a été faite.**
