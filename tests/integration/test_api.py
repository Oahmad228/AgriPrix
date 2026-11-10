"""Public API on the synthetic warehouse: routes, filters, security (US-11, US-12)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, text
from src.api.db import get_connection
from src.api.limits import limiter
from src.api.main import app
from src.config import get_settings
from src.etl.pipeline import run_etl
from src.ml.train import run_training


def _readonly_engine(schema: str) -> Engine:
    engine = create_engine(get_settings().readonly_database_url)

    @event.listens_for(engine, "connect")
    def _search_path(dbapi_connection, _record) -> None:
        with dbapi_connection.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}"')
        dbapi_connection.commit()

    return engine


def _spike(raw_dir: Path) -> None:
    """Triple the SEN retail millet price of 2025-06: a textbook upward anomaly."""
    path = raw_dir / "wfp_SEN.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("2025-06-15") and ",Millet,73,KG,actual,Retail," in line:
            fields = line.split(",")
            fields[14] = str(float(fields[14]) * 3)
            lines[i] = ",".join(fields)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _client(warehouse: Engine) -> Iterator[TestClient]:
    with warehouse.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
    readonly = _readonly_engine(schema)

    def override():
        with readonly.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            yield conn

    app.dependency_overrides[get_connection] = override
    limiter.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        readonly.dispose()


@pytest.fixture
def api(warehouse: Engine, raw_dir: Path) -> Iterator[TestClient]:
    _spike(raw_dir)
    run_etl(warehouse, raw_dir, offline=True)
    run_training(warehouse, use_mlflow=False)
    yield from _client(warehouse)


@pytest.fixture
def api_without_training(warehouse: Engine, raw_dir: Path) -> Iterator[TestClient]:
    run_etl(warehouse, raw_dir, offline=True)
    yield from _client(warehouse)


def test_reference_routes(api: TestClient) -> None:
    countries = api.get("/api/v1/countries").json()
    assert [c["country_iso3"] for c in countries] == ["BFA", "CIV", "MAR", "MLI", "NER", "SEN"]
    assert {c["country_iso3"]: c["ml_eligible_series"] for c in countries}["SEN"] == 1
    commodities = api.get("/api/v1/commodities", params={"country": "sen"}).json()
    assert {c["commodity_group"] for c in commodities} == {"Millet", "Rice"}  # tomatoes excluded
    markets = api.get("/api/v1/markets", params={"country": "MAR"}).json()
    assert markets[0]["granularity_level"] == "NATIONAL"


def test_series_are_retail_by_default_but_keep_national_series(api: TestClient) -> None:
    default = api.get("/api/v1/series").json()
    types = {(s["granularity_level"], s["price_type"]) for s in default["items"]}
    assert ("MARKET", "Wholesale") not in types
    assert ("NATIONAL", "CPI") in types  # Morocco kept
    everything = api.get("/api/v1/series", params={"price_type": "all"}).json()
    assert everything["total"] == default["total"] + 1  # + the wholesale millet series
    annual = api.get("/api/v1/series", params={"frequency": "ANNUAL"}).json()
    assert {s["unit_measure"] for s in annual["items"]} == {"TONNE"}
    page = api.get("/api/v1/series", params={"limit": 2, "offset": 2}).json()
    assert (page["limit"], page["offset"], len(page["items"])) == (2, 2, 2)


def test_history_flags_non_observed_values(api: TestClient) -> None:
    series = api.get("/api/v1/series", params={"country": "MAR", "value_type": "INFLATION_RATE"})
    sid = series.json()["items"][0]["series_id"]
    history = api.get(f"/api/v1/series/{sid}/history").json()
    assert history["observations"]
    assert all(
        o["source_flag"] == "fao_estimated" and not o["is_observed"]
        for o in history["observations"]
    )
    assert (
        api.get(f"/api/v1/series/{sid}/history", params={"observed_only": True}).json()[
            "observations"
        ]
        == []
    )
    assert api.get("/api/v1/series/999999/history").status_code == 404


def test_forecasts_with_intervals_and_test_coverage(api: TestClient) -> None:
    body = api.get("/api/v1/forecasts").json()
    assert body["training_run_id"] == 1
    assert len(body["items"]) == 6  # 2 eligible series x 3 horizons
    for item in body["items"]:
        assert item["lower_80"] <= item["upper_80"]
        assert item["target_period"] > item["origin_period"]
    six = api.get("/api/v1/forecasts", params={"horizon": 6, "country": "SEN"}).json()["items"]
    assert api.get("/api/v1/forecasts", params={"horizon": 2}).status_code == 422
    assert [(f["horizon_months"], f["unit_measure"], f["currency_code"]) for f in six] == [
        (6, "KG", "XOF")
    ]


def test_anomalies_explained_in_french(api: TestClient) -> None:
    body = api.get("/api/v1/anomalies", params={"country": "SEN", "direction": "UP"}).json()
    spike = [a for a in body["items"] if a["period"] == "2025-06-01"]
    assert spike, body
    alert = spike[0]
    assert alert["severity"] == "CRITICAL"
    assert alert["deviation_pct"] > 100
    assert "Alerte forte" in alert["explanation_fr"]
    assert "juin 2025" in alert["explanation_fr"]
    assert "au-dessus du niveau attendu" in alert["explanation_fr"]


def test_model_metrics_compare_against_persistence(api: TestClient) -> None:
    items = api.get("/api/v1/models/metrics").json()["items"]
    assert {(m["model_name"], m["horizon_months"]) for m in items} == {
        (m, h)
        for m in ("Naive", "SeasonalNaive", "Ridge_Seasonal", "LightGBM_Global")
        for h in (1, 3, 6)
    }
    naive = [m for m in items if m["model_name"] == "Naive"]
    assert all(m["gain_vs_naive_pct"] == pytest.approx(0.0) for m in naive)
    shares = {}
    for m in items:
        shares[m["horizon_months"]] = shares.get(m["horizon_months"], 0) + m["is_champion_share"]
    assert all(v == pytest.approx(1.0) for v in shares.values())
    run = api.get("/api/v1/runs/active").json()
    assert (run["training_run_id"], run["forecasts"]) == (1, 6)
    assert run["anomalies"] >= 1


def test_routes_needing_a_training_run_answer_503_before_the_first_one(
    api_without_training: TestClient,
) -> None:
    assert api_without_training.get("/api/v1/forecasts").status_code == 503
    assert api_without_training.get("/api/v1/countries").status_code == 200


def test_rate_limit_returns_429_but_health_is_exempt(api: TestClient) -> None:
    quota = int(get_settings().api_rate_limit.split("/")[0])
    codes = [api.get("/api/v1/countries").status_code for _ in range(quota + 1)]
    assert codes[:quota] == [200] * quota
    assert codes[-1] == 429
    assert api.get("/api/v1/health").status_code == 200


def test_cors_only_for_configured_origins(api: TestClient) -> None:
    allowed = get_settings().cors_origin_list[0]
    ok = api.get("/api/v1/countries", headers={"Origin": allowed})
    assert ok.headers.get("access-control-allow-origin") == allowed
    other = api.get("/api/v1/countries", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_api_is_read_only() -> None:
    methods = {m for route in app.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD"}
    paths = set(app.openapi()["paths"])
    assert {
        "/api/v1/countries", "/api/v1/commodities", "/api/v1/markets", "/api/v1/series",
        "/api/v1/series/{series_id}/history", "/api/v1/forecasts", "/api/v1/anomalies",
        "/api/v1/models/metrics", "/api/v1/runs/active", "/api/v1/health",
    } <= paths  # fmt: skip
