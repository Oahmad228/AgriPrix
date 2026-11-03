# Phase 0 — Étude de l'Existant : Observatoires des Prix Alimentaires (Version révisée)

> **Note pédagogique (Lexique intégré)** : Chaque sigle ou terme technique employé pour la première fois dans ce document est expliqué simplement en une phrase entre parenthèses.

---

## 1. Objectif de l'étude de l'existant

En ingénierie logicielle et en **AMOA** (*Assistance à Maîtrise d'Ouvrage*, activité qui consiste à définir le besoin métier et à vérifier qu'une solution répond aux attentes des utilisateurs avant de la coder), une étude de l'existant — ou **benchmark** (*analyse comparative des outils concurrents ou similaires déjà présents sur le marché*) — évite deux pièges :
1. **Réinventer l'existant sans valeur ajoutée** : recréer un simple catalogue de téléchargement de prix historiques alors que les Nations Unies le fournissent déjà.
2. **Ignorer les bonnes pratiques et l'actualité du domaine** : méconnaître les API déjà offertes par HDX ou FEWS NET et les règles de rigueur statistique (distinction entre prix observés et estimations, séparation entre indices mensuels et prix annuels).

Nous avons analysé **cinq grandes familles de systèmes existants** couvrant l'Afrique de l'Ouest et le Maroc.

---

## 2. Analyse détaillée des solutions existantes

### 2.1 WFP VAM DataViz, HungerMap LIVE & Portail HDX (Programme Alimentaire Mondial / ONU)
- **Organisme** : Branche **VAM** (*Vulnerability Analysis and Mapping*, service d'analyse de la vulnérabilité et de cartographie du Programme Alimentaire Mondial) et bureau **UNOCHA** (*Bureau de la coordination des affaires humanitaires de l'ONU*) opérant la plateforme **HDX** (*Humanitarian Data Exchange*).
- **Ce que fait l'outil** : Collecte des relevés mensuels de prix sur des centaines de marchés locaux en Afrique de l'Ouest (Sénégal, Mali, Burkina Faso, Niger, Côte d'Ivoire, etc.), affiche des courbes historiques et calcule l'indicateur **ALPS** (*Alert for Price Spikes*, indicateur statistique du PAM mesurant si le prix actuel dépasse anormalement sa tendance saisonnière).
- **Accès programmatique (API existantes vérifiées)** :
  - **API CKAN de HDX** (`https://data.humdata.org/api/3/action/`) : **API** (*interface programmable*) permettant d'interroger le catalogue de métadonnées et de récupérer les liens des fichiers CSV complets par pays (depuis 1990/2000 jusqu'en 2026). *Note technique constatée lors de notre audit* : le téléchargement répétitif des gros fichiers CSV sur `data.humdata.org` est protégé par un pare-feu **AWS WAF** (*Web Application Firewall*, bouclier de sécurité d'Amazon qui bloque temporairement une adresse IP après 6 ou 7 téléchargements massifs en moins de 3 minutes).
  - **HDX HAPI** (`https://hapi.humdata.org/`, *Humanitarian API*) : API REST moderne documentée avec **OpenAPI** (*standard générant une page web interactive de documentation d'API*) qui permet d'interroger les prix alimentaires en JSON ou CSV sans blocage WAF, mais dont la profondeur historique débute en **2017** (contre 1990/2000 dans les fichiers CSV complets).
- **Limites identifiées au regard de notre besoin** :
  - **Absence du Maroc** dans les relevés par marché local (`wfp-food-prices-for-morocco` n'existe pas).
  - **API purement rétrospective (historique uniquement)** : ni l'API CKAN ni HDX HAPI ne proposent d'endpoint de **prévision à 1, 3 et 6 mois** ni d'**intervalles d'incertitude**.
  - **Présence de lignes agrégées (`priceflag = 'aggregate'`)** dans certains pays (ex. 37,49 % des lignes en Côte d'Ivoire entre 2019 et mai 2026), qu'il faut impérativement filtrer avant tout entraînement de modèle.

### 2.2 FAO FPMA (Food Price Monitoring and Analysis) & FAOSTAT
- **Organisme** : **FAO** (*Organisation des Nations Unies pour l'Alimentation et l'Agriculture*), via son système mondial d'information et d'alerte rapide (**GIEWS** — *Global Information and Early Warning System*).
- **Ce que fait l'outil** :
  - **FPMA** : Outil web de suivi des prix domestiques et de bulletins d'alerte mensuels.
  - **FAOSTAT** : Base statistique macro-économique mondiale publiant notamment l'**IPC alimentaire** (*Indice des Prix à la Consommation alimentaire*, mesure sans devise exprimée par rapport à une base `2015 = 100`) et les prix annuels payés aux producteurs agricoles.
- **Forces** :
  - **Couvre le Maroc au niveau national** via deux jeux de données distincts :
    1. L'**IPC alimentaire mensuel (`base 2015 = 100`)** et le taux d'inflation alimentaire (`%`) de janvier 2000 à 2026 (`318 observations mensuelles continues`).
    2. Les **prix aux producteurs agricoles en `MAD/tonne`** de 1991 à 2025, mais uniquement à une **fréquence annuelle (`ANNUAL`)**.
  - Archives complètes téléchargeables en lot (**Bulk Download** — *téléchargement groupé d'un jeu de données en un seul fichier ZIP*) sur les serveurs **Amazon S3** (`bulks-faostat.fao.org`).
- **Limites identifiées** :
  - **Purement descriptif** : ne fournit pas de prévisions probabilistes à 1, 3 et 6 mois.
  - **Instabilité de l'API directe FAOSTAT** : lors de notre audit du 3 novembre 2026, le serveur d'API `fenixservices.fao.org` renvoyait une erreur **HTTP 521** (*serveur d'origine hors service derrière Cloudflare*), rendant indispensable l'utilisation des archives S3.

### 2.3 Banque Mondiale — RTFP (Real-Time Food Prices)
- **Organisme** : Groupe de la Banque mondiale (publié également sur HDX).
- **Ce que fait l'outil** : Combine des relevés du PAM et des estimations par **imputation** (*remplacement d'une valeur manquante par une estimation issue d'un modèle statistique*) pour reconstruire des séries continues dans les pays fragiles.
- **Limites identifiées** :
  - Mélange des prix observés et des estimations générées par modèle : réentraîner un modèle de prévision sur ces séries estimées provoquerait un **biais de modélisation** (*apprentissage des artefacts d'un algorithme précédent plutôt que de la réalité du marché*).
  - Ne couvre pas le Maroc.

### 2.4 FEWS NET (Famine Early Warning Systems Network) — État vérifié en 2025–2026
- **Organisme** : Réseau d'alerte précoce contre la famine financé historiquement par l'agence américaine **USAID**.
- **État opérationnel et technique actuel (vérifié)** :
  - **Continuité après le gel de début 2025** : Suite aux gels administratifs et budgétaires de l'USAID début 2025 qui avaient temporairement interrompu ses flux, FEWS NET a été partiellement relancé mi-2025 (opéré notamment via le *Data, Learning, and Communications Hub* géré par AIR/Kimetrica).
  - **Portails et API existants** : FEWS NET s'appuie sur le portail principal `fews.net`, le portail géospatial et agro-climatique de l'**USGS** (`earlywarning.usgs.gov`), et le **FDW** (*FEWS NET Data Warehouse*, entrepôt de données interne exposant des points d'accès API REST permettant d'extraire des données structurées, souvent soumis à des identifiants de connexion FDW pour les vues détaillées, avec certains jeux de données relayés sur HDX).
- **Limites identifiées au regard de notre besoin** :
  - Les projections de FEWS NET reposent principalement sur des **scénarios d'experts multidisciplinaires** et des cartes de classification **IPC** (*Integrated Food Security Phase Classification*, échelle de 1 à 5 de gravité des crises alimentaires), et non sur un moteur logiciel open-source et reproductible en conteneurs générant automatiquement à la demande des intervalles de prédiction chiffrés à 1, 3 et 6 mois.
  - Ne couvre pas le Maroc.

### 2.5 Dispositifs régionaux et nationaux (RESIMAO, Afrique Verte, HCP Maroc)
- **Organismes** : **RESIMAO** (*Réseau des Systèmes d'Information des Marchés en Afrique de l'Ouest*), bulletins d'**Afrique Verte** (Sahel : Mali, Burkina Faso, Niger), et **HCP** (*Haut-Commissariat au Plan*) / portail CKAN `data.gov.ma` au Maroc.
- **Limites identifiées** : Diffusion fragmentée entre pays (tableaux Excel/PDF hétérogènes), sans entrepôt ni API unifiant l'Afrique de l'Ouest et le Maroc.

---

## 3. Matrice comparative multicritères

> **Note de lecture** : La dernière colonne présente les **cibles d'AgriPrix Observatory** (distinguant le **Cœur MVP — Sprints 1 à 4** et le **Bonus — Sprint 5**). Aucune fonctionnalité cible n'est présentée comme déjà construite avant son exécution et sa validation dans le sprint correspondant.

| Critère d'évaluation | WFP VAM / HDX | FAO FPMA & FAOSTAT | Banque Mondiale RTFP | FEWS NET (État 2025–2026) | **AgriPrix Observatory (Cibles du projet)** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Afrique de l'Ouest (UEMOA, grain Marché, `XOF`)** | Oui (1990–2026) | Partielle | Oui (Mais prix imputés) | Oui (Sahel) | **Cible MVP (Sprint 1)** : 5 pays UEMOA (`SEN`, `MLI`, `BFA`, `NER`, `CIV`), `priceflag='actual'` pour le ML |
| **Maroc (grain National, distinction IPC mensuel vs Prix annuels)** | Non | **Oui** (IPC mensuel `2015=100` + Prix producteurs annuels `MAD/t`) | Non | Non | **Cible MVP (Sprint 1)** : Séparation stricte `MONTHLY`/`INDEX` (prévu) vs `ANNUAL`/`PRICE` (consulté) |
| **Respect de la devise/unité locale par défaut** | Mixte (Local + USD) | Variable selon l'écran | Local + USD | Local | **Cible MVP (Sprints 1–4)** : 100 % devise/unité locale par défaut ; conversion en **Cible Bonus (Sprint 5)** |
| **Prévisions algorithmiques à 1, 3 et 6 mois** | Non (Historique seul) | Non | Non (Nowcasting passé) | Projections d'experts (IPC) | **Cible MVP (Sprint 2)** : Modèles comparés à 1, 3 et 6 mois sur les 746 séries éligibles ($\ge 60$ mois continus récents) |
| **Intervalles d'incertitude calibrés (Fourchette basse/haute)** | Non | Non | Non | Non | **Cible MVP (Sprint 2)** : Prédiction conforme évaluée par le taux de couverture **PICP** sur le jeu de test |
| **Détection d'anomalies validée sur crises historiques** | Indicateur ALPS | Alertes FPMA | Non | Rapports experts | **Cible MVP (Sprint 3)** : Validée sur crises 2007–2008 et 2022 (taux de détection & fausses alertes) + français simple |
| **API REST publique** | **Oui** (API CKAN + HDX HAPI, historique seul) | API directe instable (`HTTP 521`) | Non (Fichiers CSV) | API FDW (accès complet sous compte) | **Cible MVP (Sprint 3)** : API FastAPI ouverte (historique + prévisions + anomalies) avec *Rate Limiting* et DB *Read-Only* |
| **Open-Source, Docker Compose & Bonus Kubernetes** | Non | Non | Scripts R partiels | Non | **Cible MVP (Phase 3–Sprint 4)** : Docker Compose + CI/CD ; **Cible Bonus (Sprint 5)** : Kubernetes + Prometheus/Grafana |

---

## 4. Positionnement et valeur ajoutée d'AgriPrix Observatory

Notre projet s'appuie sur les sources officielles du PAM (HDX) et de la FAO (FAOSTAT) pour construire une **chaîne décisionnelle et logicielle complète (MIAGE + Data Science + DevOps)** :

1. **Modélisation de données rigoureuse multi-grains et multi-fréquences** :
   - Nous séparons explicitement dans l'entrepôt le niveau de détail géographique (`granularity_level` : `MARKET` vs `NATIONAL`), la fréquence (`frequency` : `MONTHLY` vs `ANNUAL`) et la nature de la mesure (`value_type` : `PRICE` en `XOF` ou `MAD/tonne` vs `INDEX` base `2015=100`), sans jamais inventer de mois fictifs pour les séries annuelles marocaines.
2. **Hygiène scientifique stricte sur les séries temporelles** :
   - Exclusion de toute donnée agrégée ou estimée (`priceflag != 'actual'`) pour l'entraînement ML, exigence d'une fenêtre continue récente d'au moins **60 mois** ($\le 3$ mois manquants consécutifs), évaluation par horizon ($1, 3, 6$ mois) et calibration d'intervalles d'incertitude par prédiction conforme.
3. **Orientation produit sécurisée et accessible aux non-techniciens** :
   - Affichage par défaut des prix de détail (`Retail`), alertes d'anomalies validées sur les crises de 2007–2008 et 2022 et expliquées en français simple, API sécurisée en lecture seule, et rafraîchissement mensuel automatisé.
