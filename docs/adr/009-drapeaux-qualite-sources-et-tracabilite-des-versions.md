# ADR-009 : Drapeaux qualité des sources (FAOSTAT E/I exclus du ML) et traçabilité des versions de fichiers

- **Statut** : Accepté
- **Date** : 2026-11-10
- **Décideurs** : Ahmad (choix des options) & assistant IA (Claude Code)
- **Exigences liées** : `EF-03`, `EF-07`, `ENF-03`, `DQ-01`, `DQ-02`, `DQ-06`, `DQ-07`
- **Précise** : [`ADR-002`](./002-entrepot-postgresql-etoile-multi-grains.md) (colonne `source_flag`), `docs/diagrams/06-modele-donnees.md` (valeur `official_faostat`)

---

## 1. Contexte

En implémentant l'ETL (Sprint 1), deux faits ont été constatés par exécution :

1. **FAOSTAT publie un drapeau qualité par valeur** (colonnes `Y2007F`, … du CSV « flaggé », absentes du `*_NOFLAG.csv` utilisé lors de l'audit). Pour le Maroc :
   - IPC alimentaire `23013` : **2000–2006 = `I`** (*valeur imputée par la FAO*) et **2007–2026 = `X`** (*chiffre officiel transmis par un organisme externe*) ;
   - inflation alimentaire `23014` : 100 % `E` (*estimée*) ;
   - prix producteurs : mélange de `A` (officiel), `E` (estimé), `X` et valeurs sans drapeau.

   La conception traitait jusqu'ici toute valeur FAOSTAT comme « officielle » (`official_faostat`, `is_observed = TRUE`). C'était incohérent avec la règle du projet : ne jamais entraîner un modèle sur une valeur calculée par un autre traitement (règle déjà appliquée aux lignes WFP `aggregate`).
2. **HDX met à jour les fichiers WFP en continu.** Le fichier du Sénégal est passé de 54 039 lignes (audit du 2026-11-03) à 55 283 (2026-11-10). Un même code donne donc des chiffres différents selon la date du téléchargement.

## 2. Options étudiées et décision

### 2.1 Drapeaux FAOSTAT : option retenue par Ahmad, « exclure E et I du ML »

| `source_flag` en base | Origine | `is_observed` |
| :--- | :--- | :---: |
| `actual` | WFP, relevé réel sur le marché | ✅ |
| `aggregate` | WFP, moyenne calculée | ❌ |
| `fao_official` | FAOSTAT `A` ou sans drapeau | ✅ |
| `fao_external` | FAOSTAT `X` (organisme externe, ex. institut national) | ✅ |
| `fao_break` | FAOSTAT `B` (rupture de série, valeur réelle) | ✅ |
| `fao_estimated` | FAOSTAT `E` | ❌ |
| `fao_imputed` | FAOSTAT `I` | ❌ |

Toutes les valeurs sont chargées et consultables. Seules les valeurs `is_observed = TRUE` comptent pour l'éligibilité au ML. Une contrainte `CHECK` empêche en base toute incohérence entre `source_flag` et `is_observed`.

*Option écartée* : tout traiter comme observé (318 mois pour `23013` au lieu de 234). Cela donnait plus d'historique, mais mélangeait des valeurs imputées par la FAO avec de vraies mesures.

**Conséquence mesurée** : la série `23013` reste éligible, avec **234 mois observés continus (2007-01 → 2026-06)**, largement au-dessus du seuil de 60 mois.

### 2.2 Versions des fichiers : option retenue par Ahmad, « télécharger et tracer »

- Chaque `make etl` interroge le fournisseur. Il télécharge un fichier seulement si son MD5 diffère de la copie locale, puis vérifie la taille et le MD5 publiés (`DQ-01` / `DQ-02`).
- La table `etl_source_file` enregistre, pour chaque exécution, le MD5, la taille, l'URL et la date de modification de chacun des 7 fichiers. Tout chiffre publié est relié à une exécution (`etl_run_id`), donc à des versions exactes de fichiers.
- Le mode `--offline` réutilise les fichiers locaux sans contacter les fournisseurs. Il enregistre quand même leur MD5.
- Une copie figée des fichiers de l'audit est conservée localement (`data/raw/snapshot_20261103/`, non versionnée). Elle sert de **test de réconciliation** : sur ces fichiers, l'ETL doit retrouver exactement les 738 séries éligibles de l'audit.

*Option écartée* : figer un instantané versionné dans le dépôt. Les chiffres seraient parfaitement stables, mais il faudrait un second mécanisme pour la mise à jour mensuelle (Sprint 4), et les fichiers bruts (~40 Mo) n'ont pas leur place dans Git.

## 3. Conséquences

- **Positives** :
  - réconciliation exacte avec l'audit : 738 séries sur la copie figée (BFA 275, MLI 230, NER 187, SEN 45, MAR 1) ;
  - chaque chiffre du README est traçable jusqu'au MD5 du fichier source.
- **Négatives** :
  - les comptages évoluent avec les mises à jour de HDX. Le README doit toujours citer l'`etl_run_id` et la date des données ;
  - le seuil d'alerte `DQ-07` (baisse > 5 % du nombre de séries éligibles) se compare désormais à l'exécution réussie précédente, et non à la valeur figée 738.
