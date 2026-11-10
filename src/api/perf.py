"""API latency benchmark on the real warehouse (ENF-07: p95 < 300 ms on read routes).

    python -m src.api.perf      # inside the job-runner, writes docs/results/api-performance.md

Requests go through the full FastAPI stack (validation, SQL with the read-only role, JSON
serialization) in-process: network time between client and server is not included. The
rate limiter is disabled for the benchmark only.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.api.db import get_engine
from src.api.limits import limiter
from src.api.main import app
from src.eda.report import md_table

OUT = Path("docs/results/api-performance.md")
REQUESTS_PER_ROUTE = 100
TARGET_P95_MS = 300.0


def _scenarios(series_ids: list[int]) -> dict[str, callable]:
    pick = random.Random(42).choice
    return {
        "GET /countries": lambda: "/api/v1/countries",
        "GET /series (filtres)": lambda: "/api/v1/series?country=MLI&commodity_group=Rice",
        "GET /series/{id}/history": lambda: f"/api/v1/series/{pick(series_ids)}/history",
        "GET /forecasts?series_id": lambda: f"/api/v1/forecasts?series_id={pick(series_ids)}",
        "GET /forecasts?country": lambda: "/api/v1/forecasts?country=BFA&horizon=3",
        "GET /anomalies (pays, depuis 2023)": lambda: (
            "/api/v1/anomalies?country=NER&since=2023-01-01"
        ),
        "GET /models/metrics": lambda: "/api/v1/models/metrics",
        "GET /models/metrics (groupe)": lambda: (
            "/api/v1/models/metrics?country=SEN&commodity_group=Rice"
        ),
        "GET /runs/active": lambda: "/api/v1/runs/active",
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))
    return ordered[rank]


def benchmark() -> list[dict]:
    with get_engine().connect() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                text("SELECT series_id FROM dim_series_catalog WHERE is_ml_eligible")
            )
        ]
    client = TestClient(app)
    limiter.enabled = False
    rows = []
    try:
        for name, make_url in _scenarios(ids).items():
            for _ in range(5):  # warm-up: connection pool, query plans
                client.get(make_url())
            timings = []
            for _ in range(REQUESTS_PER_ROUTE):
                url = make_url()
                start = time.perf_counter()
                response = client.get(url)
                timings.append((time.perf_counter() - start) * 1000)
                if response.status_code != 200:
                    raise RuntimeError(f"{url} -> HTTP {response.status_code}")
            rows.append(
                {
                    "route": name,
                    "requêtes": REQUESTS_PER_ROUTE,
                    "p50 (ms)": round(statistics.median(timings), 1),
                    "p95 (ms)": round(percentile(timings, 0.95), 1),
                    "max (ms)": round(max(timings), 1),
                    "objectif p95 < 300 ms": "oui"
                    if percentile(timings, 0.95) < TARGET_P95_MS
                    else "NON",
                }
            )
    finally:
        limiter.enabled = True
    return rows


def main() -> int:
    import pandas as pd

    rows = benchmark()
    table = pd.DataFrame(rows).set_index("route")
    lines = [
        "# Performance de l'API (ENF-07)",
        "",
        f"> Généré le {date.today():%Y-%m-%d} par `python -m src.api.perf` sur l'entrepôt réel. "
        f"{REQUESTS_PER_ROUTE} requêtes par route après 5 requêtes de chauffe, pile FastAPI complète "
        "(validation, SQL avec le rôle lecture seule, sérialisation JSON) exécutée dans le conteneur "
        "`job-runner` ; le temps réseau client-serveur n'est pas inclus. Limites Docker : base 0,75 CPU, "
        "conteneur de mesure 1,5 CPU.",
        "",
        md_table(table),
        "",
        f"**Toutes les routes sous l'objectif : {'oui' if (table['objectif p95 < 300 ms'] == 'oui').all() else 'NON'}.**",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(table.to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
