"""Forecasting results report generated from the active training run (docs/results/).

python -m src.ml.report      # inside the job-runner container, after `make train`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import Connection, text

from src.eda.report import md_table
from src.ml.models import BASELINES
from src.ml.train import headline_report
from src.ml.windows import HORIZONS

OUT = Path("docs/results/forecast-report.md")


def load_run(conn: Connection) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    run = (
        conn.execute(
            text(
                "SELECT run_id, etl_run_id, git_sha, max_data_date, mlflow_parent_run_id,"
                " finished_at - run_timestamp AS duration FROM training_run WHERE is_production_active"
            )
        )
        .mappings()
        .one()
    )
    metrics = pd.read_sql(
        text(
            "SELECT m.*, s.country_iso3, c.commodity_group FROM fact_model_metrics_by_series m"
            " JOIN dim_series_catalog s USING (series_id) JOIN dim_commodity c USING (commodity_code)"
            " WHERE m.run_id = :run"
        ),
        conn,
        params={"run": run["run_id"]},
    )
    champions = pd.read_sql(
        text("SELECT * FROM fact_champion_model WHERE run_id = :run"),
        conn,
        params={"run": run["run_id"]},
    )
    for col in ("mae", "rmse", "mape", "mase", "rel_mae", "picp_80"):
        metrics[col] = metrics[col].astype(float)
    return dict(run), metrics, champions


def headline_table(report: dict[str, float], tag: str) -> pd.DataFrame:
    rows = {}
    for h in HORIZONS:
        key = f"{tag}_h{h}"
        if f"{key}_series" not in report:
            continue
        rows[f"{h} mois"] = {
            "séries": int(report[f"{key}_series"]),
            "MAPE (%)": round(report[f"{key}_mape"], 1),
            "MASE médian": round(report[f"{key}_median_mase"], 2),
            "RelMAE médian vs SeasonalNaive": round(report[f"{key}_median_rel_mae"], 2),
            **{
                f"gain vs {b} (%)": round(100 * report[f"{key}_skill_vs_{b}"], 1) for b in BASELINES
            },
            "PICP 80 % (%)": round(100 * report[f"{key}_picp_80"], 1)
            if f"{key}_picp_80" in report
            else None,
        }
    frame = pd.DataFrame.from_dict(rows, orient="index").astype(object)
    frame["séries"] = frame["séries"].astype(int)
    frame.index.name = "horizon"
    return frame


def model_comparison(metrics: pd.DataFrame, window: str) -> pd.DataFrame:
    """Gain of each model vs persistence (Naive), total absolute error, per horizon."""
    w = metrics[metrics["eval_window"] == window].assign(
        err=lambda d: d["mae"] * d["n_eval_points"]
    )
    total = w.groupby(["horizon_months", "model_name"])["err"].sum().unstack()
    gain = (1 - total.div(total["Naive"], axis=0)) * 100
    gain.index = [f"{h} mois" for h in gain.index]
    gain.index.name = "horizon"
    return gain.round(1)


def render(run: dict, metrics: pd.DataFrame, champions: pd.DataFrame) -> str:
    report = headline_report(metrics, champions)
    champ_counts = (
        champions.groupby(["horizon_months", "champion_model_name"]).size().unstack(fill_value=0)
    )
    champ_counts.index = [f"{h} mois" for h in champ_counts.index]
    champ_counts.index.name = "horizon"
    lines = [
        "# Résultats des prévisions (rapport généré)",
        "",
        f"> Généré par `python -m src.ml.report` depuis la campagne active `training_run.run_id = {run['run_id']}` "
        f"(données ETL `etl_run_id = {run['etl_run_id']}`, dernières données {run['max_data_date']}, "
        f"commit `{run['git_sha']}`, run MLflow parent `{run['mlflow_parent_run_id']}`). "
        "Aucun chiffre n'est saisi à la main.",
        "",
        "## 1. Test final hors échantillon — fenêtre W3 (cibles 2025-09 → 2026-08)",
        "",
        "Modèles champions choisis **uniquement** sur W1 + W2, puis évalués sur W3.",
        "",
        f"Règle de sélection : `{champions['selection_rule'].iloc[0]}`.",
        "",
        md_table(headline_table(report, "W3")),
        "",
        "## 2. Choc de 2022 — fenêtre W1 (cibles 2022-01 → 2022-12)",
        "",
        md_table(headline_table(report, "W1")),
        "",
        "## 3. Gain de chaque famille de modèles face à la persistance (Naive), en %",
        "",
        "Valeur positive = erreur absolue totale plus faible que « le prix restera le dernier prix connu ».",
        "",
        "**Fenêtre de sélection W1 (2022) :**",
        "",
        md_table(model_comparison(metrics, "VAL_W1_2022")),
        "",
        "**Fenêtre de sélection W2 (2024-07 → 2025-06) :**",
        "",
        md_table(model_comparison(metrics, "VAL_W2_24_25")),
        "",
        "**Fenêtre de test W3 :**",
        "",
        md_table(model_comparison(metrics, "TEST_W3_25_26")),
        "",
        "## 4. Modèles champions par horizon (19 groupes pays × produit)",
        "",
        md_table(champ_counts),
        "",
        "Définitions : MAPE = erreur absolue moyenne en % du prix réel ; MASE = erreur rapportée à la "
        "variation saisonnière moyenne de la série sur l'entraînement (< 1 = mieux que cette variation) ; "
        "RelMAE = erreur du modèle / erreur de SeasonalNaive ; PICP = part des prix réels tombés dans "
        "l'intervalle à 80 %.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    from src.etl.db import make_writer_engine

    engine = make_writer_engine()
    try:
        with engine.connect() as conn:
            run, metrics, champions = load_run(conn)
    finally:
        engine.dispose()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(run, metrics, champions), encoding="utf-8")
    print(f"Report written to {OUT}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
