# Diagramme 01 — Cas d'utilisation (*Use Case Diagram*)

> **Termes techniques introduits dans ce document (en une phrase simple)** :
> - **Diagramme de cas d'utilisation (*Use Case Diagram*)** : Un schéma UML qui représente ce que le système permet de faire du point de vue de ses acteurs externes (humains ou systèmes tiers), sans entrer dans les détails techniques internes.
> - **Relation `<<include>>` (Inclusion obligatoire)** : Une flèche en pointillés signifiant que le cas d'utilisation principal exécute **systématiquement** le sous-cas pointé lors de son exécution.
> - **Relation `<<extend>>` (Extension conditionnelle)** : Une flèche en pointillés pointant vers le cas principal, signifiant qu'un comportement optionnel vient **compléter** le cas de base uniquement sous une condition précise.

---

## 1. Diagramme Mermaid (Rendu natif GitHub)

```mermaid
flowchart LR
    %% Acteurs externes (Gauche : Utilisateurs humains & Clients API ; Droite : Ordonnanceur & Systèmes externes)
    ActorAnalyst["👤 Analyste Sécurité Alimentaire<br/>(Persona 1 : Kofi - ONG / PAM)"]
    ActorDecider["🏛️ Décideur / Chargée d'Études<br/>(Persona 2 : Yasmine - Ministère)"]
    ActorThirdParty["💻 Développeur / Système Tiers<br/>(Client API REST JSON)"]
    ActorCron["⏰ Planificateur Mensuel / DevOps<br/>(Cron / Makefile / GitHub Actions)"]
    ExtSources["🌐 Sources Open Data<br/>(API CKAN HDX WFP & Bulk FAOSTAT)"]

    subgraph SystemBoundary ["Système : AgriPrix Observatory (MVP Docker Compose)"]
        direction TB

        %% Cas d'utilisation Consultation & API
        UC01(["UC-01 : Consulter l'historique d'une série<br/>(Prix Retail XOF/MAD par défaut ou Indice IPC)"])
        UC02(["UC-02 : Filtrer par type de prix ou d'unité<br/>(Basculer Retail vers Wholesale ou Producteur)"])
        UC03(["UC-03 : Convertir l'affichage en EUR/USD<br/>(Condition : Feature Flag actif & value_type = PRICE)"])
        UC04(["UC-04 : Consulter les prévisions pré-calculées (1, 3, 6 mois)<br/>et leurs intervalles conformes à 80 % (si is_ml_eligible = TRUE)"])
        UC05(["UC-05 : Afficher le bandeau d'inéligibilité ML<br/>(Condition : is_ml_eligible = FALSE : série ANNUAL, aggregate ou < 60m)"])
        UC06(["UC-06 : Explorer la carte et les alertes d'anomalies<br/>(Résidu log-tendance-saisonnalité Warning / Critical)"])
        UC07(["UC-07 : Consulter la performance des modèles et des quantiles<br/>(MASE, RelMAE, MAPE, RMSE, PICP Fenêtre 3 & Choc 2022)"])
        UC08(["UC-08 : Exporter / Consommer les données en CSV ou JSON<br/>(/api/v1/prices, /forecasts, /anomalies, /metadata)"])

        %% Cas d'utilisation Pipeline Batch & MLOps
        UC09(["UC-09 : Exécuter le pipeline ETL mensuel<br/>(Collecte, ref_unit_conversion, déduplication et chargement)"])
        UC10(["UC-10 : Vérifier l'intégrité des fichiers téléchargés<br/>(DQ-01 Anti-WAF + DQ-02 Taille, hash MD5 et nb lignes)"])
        UC11(["UC-11 : Calculer et persister le statut is_ml_eligible<br/>dans dim_series_catalog (is_observed=TRUE, fraîcheur <= 3m, >= 60m)"])
        UC12(["UC-12 : Entraîner les 19 groupes de modèles (Rolling-Origin)<br/>et calibrer les quantiles conformes relatifs (training_run)"])
        UC13(["UC-13 : Détecter les anomalies (>= 5 ans, MAD x 1.4826)<br/>et valider le rappel sur les chocs 2007-2008 et 2022"])
    end

    %% Associations Acteurs -> Cas d'utilisation
    ActorAnalyst --> UC01
    ActorAnalyst --> UC04
    ActorAnalyst --> UC06
    ActorAnalyst --> UC07
    ActorAnalyst --> UC08

    ActorDecider --> UC01
    ActorDecider --> UC04
    ActorDecider --> UC06
    ActorDecider --> UC08

    ActorThirdParty --> UC01
    ActorThirdParty --> UC04
    ActorThirdParty --> UC06
    ActorThirdParty --> UC07
    ActorThirdParty --> UC08

    ActorCron --> UC09
    ActorCron --> UC12
    ActorCron --> UC13

    UC09 --> ExtSources

    %% Relations <<include>> (Flèche du cas de base vers le cas inclus obligatoire)
    UC04 -. "<<include>> [lit le catalogue & l'historique]" .-> UC01
    UC09 -. "<<include>>" .-> UC10
    UC09 -. "<<include>> [calcule et sauvegarde is_ml_eligible]" .-> UC11
    UC12 -. "<<include>> [filtre WHERE is_ml_eligible = TRUE]" .-> UC11

    %% Relations <<extend>> (Flèche du cas d'extension vers le cas de base étendu)
    UC02 -. "<<extend>> [si changement du filtre pricetype]" .-> UC01
    UC03 -. "<<extend>> [si ENABLE_CURRENCY_CONVERSION=true & PRICE]" .-> UC01
    UC05 -. "<<extend>> [si dim_series_catalog.is_ml_eligible == false]" .-> UC04
```

---

## 2. Comment lire ce diagramme ?

1. **Quatre acteurs** interagissent avec le système :
   - **L'Analyste (`Kofi`)** et **la Décideuse (`Yasmine`)** utilisent l'interface visuelle Streamlit (qui consomme l'API).
   - **Le Développeur / Système Tiers (`Client API REST JSON`)** interroge directement les endpoints `/api/v1/*` de FastAPI pour intégrer nos séries, prévisions ou alertes dans ses propres notebooks ou outils externes.
   - **Le Planificateur Mensuel / DevOps** exécute les jobs batch (`UC-09`, `UC-12`, `UC-13`).
2. **Distinction claire entre le calcul batch (`UC-11`) et la lecture temps réel (`UC-04` / `UC-05`)** :
   - C'est uniquement lors de l'ETL (`UC-09`) que `UC-11` parcourt tout l'historique pour **calculer et persister** le booléen `is_ml_eligible` dans `dim_series_catalog` (utilisé ensuite par l'entraînement `UC-12`).
   - Lorsqu'un utilisateur consulte une série (`UC-04`), l'API **ne recalcule jamais** l'algorithme d'éligibilité : elle lit simplement le booléen pré-calculé `dim_series_catalog.is_ml_eligible`, et déclenche l'extension `UC-05` (bandeau explicatif) si ce booléen vaut `FALSE`.

---

## 3. Deux questions qu'un recruteur pourrait poser sur ce diagramme

### Question 1 : *« Pourquoi avoir retiré le lien `<<include>>` entre `UC-04 (Consulter les prévisions)` et `UC-11 (Calculer l'éligibilité ML)` ? »*
> **Réponse conseillée** :
> « Parce que recalculer la continuité sur 60 mois et le nombre maximal de mois manquants consécutifs à chaque requête HTTP d'un utilisateur gaspillerait du CPU et violerait la séparation entre le pipeline batch (ETL) et la couche de service (API). L'éligibilité ML d'une série ne change qu'une fois par mois lors de l'ingestion de nouvelles observations : c'est donc `UC-09 (ETL)` qui inclut `UC-11` pour matérialiser `is_ml_eligible` et `ineligibility_reason` dans la table `dim_series_catalog`. En lecture (`UC-04`), l'API se contente d'une lecture indexée en $O(1)$ de cette colonne, et `UC-05` affiche le bandeau d'avertissement si `is_ml_eligible == FALSE`. »

### Question 2 : *« Pourquoi avoir ajouté l'acteur "Développeur / Système Tiers" en plus de l'Analyste et du Décideur ? »*
> **Réponse conseillée** :
> « Parce que l'un des apports majeurs d'AgriPrix Observatory par rapport aux portails existants (identifié dans notre étude de l'existant) est d'exposer une **API REST publique documentée sous OpenAPI/Swagger** (`/api/v1/prices`, `/forecasts`, `/anomalies`, `/metadata`). Un data scientist d'une ONG ou un système d'alerte précoce tiers peut consommer directement nos prévisions JSON sans passer par le dashboard Streamlit. Modéliser cet acteur justifie nos exigences non fonctionnelles propres à l'API : pagination, validation `Pydantic`, limitation de débit (`60 req/min/IP`) et compte PostgreSQL en lecture seule. »
