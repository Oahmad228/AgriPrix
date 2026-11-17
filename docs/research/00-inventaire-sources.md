# Inventaire des sources de facteurs externes (étude « retournements de prix »)

> Établi le 2026-11-17, avant le protocole et avant tout calcul. But : choisir les 2 ou 3 sources à intégrer d'abord.
> Chaque affirmation est étiquetée :
> - **(a)** vérifié par une commande ou dans nos fichiers ;
> - **(b)** lu dans une source en ligne citée en bas, **à vérifier par Ahmad** ;
> - **(c)** estimation ou supposition.

## 1. Rappel : ce dont l'étude a besoin

Pour chaque facteur, la question est la même : **qu'est-ce qui était publié au mois t ?** Une valeur sans date de publication ne peut pas être utilisée sans risque de fuite.

**Attention au biais du recul :** on a choisi les récoltes et les interdictions d'exportation parce qu'elles semblent expliquer la baisse de W3, déjà vue. Ce choix sera déclaré dans le protocole. Seules les fenêtres W1, W2 et W4 peuvent confirmer l'hypothèse H4.

## 2. Tableau des sources

| Source | Contenu | Période et résolution | Date de publication connue ? | Licence (usage commercial) | Accès | Effort (c) | Intérêt pour H4 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CHIRPS (pluie)** | Pluie mensuelle par satellite et stations | Depuis 1981, grille de 0,05° (~5 km) (b) | Partiellement : provisoire quelques jours après le mois, définitive vers le 15-20 du mois suivant (b). Pas d'archive connue des versions provisoires (b). | Domaine public / CC0, usage commercial autorisé (b) | Copie gratuite sans compte sur Digital Earth Africa (fichiers COG, AWS af-south-1) (a : dossier `rainfall_chirps_monthly/` listé) ; serveur du Climate Hazards Center (a : répond, mais limite le débit avec des erreurs HTTP 429) | 1 jour | **Élevé** : la pluie de la saison précède la récolte de plusieurs mois |
| **GIEWS – fiches pays (FAO)** | Estimations et prévisions de production céréalière, en % de la moyenne, et notes sur les prix et les mesures commerciales | BFA : **29 fiches datées de 2009-09 à 2024-12** (a, archive PDF extraite) ; une fiche plus récente datée du 2025-06-19 (b) ; environ 2 fiches par an et par pays | **Oui** : chaque fiche porte une « Reference Date » (a) | CC BY 4.0, usage commercial autorisé (b) | PDF libres, archive par pays (a) | 2 jours pour 5 pays (saisie assistée + ta validation) | **Élevé** : c'est l'information « récolte au-dessus ou en dessous de la normale » disponible à t |
| **PREGEC / CILSS (avis)** | Prévisions puis résultats définitifs de la campagne agricole, bilans céréaliers, Sahel + Afrique de l'Ouest et par pays | 3 avis par an (septembre, novembre, mars) (b) ; avis trouvés pour 2017, 2020 et 2024 à 2026 (b) | **Oui** : date de la réunion | **Non précisée** (c) : citation des chiffres en recherche probablement acceptable, à confirmer | PDF dispersés sur plusieurs sites (b) | 1 à 2 jours | Élevé, mais redondant avec GIEWS : à utiliser pour **recouper** |
| **Événements : interdictions d'exportation, fermetures de frontières** | Mesures commerciales par pays et par mois | À construire | Oui, par la date du document source | Dépend de la source citée | Construction manuelle à partir de GIEWS, des rapports FEWS NET et du tracker IFPRI | 1 à 2 jours + 2-3 h de ta validation | Moyen à élevé ; peu d'événements |
| ↳ **Tracker IFPRI** | Restrictions d'exportation (nourriture, engrais) | **Depuis 2022** seulement (b) ; 32 pays avec 77 mesures en 2022 (b) | Oui | CC BY 4.0 / ODC-By pour la version COVID ; licence actuelle à confirmer (b) | Food Security Portal (b) | 0,5 jour | Utile pour W1 (2022) et W3, rien avant 2022 |
| ↳ **Rapports FEWS NET** | Perspectives mensuelles, bulletins de prix, mesures commerciales | Longue histoire (b) ; **pause début 2025**, reprise annoncée à partir de juillet 2025 avec des trous de collecte (b) | Oui, date du rapport | À vérifier (c) | Site fews.net (a : répond) ; API des données avec droits variables (b) | Inclus dans la ligne « Événements » | Source principale des événements (et matière pour l'agent LLM plus tard) |
| **FAOSTAT – production agricole** | Production annuelle par culture et par pays | Annuelle ; publiée en décembre pour l'année précédente (b) | Oui, mais **avec ~1 an de retard** (b) | CC BY 4.0 (b) | Téléchargement libre | 0,5 jour | **Faible pour la prévision** (trop tardive) ; utile comme « vérité finale » pour juger les estimations GIEWS/PREGEC |
| **NDVI (végétation)** | Indice de verdure | eMODIS **arrêté depuis 2022** (b) ; successeur eVIIRS par décades (10 jours), 375 m ou 1 km (b) | Partiellement | Domaine public (c, produit USGS) | EarthExplorer ou portail FEWS NET (b) | 2 jours | Moyen ; recoupe en partie la pluie, à repousser |
| **Carburant (local)** | Prix du carburant sur les marchés | **CIV seulement, 7 séries, 24 observations, depuis 2026-06** (a) | — | CC BY-IGO (WFP) | Déjà dans nos fichiers | — | **Inutilisable** sur 2015-2026 |
| **Taux de change** | XOF/USD, MAD | **Absent de nos fichiers WFP** (a) ; le franc CFA a une parité fixe avec l'euro (b) | — | — | BCE (EUR/USD) | 0,5 jour | **Faible** : effet seulement via EUR/USD sur le riz importé |
| **Pétrole (Brent)** | Prix mondial | Quotidien depuis des décennies (b) | Oui | Domaine public (EIA, b) | FRED/EIA | 0,5 jour | Faible, lien lointain avec le mil |
| **Salaires journaliers (Mali)** | Pouvoir d'achat agricole | **MLI, 3 types × 78 séries, 2020-04 → 2026-06** (a) | Comme les prix WFP | CC BY-IGO 3.0 | Déjà dans l'entrepôt | 0,5 jour | Inattendu ; un seul pays, période courte : à garder pour plus tard |
| **ACLED (conflits)** | Événements de conflit géolocalisés | Bonne couverture du Sahel (b) | Oui | **Compte obligatoire, conditions d'usage restrictives** (b) | Inscription | 1 jour | Hors périmètre actuel |

## 3. Recommandation : trois sources pour démarrer

1. **CHIRPS (pluie)** : licence libre, accès sans compte, longue histoire, déjà en grille. Règle de datation prudente : la pluie du mois m n'est utilisable qu'à partir du mois m+1. Pour la sortie définitive (vers le 15-20 de m+1), une règle encore plus prudente, à partir du mois m+2, pourra être testée en sensibilité.
2. **Estimations de récolte GIEWS, recoupées avec PREGEC** : GIEWS est daté fiche par fiche, sous licence CC BY 4.0, avec 29 fiches depuis 2009 rien que pour le Burkina (a). C'est la source la plus directement liée à H4. Je propose les valeurs avec le lien et la page de chaque fiche ; tu valides chaque ligne.
3. **Table manuelle des événements** (interdictions d'exportation, fermetures de frontières, sanctions), sourcée par GIEWS, FEWS NET et IFPRI. Petite (quelques dizaines de lignes), chaque fait avec sa source, sa date de publication et ta validation.

**À repousser :** NDVI, carburant, taux de change, Brent, salaires du Mali, ACLED, agent LLM.

## 4. Points à trancher (décisions d'Ahmad)

1. **Valider ces 3 sources**, ou en retirer une (la table des événements est la plus coûteuse en validation humaine).
2. **Version de CHIRPS.** La v2 sera remplacée par la v3 et sa production continuera en parallèle jusqu'à fin 2026 (b). Or la fenêtre W4 commence en 2026-11 : la v2 risque de s'arrêter pendant W4.
   - Option A : **v3 partout** (historique et W4), cohérent. Je recommande cette option, sous réserve de vérifier que l'historique v3 couvre bien 2005-2026 pour l'Afrique.
   - Option B : v2 pour l'historique et v3 pour W4 : incohérent, à éviter.
3. **Source principale des récoltes** : GIEWS en principal et PREGEC en recoupement (je recommande), ou l'inverse. PREGEC est plus régional, mais sa licence n'est pas claire.

## 5. Ce qui m'a surpris

- **Le tracker IFPRI ne commence qu'en 2022 (b).** Pour les interdictions d'exportation plus anciennes, il faudra s'appuyer sur GIEWS et FEWS NET.
- **eMODIS (NDVI) est arrêté depuis 2022 (b).** Cela renforce l'idée de le repousser.
- **FEWS NET a interrompu ses services début 2025 (b)**, avec des trous de données pendant la période qui précède W3. Cela fragilise les événements de 2025, période justement cruciale.
- **Le Climate Hazards Center limite fortement les téléchargements (a, HTTP 429).** La collecte devra être lente, avec des reprises. Digital Earth Africa est une alternative.

## Sources consultées

- CHIRPS : [catalogue data.gov](https://catalog.data.gov/dataset/chirps-version-2-0-precipitation-global-0-05-monthly-1981-present), [FAQ CHC](https://wiki.chc.ucsb.edu/CHIRPS_FAQ), [CHIRPS 3.0 (USGS)](https://earlywarning.usgs.gov/fews/product/175), [Digital Earth Africa – CHIRPS](https://docs.digitalearthafrica.org/en/latest/data_specs/CHIRPS_specs.html), [registre AWS DE Africa CHIRPS](https://registry.opendata.aws/deafrica-chirps/), [CHC – Early Estimates](https://chc.ucsb.edu/node/396)
- GIEWS : [fiche pays Burkina Faso](https://www.fao.org/giews/countrybrief/country.jsp?code=BFA), [archive PDF BFA](https://cb.apps.fao.org/country/BFA/pdf_archive/BFA_Archive.pdf), [fiche du 19 juin 2025 (ReliefWeb)](https://reliefweb.int/report/burkina-faso/giews-country-brief-burkina-faso-19-june-2025)
- PREGEC : [avis de mars 2026](https://agrhymet.cilss.int/wp-content/uploads/2026/04/Avis-PREGEC-mars-2026.pdf), [avis de novembre 2025](https://agrhymet.cilss.int/wp-content/uploads/2025/11/Avis-PREGEC-Nov2025_FR.pdf), [avis de septembre 2025](https://www.cilss.int/wp-content/uploads/2025/09/AVIS_PREGEC_OUAGADOUGOU_SEPT_2025_FR.pdf), [avis de mars 2017](https://www.inter-reseaux.org/wp-content/uploads/avis_pregec_mars-2017_vfinale.pdf)
- FEWS NET : [relance du site](https://fews.net/fews-net-relaunches-website-resumes-global-food-security-analysis), [données marchés et commerce](https://fews.net/data/markets-and-trade), [API](https://help.fews.net/fdw/fews-net-api)
- IFPRI : [documentation du tracker](https://knowledge4policy.ec.europa.eu/publication/documentation-food-fertilizers-export-restriction-tracker-tracking-export-policy_en), [billet IFPRI 2022](https://www.ifpri.org/blog/food-export-restrictions-have-eased-russia-ukraine-war-continues-concerns-remain-key/)
- NDVI : [aa-toolbox – USGS eMODIS](https://aa-toolbox.readthedocs.io/en/latest/datasources/usgs_ndvi.html), [USGS eVIIRS](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-vegetation-monitoring-eros-visible-infrared-imaging)
- FAOSTAT : [catalogue production agricole](https://data.fao.org/catalog/iso/d24a448b-3b62-4c09-8c1d-4a39bb599876)
- ACLED : [conditions d'utilisation](https://acleddata.com/terms-and-conditions)
