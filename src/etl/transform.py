"""Unit normalization, series keys and duplicate/collision resolution (quality gate DQ-05)."""

from __future__ import annotations

import pandas as pd

from src.etl.parsers import REJECT_COLUMNS
from src.etl.reference import UNIT_BY_RAW

OBSERVED_FLAGS = {"actual", "fao_official", "fao_external", "fao_break"}


def series_natural_key(frame: pd.DataFrame) -> pd.Series:
    """Canonical 8-part series key (docs/02-sources-donnees.md section 5.1)."""
    parts = [
        "country_iso3",
        "market_code",
        "commodity_code",
        "price_type",
        "unit_measure",
        "currency_code",
        "frequency",
        "value_type",
    ]
    return frame[parts].astype(str).agg("|".join, axis=1)


def normalize(observations: pd.DataFrame) -> pd.DataFrame:
    """Add canonical unit/value, calendar id, observed flag and series key."""
    obs = observations.copy()
    obs["unit_measure"] = obs["raw_unit"].map(lambda u: UNIT_BY_RAW[u].canonical_unit)
    multiplier = obs["raw_unit"].map(lambda u: UNIT_BY_RAW[u].multiplier)
    obs["observed_value"] = (obs["raw_value"].astype(float) * multiplier).round(4)
    month = obs["reference_month"].fillna(0).astype(int)
    obs["calendar_id"] = obs["reference_year"].astype(int) * 100 + month
    obs["is_observed"] = obs["source_flag"].isin(OBSERVED_FLAGS)
    obs["series_natural_key"] = series_natural_key(obs)
    return obs


def resolve_duplicates(obs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep one row per (series, period, source_flag); quarantine the others.

    Deterministic priority: the row already expressed in the canonical unit
    (raw_unit == canonical unit) wins, then the earliest line in the file.
    Losers are tagged UNIT_NORMALIZATION_COLLISION when their raw unit differs from
    the kept row, DUPLICATE_OBSERVATION otherwise.
    """
    keys = ["series_natural_key", "calendar_id", "source_flag"]
    ranked = obs.assign(_native=(obs["raw_unit"] != obs["unit_measure"]).astype(int)).sort_values(
        keys + ["_native", "source_file", "line_number"], kind="mergesort"
    )
    dup_mask = ranked.duplicated(keys, keep="first")
    kept = ranked[~dup_mask].drop(columns="_native")
    losers = ranked[dup_mask]
    if losers.empty:
        return kept.reset_index(drop=True), pd.DataFrame(columns=REJECT_COLUMNS)

    winner_unit = kept.set_index(keys)["raw_unit"]
    loser_winner_unit = winner_unit.reindex(pd.MultiIndex.from_frame(losers[keys])).to_numpy()
    reasons = [
        "UNIT_NORMALIZATION_COLLISION" if lu != wu else "DUPLICATE_OBSERVATION"
        for lu, wu in zip(losers["raw_unit"], loser_winner_unit, strict=True)
    ]
    payload_cols = ["series_natural_key", "calendar_id", "source_flag", "raw_unit", "raw_value"]
    rejects = pd.DataFrame(
        {
            "source_file": losers["source_file"].to_numpy(),
            "line_number": losers["line_number"].astype(int).to_numpy(),
            "reason_code": reasons,
            "raw_payload_json": losers[payload_cols]
            .to_json(orient="records", lines=True)
            .strip()
            .split("\n"),
        },
        columns=REJECT_COLUMNS,
    )
    return kept.reset_index(drop=True), rejects
