"""Unit conversion, commodity groups, calendar and duplicate resolution (DQ-05)."""

import pandas as pd
import pytest
from src.etl.reference import calendar_rows, commodity_group, month_add
from src.etl.transform import normalize, resolve_duplicates


@pytest.mark.parametrize(
    ("label", "group"),
    [
        ("Rice (imported)", "Rice"),
        ("Millet", "Millet"),
        ("Sorghum (white)", "Sorghum"),
        ("Maize (local)", "Maize"),
        ("Beans (niebe)", "Beans"),
        ("Maize flour", "Other"),
        ("Tomatoes", "Other"),
    ],
)
def test_commodity_group(label: str, group: str) -> None:
    assert commodity_group(label) == group


def test_month_add_crosses_years() -> None:
    assert month_add(2019, 12, 1) == (2020, 1)
    assert month_add(2020, 1, -1) == (2019, 12)
    assert month_add(2019, 1, 92) == (2026, 9)


def test_calendar_never_invents_month_for_annual_rows() -> None:
    rows = calendar_rows(2024, 2024)
    annual = [r for r in rows if r[1] == "ANNUAL"]
    monthly = [r for r in rows if r[1] == "MONTHLY"]
    assert annual == [(202400, "ANNUAL", 2024, None, annual[0][4], None, None)]
    assert len(monthly) == 12
    assert monthly[1][5].day == 15  # WFP reference day


def _obs(**overrides) -> dict:
    base = {
        "source_file": "wfp_SEN",
        "line_number": 2,
        "country_iso3": "SEN",
        "market_code": "SEN_447",
        "commodity_code": "WFP_73",
        "price_type": "Retail",
        "raw_unit": "KG",
        "currency_code": "XOF",
        "frequency": "MONTHLY",
        "value_type": "PRICE",
        "reference_year": 2024,
        "reference_month": 3,
        "raw_value": 200.0,
        "source_flag": "actual",
    }
    return base | overrides


def test_normalize_converts_metric_units_only() -> None:
    frame = pd.DataFrame(
        [
            _obs(raw_unit="100 KG", raw_value=25000.0),
            _obs(raw_unit="500 G", raw_value=150.0),
            _obs(raw_unit="Pile", raw_value=300.0),
        ]
    )
    out = normalize(frame)
    assert list(out["unit_measure"]) == ["KG", "KG", "Pile"]
    assert list(out["observed_value"]) == [250.0, 300.0, 300.0]
    assert list(out["calendar_id"]) == [202403] * 3
    assert out["is_observed"].all()


def test_normalize_flags_and_annual_calendar() -> None:
    frame = pd.DataFrame(
        [
            _obs(source_flag="aggregate"),
            _obs(source_flag="fao_imputed", frequency="ANNUAL", reference_month=None),
            _obs(source_flag="fao_external"),
        ]
    )
    out = normalize(frame)
    assert list(out["is_observed"]) == [False, False, True]
    assert out["calendar_id"].iloc[1] == 202400


def test_collision_keeps_native_unit_and_quarantines_the_other() -> None:
    frame = pd.DataFrame(
        [
            _obs(raw_unit="100 KG", raw_value=20000.0, line_number=2),
            _obs(raw_unit="KG", raw_value=201.0, line_number=3),
            _obs(raw_unit="KG", raw_value=999.0, line_number=4, reference_month=4),
            _obs(raw_unit="KG", raw_value=998.0, line_number=5, reference_month=4),
        ]
    )
    kept, rejects = resolve_duplicates(normalize(frame))
    assert sorted(kept["line_number"]) == [3, 4]
    reasons = dict(zip(rejects["line_number"], rejects["reason_code"], strict=True))
    assert reasons == {2: "UNIT_NORMALIZATION_COLLISION", 5: "DUPLICATE_OBSERVATION"}


def test_no_duplicates_means_no_rejects() -> None:
    kept, rejects = resolve_duplicates(normalize(pd.DataFrame([_obs()])))
    assert len(kept) == 1
    assert rejects.empty
