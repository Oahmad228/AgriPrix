# ADR-006 : Gestion des devises locales (`XOF`, `MAD`), des indices (`INDEX`) et conversion à la demande sous *Feature Flag*

- **Statut** : Accepté
- **Date** : 2026-11-03
- **Décideurs** : Amine & Ingénieur Data/Logiciel Junior
- **Exigences liées** : `EF-05`, `EF-06`, `EF-07`, `US-04`, `US-06`

---

## 1. Contexte et Problème

Le périmètre géographique d'AgriPrix Observatory couvre deux zones monétaires et deux natures de mesures :
1. **5 pays de la zone UEMOA (`SEN`, `MLI`, `BFA`, `NER`, `CIV`)** : Tous partagent la même devise locale, le **Franc CFA d'Afrique de l'Ouest (`XOF`)**, qui bénéficie d'une **parité fixe historique avec l'Euro** ($1\text{ EUR} = 655{,}957\text{ XOF}$). Les prix y sont exprimés en `XOF/kg` (ou normalisés en `XOF/kg` / `XOF/L`).
2. **Maroc (`MAR` via FAOSTAT)** :
   - La série mensuelle prévisible (`Item 23013`, IPC alimentaire) est un **indice sans unité monétaire (`value_type = 'INDEX'`, base `2015 = 100`, `currency_code = 'NONE'`)**.
   - Les séries annuelles consultables (Prix producteurs `PP`) sont exprimées en **Dirham marocain (`MAD/tonne`)**, en `USD/tonne` ou en indice (`2014-2016 = 100`).

**Piège méthodologique à éviter** :
Si l'on convertissait en amont (dans l'ETL) tous les prix `XOF` et `MAD` en Dollars américains (`USD`) avant d'entraîner les modèles de prévision ou le détecteur d'anomalies, **une hausse du Dollar face à l'Euro (donc face au Franc CFA `XOF`) créerait une fausse anomalie de prix alimentaire local**, alors même que le prix payé par le ménage dakarois ou bamakois sur son marché en `XOF` n'aurait pas bougé d'un centime !

---

## 2. Décision

1. **Stockage, détection d'anomalies et entraînement ML 100 % en devise locale d'origine (ou indice natif)** :
   - Toutes les tables de faits (`fact_price_observation`, `fact_forecast`, `fact_anomaly`) stockent exclusivement les valeurs dans leur devise ou unité native (`XOF`, `MAD`, ou `NONE` pour `INDEX`).
   - Les modèles de prévision et les $Z$-scores saisonniers opèrent **strictement en devise locale** pour mesurer la réalité économique vécue par les ménages locaux, sans bruit de change exogène `EUR/USD`.
2. **Interdiction formelle de convertir un `INDEX` en devise** :
   - Toute série ayant `value_type != 'PRICE'` (comme l'IPC alimentaire du Maroc en base `2015 = 100`) ignore tout paramètre de conversion monétaire.
3. **Table de taux de change datés (`dim_exchange_rate`) et conversion uniquement à la couche d'exposition API sous *Feature Flag*** :
   - Un **Feature Flag** (un interrupteur de configuration permettant d'activer ou de désactiver une fonctionnalité sans modifier le code, ici `ENABLE_CURRENCY_CONVERSION=false` par défaut dans `.env`) contrôle la conversion à la volée dans `FastAPI`.
   - Lorsque ce drapeau est activé et que l'utilisateur passe le paramètre optionnel `?display_currency=EUR` ou `?display_currency=USD` sur `/api/v1/prices` (uniquement pour les séries où `value_type == 'PRICE'`), l'API effectue la jointure avec la table `dim_exchange_rate (from_currency, to_currency, reference_year, reference_month, exchange_rate)` correspondant au mois exact de l'observation (et non un taux unique figé sur 25 ans).
   - Par défaut dans le MVP, l'affichage se fait en devise locale (`XOF` pour l'UEMOA, indice `2015=100` ou `MAD` pour le Maroc), la parité au sein des 5 pays UEMOA étant déjà strictement identique ($1\text{ XOF} = 1\text{ XOF}$).

---

## 3. Conséquences

- **Zéro contamination monétaire des modèles ML** : Les prévisions et anomalies reflètent uniquement les dynamiques des marchés agricoles locaux.
- **Évolutivité propre** : La table `dim_exchange_rate` est présente dans le schéma en étoile (alimentée a minima par la parité fixe officielle `XOF/EUR = 655.957` et les moyennes mensuelles `MAD/EUR` et `USD` si le *Feature Flag* est activé), sans alourdir le MVP.
