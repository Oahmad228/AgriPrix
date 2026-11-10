"""Reproducible exploratory data analysis (US-07): writes docs/eda/EDA.md + PNG figures.

Every number in the report is computed from the warehouse at generation time, and the
written analysis is derived from those numbers, so the report never drifts from the data.

    python -m src.eda.report            # inside the job-runner container
"""

from __future__ import annotations

import sys
import warnings
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import Connection, text  # noqa: E402
from statsmodels.tsa.stattools import adfuller  # noqa: E402

OUT_DIR = Path("docs/eda")
MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]  # fmt: skip
COLORS = {"SEN": "#2a6f97", "MLI": "#c9184a", "BFA": "#e09f3e", "NER": "#335c67", "MAR": "#6a4c93"}

ELIGIBLE_SQL = """
SELECT s.series_id, s.country_iso3, c.commodity_group, s.commodity_code, s.max_consecutive_missing,
       s.recent_continuous_months, cal.reference_year AS y, cal.reference_month AS m,
       f.observed_value AS v
FROM dim_series_catalog s
JOIN dim_commodity c USING (commodity_code)
JOIN fact_price_observation f ON f.series_id = s.series_id AND f.is_observed
JOIN dim_calendar cal ON cal.calendar_id = f.calendar_id
WHERE s.is_ml_eligible
"""


def load(conn: Connection) -> tuple[pd.DataFrame, dict]:
    obs = pd.read_sql(text(ELIGIBLE_SQL), conn)
    obs["date"] = pd.to_datetime({"year": obs["y"], "month": obs["m"], "day": 1})
    meta = {
        "etl_run_id": conn.execute(
            text("SELECT MAX(etl_run_id) FROM etl_run_audit WHERE status = 'SUCCESS'")
        ).scalar_one(),
        "catalog": pd.read_sql(
            text(
                "SELECT s.country_iso3, c.commodity_group, COUNT(*) AS series"
                " FROM dim_series_catalog s JOIN dim_commodity c USING (commodity_code)"
                " WHERE s.is_ml_eligible GROUP BY 1, 2 ORDER BY 1, 2"
            ),
            conn,
        ),
    }
    return obs, meta


def md_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table (no extra dependency such as tabulate)."""
    header = [str(frame.index.name or "")] + [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for index, row in frame.iterrows():
        cells = ["" if pd.isna(v) else str(v) for v in row]
        lines.append("| " + " | ".join([str(index), *cells]) + " |")
    return "\n".join(lines)


def wide_log(obs: pd.DataFrame) -> pd.DataFrame:
    return np.log(obs.pivot_table(index="date", columns="series_id", values="v")).asfreq("MS")


def seasonal_profile(obs: pd.DataFrame) -> pd.DataFrame:
    """Median deviation (%) of each calendar month from the centred 12-month mean, per country.

    Only cereals (millet, sorghum, maize) of the Sahel are used: their lean-season pattern
    is the agronomic hypothesis we want to check.
    """
    cereals = obs[obs["commodity_group"].isin(["Millet", "Sorghum", "Maize"])]
    logp = wide_log(cereals)
    trend = logp.rolling(13, center=True, min_periods=9).mean()
    deviation = (logp - trend).stack().rename("dev").reset_index()
    country = cereals.drop_duplicates("series_id").set_index("series_id")["country_iso3"]
    deviation["country"] = deviation["series_id"].map(country)
    deviation["month"] = deviation["date"].dt.month
    profile = deviation.groupby(["country", "month"])["dev"].median().unstack(0)
    return (np.exp(profile) - 1) * 100


def yoy_by_country(obs: pd.DataFrame) -> pd.DataFrame:
    logp = wide_log(obs)
    yoy = (np.exp(logp - logp.shift(12)) - 1) * 100
    country = obs.drop_duplicates("series_id").set_index("series_id")["country_iso3"]
    return yoy.T.groupby(country).median().T.dropna(how="all")


def adf_shares(obs: pd.DataFrame, max_series: int = 200) -> tuple[float, float, int]:
    """Share of series where ADF rejects a unit root (5 %), on log levels vs log returns."""
    logp = wide_log(obs)
    sample = logp.columns[:: max(1, len(logp.columns) // max_series)]
    levels, returns, n = 0, 0, 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for sid in sample:
            series = logp[sid].dropna()
            if len(series) < 60:
                continue
            n += 1
            levels += adfuller(series, autolag="AIC")[1] < 0.05
            returns += adfuller(series.diff().dropna(), autolag="AIC")[1] < 0.05
    return levels / n, returns / n, n


def volatility(obs: pd.DataFrame) -> pd.DataFrame:
    logp = wide_log(obs)
    vol = logp.diff().std() * 100
    meta = obs.drop_duplicates("series_id").set_index("series_id")[
        ["country_iso3", "commodity_group"]
    ]
    frame = meta.join(vol.rename("vol"))
    return frame.groupby(["country_iso3", "commodity_group"])["vol"].median().unstack(1).round(1)


def _save(fig, name: str) -> str:
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=110)
    plt.close(fig)
    return name


def figures(obs: pd.DataFrame, profile: pd.DataFrame, yoy: pd.DataFrame) -> dict[str, str]:
    out = {}
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(obs.drop_duplicates("series_id")["recent_continuous_months"], bins=30, color="#2a6f97")
    ax.axvline(60, color="#c9184a", linestyle="--", label="seuil 60 mois")
    ax.set_xlabel("Mois observés dans le segment continu récent")
    ax.set_ylabel("Séries éligibles")
    ax.legend()
    out["segments"] = _save(fig, "01-segments-continus.png")

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.axvspan(5.5, 9.5, color="#e09f3e", alpha=0.15, label="soudure (juin-sept.)")
    for country in profile.columns:
        ax.plot(
            range(1, 13), profile[country], marker="o", label=country, color=COLORS.get(country)
        )
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_xticks(range(1, 13), MONTHS_FR)
    ax.set_ylabel("Écart au niveau annuel (%)")
    ax.legend(ncol=5, fontsize=8)
    out["seasonality"] = _save(fig, "02-saisonnalite-cereales.png")

    fig, ax = plt.subplots(figsize=(9, 3.8))
    recent = yoy[yoy.index >= "2006-01-01"]
    for country in recent.columns:
        ax.plot(
            recent.index, recent[country], label=country, color=COLORS.get(country), linewidth=1.2
        )
    ax.axhline(0, color="grey", linewidth=0.8)
    for start, end, label in (("2022-01-01", "2022-12-31", "W1"), ("2024-07-01", "2025-06-30", "W2"), ("2025-09-01", "2026-08-31", "W3")):  # fmt: skip
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color="grey", alpha=0.12)
        ax.text(pd.Timestamp(start), ax.get_ylim()[1] * 0.9, label, fontsize=8)
    ax.set_ylabel("Variation sur 1 an, médiane (%)")
    ax.legend(ncol=5, fontsize=8)
    out["yoy"] = _save(fig, "03-variation-annuelle.png")
    return out


def render(obs: pd.DataFrame, meta: dict) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = seasonal_profile(obs)
    yoy = yoy_by_country(obs)
    vol = volatility(obs)
    adf_level, adf_return, adf_n = adf_shares(obs)
    figs = figures(obs, profile, yoy)
    series = obs.drop_duplicates("series_id")

    lean = profile.loc[6:9].mean()
    harvest = profile.loc[[10, 11, 12]].mean()
    peak_month = profile.idxmax()
    w2 = yoy.loc["2024-07-01":"2025-06-01"].median()
    w3 = yoy.loc["2025-09-01":"2026-08-01"].median()
    y2022 = yoy.loc["2022-01-01":"2022-12-01"].median()
    gaps = series["max_consecutive_missing"].value_counts().sort_index()

    lines = [
        "# Analyse exploratoire des séries éligibles (EDA)",
        "",
        f"> Rapport **généré automatiquement** le {date.today():%Y-%m-%d} par `python -m src.eda.report`, "
        f"à partir de l'entrepôt (exécution ETL `etl_run_id = {meta['etl_run_id']}`). "
        "Tous les chiffres viennent de cette exécution ; les commentaires sont déduits de ces chiffres.",
        "",
        "## 1. Périmètre",
        "",
        f"**{series['series_id'].nunique()} séries éligibles**, "
        f"{len(obs):_} observations mensuelles réellement observées (aucune valeur interpolée).".replace(
            "_", " "
        ),
        "",
        md_table(
            meta["catalog"]
            .pivot(index="commodity_group", columns="country_iso3", values="series")
            .fillna(0)
            .astype(int)
        ),
        "",
        "## 2. Continuité des séries et seuil de 60 mois",
        "",
        f"![Segments continus]({figs['segments']})",
        "",
        f"- Segment continu récent : médiane **{series['recent_continuous_months'].median():.0f} mois**, "
        f"minimum {series['recent_continuous_months'].min()} (le seuil de 60 est respecté par construction).",
        "- Plus long trou toléré dans le segment : "
        + ", ".join(f"{int(k)} mois → {v} séries" for k, v in gaps.items())
        + ". Ces mois manquants restent vides : les modèles reçoivent des `NaN`, jamais une valeur inventée.",
        "- Pourquoi 60 mois : 12 mois de retards saisonniers (`lag_12`) + au moins 24 mois d'entraînement "
        "+ 12 mois de validation + 12 mois de test (voir `docs/02-sources-donnees.md` §5.2).",
        "",
        "## 3. Saisonnalité agricole (céréales sèches)",
        "",
        f"![Saisonnalité]({figs['seasonality']})",
        "",
        "Écart médian de chaque mois au niveau moyen centré sur 12 mois (mil, sorgho, maïs) :",
        "",
        md_table(profile.round(1).rename(index=dict(enumerate(MONTHS_FR, start=1)))),
        "",
    ]
    for country in profile.columns:
        lines.append(
            f"- **{country}** : pic en **{MONTHS_FR[peak_month[country] - 1]}** ; "
            f"juin–sept. en moyenne {lean[country]:+.1f} % contre {harvest[country]:+.1f} % en oct.–déc."
            + (
                " → la hausse pendant la soudure est visible."
                if lean[country] > harvest[country]
                else " → pas de hausse nette pendant la soudure."
            )
        )
    lines += [
        "",
        "**Conséquence pour la modélisation** : le mois cible, l'indicateur de soudure et le prix du même "
        "mois l'an passé (`seasonal_level`, `seasonal_change`) font partie des variables explicatives.",
        "",
        "## 4. Stationnarité",
        "",
        f"Test de Dickey-Fuller augmenté (ADF : il teste si une série « dérive » sans revenir vers une moyenne) "
        f"sur {adf_n} séries échantillonnées : l'hypothèse de racine unitaire est rejetée à 5 % pour "
        f"**{adf_level:.0%}** des séries en log-niveau, contre **{adf_return:.0%}** en variations mensuelles.",
        "",
        "**Conséquence** : les modèles prédisent la **variation logarithmique** entre le dernier prix connu "
        "et le prix à l'horizon h, et non le niveau. Cela rend aussi comparables des marchés aux niveaux de "
        "prix très différents, condition pour entraîner un modèle global par (pays, produit).",
        "",
        "## 5. Dynamique des prix et régimes des fenêtres d'évaluation",
        "",
        f"![Variation annuelle]({figs['yoy']})",
        "",
        "Médiane des variations sur 1 an (%) par pays et par fenêtre :",
        "",
        md_table(
            pd.DataFrame(
                {"2022 (W1)": y2022, "2024-07→2025-06 (W2)": w2, "2025-09→2026-08 (W3)": w3}
            ).round(1)
        ),
        "",
    ]
    # A "reversal" needs a clear move on both sides (>= 5 points), not noise around zero.
    reversed_countries = [c for c in w3.index if pd.notna(w2.get(c)) and w2[c] >= 5 and w3[c] <= -5]
    falling = [c for c in w3.index if w3[c] <= -10 and c not in reversed_countries]
    if reversed_countries:
        lines.append(
            f"- **Retournement de marché** pour {', '.join(reversed_countries)} : les prix montaient pendant "
            "la fenêtre de calibration W2 et baissent nettement pendant la fenêtre de test W3."
        )
    if falling:
        lines.append(
            f"- **Forte baisse en W3** pour {', '.join(falling)} après une période stable en W2."
        )
    if reversed_countries or falling:
        lines.append(
            "- Les intervalles conformes supposent que les erreurs futures ressemblent aux erreurs passées "
            "(échangeabilité) : ces changements de régime l'enfreignent, comme le choc de 2022."
        )
    lines += [
        "",
        "## 6. Volatilité mensuelle",
        "",
        "Écart-type médian des variations mensuelles du log-prix (%), par pays et produit :",
        "",
        md_table(vol),
        "",
        "Les groupes les plus volatils sont ceux où un intervalle de 80 % sera le plus large.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    from src.etl.db import make_writer_engine

    engine = make_writer_engine()
    try:
        with engine.connect() as conn:
            obs, meta = load(conn)
        (OUT_DIR / "EDA.md").parent.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "EDA.md").write_text(render(obs, meta), encoding="utf-8")
    finally:
        engine.dispose()
    print(f"EDA written to {OUT_DIR / 'EDA.md'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
