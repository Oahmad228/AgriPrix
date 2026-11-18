"""Comparison of the two 80 % interval methods on the same backtest (ADR-004 section 3).

    python -m src.ml.intervals_report   # job-runner, writes docs/results/interval-methods-comparison.md

Both methods are calibrated on the same window and measured on the next one, never on the
window used for calibration:
- W1 (2022) calibrated on CAL_W0 (2021);
- W3 (2025-09 -> 2026-08) calibrated on W2 (2024-07 -> 2025-06).
Only champion models are evaluated (one per country x group x horizon), as on the site.
The published report of v1.0-baseline (forecast-report.md) is not modified.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.eda.report import md_table
from src.ml.evaluation import (
    apply_interval,
    apply_log_interval,
    conformal_quantiles,
    log_conformal_radius,
    log_errors,
    median_bias,
)
from src.ml.windows import HORIZONS, TEST_W3, VAL_W1

OUT = Path("docs/results/interval-methods-comparison.md")
KEYS = ["country_iso3", "commodity_group", "model_name", "horizon_months"]
WINDOWS = (VAL_W1, TEST_W3)


def compare(predictions: pd.DataFrame, champions: pd.DataFrame) -> pd.DataFrame:
    """One row per (window, horizon): coverage, width and forecasts outside their interval."""
    champ = champions.rename(columns={"champion_model_name": "model_name"})[
        ["country_iso3", "commodity_group", "horizon_months", "model_name"]
    ]
    rows = []
    for window in WINDOWS:
        calib = predictions[predictions["eval_window"] == window.calibrated_by]
        evald = predictions[predictions["eval_window"] == window.name].merge(
            champ, on=KEYS[:2] + ["horizon_months", "model_name"]
        )
        parts = []
        for key, block in evald.groupby(KEYS):
            cal = calib[(calib[KEYS] == pd.Series(key, index=KEYS)).all(axis=1)]
            if cal.empty:
                continue
            rel = ((cal["actual_value"] - cal["prediction"]) / cal["prediction"]).to_numpy()
            logs = log_errors(cal["actual_value"], cal["prediction"])
            logs = logs[~np.isnan(logs)]
            q_low, q_high = conformal_quantiles(rel)
            old_lo, old_hi = apply_interval(block["prediction"].to_numpy(), q_low, q_high)
            new_lo, new_hi = apply_log_interval(
                block["prediction"].to_numpy(), log_conformal_radius(logs)
            )
            parts.append(
                pd.DataFrame(
                    {
                        "horizon_months": key[3],
                        "actual": block["actual_value"].to_numpy(),
                        "pred": block["prediction"].to_numpy(),
                        "old_lo": old_lo, "old_hi": old_hi, "new_lo": new_lo, "new_hi": new_hi,
                        "bias": median_bias(logs),
                    }
                )
            )  # fmt: skip
        data = pd.concat(parts, ignore_index=True)
        for horizon in HORIZONS:
            d = data[data["horizon_months"] == horizon]
            rows.append(
                {
                    "fenêtre": window.name,
                    "calibrée sur": window.calibrated_by,
                    "horizon": f"{horizon} mois",
                    "prévisions": len(d),
                    "couverture v1 (%)": round(100 * ((d.actual >= d.old_lo) & (d.actual <= d.old_hi)).mean(), 1),
                    "couverture log-sym. (%)": round(100 * ((d.actual >= d.new_lo) & (d.actual <= d.new_hi)).mean(), 1),
                    "largeur médiane v1 (% de la prévision)": round(100 * ((d.old_hi - d.old_lo) / d.pred).median(), 1),
                    "largeur médiane log-sym. (%)": round(100 * ((d.new_hi - d.new_lo) / d.pred).median(), 1),
                    "prévisions hors de leur fourchette v1 (%)": round(100 * ((d.pred < d.old_lo) | (d.pred > d.old_hi)).mean(), 1),
                    "biais médian de calibration (%)": round(100 * np.expm1(d["bias"].median()), 1),
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def render(table: pd.DataFrame, run_note: str) -> str:
    return "\n".join(
        [
            "# Comparaison des deux méthodes d'intervalles à 80 % (rapport généré)",
            "",
            f"> Généré par `python -m src.ml.intervals_report` ({run_note}). Aucun chiffre n'est saisi à la main.",
            "> Les deux méthodes sont calibrées sur la même fenêtre et mesurées sur la fenêtre suivante,"
            " jamais sur celle qui a servi à les calibrer. Seuls les modèles champions sont évalués.",
            "",
            "- **v1 (`signed_relative`)** : quantiles 10 % et 90 % des erreurs relatives signées"
            " (ADR-004 §1-2, référence figée `v1.0-baseline`).",
            "- **log-symétrique (`log_symmetric`)** : rayon = 80ᵉ centile corrigé de |ln(réel / prévision)|,"
            " fourchette = prévision × exp(±rayon) (ADR-004 §3).",
            "",
            md_table(table),
            "",
            "Lecture : la couverture est la part des prix réels tombés dans la fourchette (objectif 80 %) ;"
            " « hors de leur fourchette » compte les prévisions que la méthode v1 plaçait en dehors de leur propre"
            " fourchette (impossible avec la méthode log-symétrique) ; un biais négatif signifie que le modèle"
            " surestimait le prix pendant la fenêtre de calibration.",
            "",
        ]
    )


def main() -> int:  # pragma: no cover - needs the warehouse; logic tested via compare()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    from src.etl.db import make_writer_engine
    from src.ml.data import calendar_id_of, load_panel
    from src.ml.train import (
        add_test_quality,
        backtest,
        calibrate,
        choose_champions,
        compute_metrics,
    )

    engine = make_writer_engine()
    with engine.connect() as conn:
        panel = load_panel(conn)
    raw, _cache = backtest(panel)
    calibrated, _quantiles = calibrate(raw)
    champions = add_test_quality(
        choose_champions(compute_metrics(panel, calibrated)), compute_metrics(panel, calibrated)
    )
    table = compare(raw, champions)
    cid = calendar_id_of(panel.last_month)
    note = f"entrepôt local, données jusqu’à {str(cid)[:4]}-{str(cid)[4:6]}"
    OUT.write_text(render(table, note), encoding="utf-8")
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
