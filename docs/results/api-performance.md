# Performance de l'API (ENF-07)

> Généré le 2026-11-10 par `python -m src.api.perf` sur l'entrepôt réel. 100 requêtes par route après 5 requêtes de chauffe, pile FastAPI complète (validation, SQL avec le rôle lecture seule, sérialisation JSON) exécutée dans le conteneur `job-runner` ; le temps réseau client-serveur n'est pas inclus. Limites Docker : base 0,75 CPU, conteneur de mesure 1,5 CPU.

| route | requêtes | p50 (ms) | p95 (ms) | max (ms) | objectif p95 < 300 ms |
|---|---|---|---|---|---|
| GET /countries | 100 | 12.5 | 13.9 | 14.8 | oui |
| GET /series (filtres) | 100 | 13.0 | 14.5 | 15.1 | oui |
| GET /series/{id}/history | 100 | 15.3 | 22.2 | 100.7 | oui |
| GET /forecasts?series_id | 100 | 18.1 | 21.9 | 44.6 | oui |
| GET /forecasts?country | 100 | 26.5 | 31.2 | 40.0 | oui |
| GET /anomalies (pays, depuis 2023) | 100 | 37.4 | 44.0 | 93.9 | oui |
| GET /models/metrics | 100 | 81.2 | 108.1 | 194.6 | oui |
| GET /models/metrics (groupe) | 100 | 17.5 | 19.5 | 21.0 | oui |
| GET /runs/active | 100 | 15.3 | 18.3 | 19.5 | oui |

**Toutes les routes sous l'objectif : oui.**
