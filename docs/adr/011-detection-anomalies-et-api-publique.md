# ADR-011 : Détecteur d'anomalies validé a priori et API publique en lecture seule

- **Statut** : Accepté
- **Date** : 2026-11-10
- **Décideurs** : Ahmad (critère de détection, stratégie de validation) & assistant IA (Claude Code)
- **Exigences liées** : `EF-11`, `EF-12`, `ENF-04`, `ENF-05`, `ENF-06`, `ENF-07`, `KPI-M4`, `US-10`, `US-11`, `US-12`
- **Précise** : [`ADR-003`](./003-strategie-ml-globale-fenetre-historique-rolling-origin.md) §2.6

---

## 1. Détecteur d'anomalies

**Définition** : celle de [`05-conception.md`](../05-conception.md) §3.2, implémentée dans `src/anomaly/detector.py` :
- tendance = médiane glissante des 12 mois précédents ;
- saisonnalité = médiane par mois calendaire ;
- échelle = 1,4826 × MAD par mois, avec un plancher de 2 % ;
- alerte si |z| ≥ 2,5 (`WARNING`), alerte forte si |z| ≥ 3,5 (`CRITICAL`).

**Périmètre** : séries mensuelles observées du panier (prix de détail) et IPC alimentaire du Maroc, ayant au moins 60 mois observés. Contrairement à l'éligibilité ML, les séries arrêtées sont conservées : elles sont indispensables pour noter 2008 et 2012.

**Limite assumée** : la saisonnalité et l'échelle sont calculées sur tout l'historique de la série, y compris les années postérieures au mois noté. La tendance, elle, est strictement passée. Les médianes limitent l'influence d'un choc sur ces paramètres, mais la validation historique n'est donc pas parfaitement « temps réel ».

**Exécution** : le détecteur tourne dans chaque campagne `make train`. Les alertes sont versionnées dans `fact_anomaly` (migration `V003`), avec leur direction (hausse ou baisse) et leur gravité. Des contraintes `CHECK` garantissent la cohérence entre z, direction et gravité.

## 2. Validation sur des crises documentées (KPI-M4)

**Fixé a priori par Ahmad** (commit `d7bfac9`, publié sur GitHub avant tout calcul sur données réelles) :
- 5 épisodes déclinés en 41 couples (pays, produit), avec des liens vérifiables ;
- un couple est détecté si **≥ 25 % de ses marchés** ont z ≥ +2,5 le même mois pendant l'épisode ;
- un épisode est détecté si au moins un de ses couples l'est.

**Résultats** (données `etl_run_id = 5`, rapport [`anomaly-validation.md`](../results/anomaly-validation.md)) :

| Épisode | Couples détectés | Part max. de marchés en alerte |
| :--- | ---: | ---: |
| SHOCK-01 Crise 2007–2008 | 2 / 3 | 95 % |
| SHOCK-02 Sahel 2012 | 6 / 6 | 100 % |
| SHOCK-03 COVID-19 2020 | **1 / 16** | **25 %** (limite) |
| SHOCK-04 Ukraine 2022 | 13 / 13 | 100 % |
| SHOCK-05 Niger 2023–24 | 2 / 3 | 91 % |

- **Rappel : 5/5.** Avec 5 épisodes, l'intervalle de confiance exact de Clopper-Pearson à 95 % va de 48 % à 100 % : c'est l'absence d'échec grossier, pas une preuve de performance générale.
- **Le choc COVID est détecté de justesse**, par un seul couple (mil au Sénégal, exactement 25 % des marchés). Les hausses de 2020 ont été modérées et étalées dans le temps.
- **Alertes en période calme (2015–2018) : 4,56 %** pour un objectif ≤ 5 %, atteint de peu. Par pays : la Côte d'Ivoire est à 12,1 %, le Sénégal à 6,8 %, le Niger à 5,1 %.
- **Stratégie de test (choix d'Ahmad)** :
  - la CI GitHub teste l'algorithme sur des données synthétiques (choc injecté, taux de fausses alertes sur un bruit saisonnier, règle des 25 %) ;
  - le test sur données réelles (`tests/integration/test_anomaly_real_data.py`) s'exécute en local et est signalé « SKIPPED » quand l'entrepôt est vide.

## 3. API publique

- **Rôle PostgreSQL en lecture seule** et transactions `READ ONLY`. Les routes sont uniquement en `GET` ; un test vérifie qu'aucune autre méthode n'existe.
- **9 routes métier documentées dans OpenAPI** (`/docs`) : référentiels, séries, historique, prévisions, alertes, métriques, run actif. Par défaut, les séries de marché sont filtrées sur le prix de détail (`Retail`) ; les séries nationales du Maroc restent toujours visibles.
- **Alertes expliquées en français simple**, phrase générée à la volée à partir des chiffres. Exemple réel renvoyé par `GET /api/v1/anomalies?country=BFA&commodity_group=Millet&since=2022-01-01&until=2022-12-31&severity=CRITICAL&limit=1` : « Alerte forte : en décembre 2022, le prix de « Millet » à Djibo (BFA) était de 1 464 XOF/kg, soit 214 % au-dessus du niveau attendu (466 XOF/kg) compte tenu de la tendance de l'année écoulée et de la saison. »
- **Limitation de débit** (60 requêtes par minute et par client, valeur configurable) :
  - la route `/health` n'est pas limitée ;
  - **bug découvert par les tests** : avec les versions de FastAPI et Starlette verrouillées, le *middleware* de SlowAPI ne retrouve plus la route d'une requête et **laisse tout passer sans prévenir** ;
  - solution : un décorateur `@limited` sur chaque route. Le test qui vérifie le code `429` à la 61e requête protège contre une régression.
- **CORS** limité aux origines configurées (test : une origine inconnue ne reçoit pas l'en-tête). En cas d'erreur inattendue, l'API renvoie un message générique et le détail ne va que dans les logs.

## 4. Performance (ENF-07)

Mesure de 100 requêtes par route sur l'entrepôt réel (rapport [`api-performance.md`](../results/api-performance.md)) : **p95 entre 14 et 108 ms**, pour un objectif < 300 ms.

Une optimisation a été faite en cours de sprint. La couverture des intervalles sur le test était recalculée à chaque appel de `/forecasts` (p95 = 279 ms, trop proche de la limite) ; elle est désormais pré-calculée pendant l'entraînement (migration `V004`), et la p95 descend à 31 ms.

Une mesure à 193 ms sur `/anomalies` a été diagnostiquée comme du bruit : la requête prend 9 ms d'après `EXPLAIN ANALYZE` et la p95 retombe à 44 ms quand la base n'est pas occupée.

## 5. Points reportés au Sprint 4

- Derrière le reverse proxy HTTPS, l'adresse du client doit être lue dans `X-Forwarded-For`, sinon tous les visiteurs partageraient le même quota.
- Politique de rétention des anciens runs (≈ 23 000 alertes et ≈ 37 000 métriques par campagne).
- Les mots de passe des rôles sont en dur dans `01-init.sql` ; ils devront venir de `.env` avant la mise en ligne.
