"""Validation of the detector on the a-priori shock catalog (KPI-M4, US-10).

python -m src.anomaly.validation    # writes docs/results/anomaly-validation.md
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta
from sqlalchemy import text

from src.anomaly.catalog import (
    CALM_PERIOD,
    CATALOG,
    MAX_CALM_ALERT_RATE,
    MIN_EPISODE_RECALL,
    MIN_SHARE_OF_MARKETS,
    WARNING_Z,
    Episode,
)
from src.eda.report import md_table

OUT = Path("docs/results/anomaly-validation.md")


def _idx(year_month: tuple[int, int]) -> int:
    return year_month[0] * 12 + year_month[1] - 1


def _label(month_idx: int) -> str:
    return f"{month_idx // 12}-{month_idx % 12 + 1:02d}"


@dataclass
class ValidationResult:
    couples: pd.DataFrame
    episodes: pd.DataFrame
    recall: float
    recall_ci: tuple[float, float]
    calm_rate: float
    calm_scored: int
    calm_by_country: pd.Series

    @property
    def kpi_recall_met(self) -> bool:
        return self.recall >= MIN_EPISODE_RECALL

    @property
    def kpi_calm_met(self) -> bool:
        return self.calm_rate <= MAX_CALM_ALERT_RATE


def clopper_pearson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Exact binomial confidence interval: honest uncertainty for a recall on few events."""
    alpha = 1 - level
    low = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    high = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return low, high


def evaluate_couple(z: pd.DataFrame, meta: pd.DataFrame, episode: Episode, couple) -> dict:
    country, group = couple
    ids = meta[(meta["country_iso3"] == country) & (meta["commodity_group"] == group)].index
    window = z.loc[_idx(episode.start) : _idx(episode.end), z.columns.intersection(ids)]
    scored = window.notna().sum(axis=1)
    alerted = (window >= WARNING_Z).sum(axis=1)
    share = (alerted / scored).where(scored > 0)
    best = share.idxmax() if share.notna().any() else None
    return {
        "episode": episode.code,
        "country": country,
        "group": group,
        "markets_scored": int(scored.max()) if len(scored) else 0,
        "max_share_alert": float(share.max()) if best is not None else np.nan,
        "best_month": _label(int(best)) if best is not None else None,
        "max_z": float(window.max().max()) if window.notna().any().any() else np.nan,
        "detected": bool(best is not None and share.max() >= MIN_SHARE_OF_MARKETS),
    }


def validate(z: pd.DataFrame, meta: pd.DataFrame) -> ValidationResult:
    couples = pd.DataFrame([evaluate_couple(z, meta, e, c) for e in CATALOG for c in e.couples])
    evaluable = couples[couples["markets_scored"] > 0]
    episodes = (
        evaluable.groupby("episode")
        .agg(
            couples_evaluated=("detected", "size"),
            couples_detected=("detected", "sum"),
            max_share_alert=("max_share_alert", "max"),
        )
        .reindex([e.code for e in CATALOG])
    )
    episodes["detected"] = episodes["couples_detected"].fillna(0) > 0
    episodes["title"] = [e.title_fr for e in CATALOG]
    k, n = int(episodes["detected"].sum()), len(episodes)

    calm = z.loc[_idx(CALM_PERIOD[0]) : _idx(CALM_PERIOD[1])]
    scored = calm.notna()
    alerts = calm.abs() >= WARNING_Z
    by_country = alerts.T.groupby(meta["country_iso3"]).sum().sum(axis=1) / scored.T.groupby(
        meta["country_iso3"]
    ).sum().sum(axis=1)
    return ValidationResult(
        couples,
        episodes,
        k / n,
        clopper_pearson(k, n),
        float(alerts.sum().sum() / scored.sum().sum()),
        int(scored.sum().sum()),
        by_country.dropna(),
    )


def render(result: ValidationResult, run_label: str) -> str:
    ep = result.episodes.reset_index()[
        ["episode", "title", "couples_evaluated", "couples_detected", "max_share_alert", "detected"]
    ].copy()
    ep["max_share_alert"] = (ep["max_share_alert"] * 100).round(0)
    ep["detected"] = ep["detected"].map({True: "OUI", False: "NON"})
    ep = ep.rename(columns={"max_share_alert": "part max. de marchés en alerte (%)"}).set_index(
        "episode"
    )
    couples = result.couples.copy()
    couples["max_share_alert"] = (couples["max_share_alert"] * 100).round(0)
    couples["max_z"] = couples["max_z"].round(2)
    couples["detected"] = couples["detected"].map({True: "oui", False: "non"})
    couples = couples.set_index("episode")
    low, high = result.recall_ci
    lines = [
        "# Validation du détecteur d'anomalies sur les crises historiques",
        "",
        f"> Rapport **généré** par `python -m src.anomaly.validation` ({run_label}). Catalogue, seuils et "
        "critère fixés *a priori* dans `src/anomaly/catalog.py` (commit `d7bfac9`, publié avant tout calcul "
        "sur données réelles). Un épisode manqué est un résultat, jamais un motif de retoucher les seuils.",
        "",
        f"Critère : un couple (pays, produit) est détecté si, pendant l'épisode, au moins "
        f"**{MIN_SHARE_OF_MARKETS:.0%} de ses marchés** ont un score robuste **z ≥ +{WARNING_Z}** le même mois. "
        "Un épisode est détecté si au moins un de ses couples l'est.",
        "",
        "## 1. Résultat par épisode",
        "",
        md_table(ep),
        "",
        f"**Rappel : {int(result.episodes['detected'].sum())} / {len(result.episodes)} épisodes = "
        f"{result.recall:.0%}** (intervalle de confiance exact à 95 % : {low:.0%} – {high:.0%}). "
        f"Objectif KPI-M4 ≥ {MIN_EPISODE_RECALL:.0%} : **{'atteint' if result.kpi_recall_met else 'NON atteint'}**.",
        "",
        "Avec seulement 5 épisodes, l'intervalle de confiance est très large : ce rappel ne permet pas "
        "d'affirmer une performance générale, seulement l'absence d'échec grossier.",
        "",
        "## 2. Taux d'alerte en période calme (2015–2018)",
        "",
        f"**{result.calm_rate:.2%}** des {result.calm_scored:_} mois-séries notés sont en alerte (|z| ≥ {WARNING_Z}), ".replace(
            "_", " "
        )
        + f"objectif ≤ {MAX_CALM_ALERT_RATE:.0%} : **{'atteint' if result.kpi_calm_met else 'NON atteint'}**. "
        "Sous une loi normale, |z| ≥ 2,5 arriverait 1,24 % du temps ; l'écart mesure les queues épaisses des prix.",
        "",
        md_table((result.calm_by_country * 100).round(2).rename("taux d'alerte (%)").to_frame()),
        "",
        "## 3. Détail par couple (pays, produit)",
        "",
        md_table(couples),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    from src.anomaly.detector import load_scope, robust_scores
    from src.etl.db import make_writer_engine

    engine = make_writer_engine()
    try:
        with engine.connect() as conn:
            meta, prices = load_scope(conn)
            etl_run = conn.execute(
                text("SELECT MAX(etl_run_id) FROM etl_run_audit WHERE status = 'SUCCESS'")
            ).scalar_one()
    finally:
        engine.dispose()
    result = validate(robust_scores(prices)["z"], meta)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(result, f"données ETL `etl_run_id = {etl_run}`"), encoding="utf-8")
    print(
        f"recall {result.recall:.0%} (CI {result.recall_ci[0]:.0%}-{result.recall_ci[1]:.0%}), "
        f"calm alert rate {result.calm_rate:.2%} -> {OUT}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
