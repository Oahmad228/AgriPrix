"""ML eligibility rules (docs/05-conception.md 2.2): no imputation, 60 months, gaps <= 3."""

import pandas as pd
import pytest
from src.etl.eligibility import build_series_catalog, recent_segment
from src.etl.reference import month_add


def idx(year: int, month: int) -> int:
    return year * 12 + month - 1


def test_recent_segment_empty() -> None:
    assert recent_segment([]) == (0, None)


def test_recent_segment_tolerates_gaps_up_to_three_months() -> None:
    months = [idx(2020, 1), idx(2020, 2), idx(2020, 6), idx(2020, 7)]  # gap of 3 (Mar-May)
    assert recent_segment(months) == (4, 3)


def test_recent_segment_stops_at_gap_of_four_months() -> None:
    months = [idx(2020, 1), idx(2020, 6), idx(2020, 7)]  # gap of 4 (Feb-May)
    assert recent_segment(months) == (2, 0)


def test_segment_counts_observed_months_not_calendar_span() -> None:
    # 60-month span with one gap of 2 months -> only 58 observed months: NOT enough.
    months = [idx(*month_add(2020, 1, k)) for k in range(60) if k not in (10, 11)]
    count, gap = recent_segment(months)
    assert (count, gap) == (58, 2)


def _series_obs(n_months: int, start=(2021, 1), **attrs) -> pd.DataFrame:
    base = {
        "series_natural_key": "SEN|SEN_1|WFP_73|Retail|KG|XOF|MONTHLY|PRICE",
        "market_code": "SEN_1",
        "country_iso3": "SEN",
        "commodity_code": "WFP_73",
        "price_type": "Retail",
        "unit_measure": "KG",
        "currency_code": "XOF",
        "frequency": "MONTHLY",
        "value_type": "PRICE",
        "granularity_level": "MARKET",
        "is_food_security_basket": True,
        "is_observed": True,
    } | attrs
    rows = []
    for k in range(n_months):
        year, month = month_add(start[0], start[1], k)
        rows.append(base | {"reference_year": year, "reference_month": month})
    frame = pd.DataFrame(rows)
    frame["reference_month"] = frame["reference_month"].astype("Int64")
    return frame


def _verdict(frame: pd.DataFrame) -> tuple[bool, str | None]:
    row = build_series_catalog(frame).iloc[0]
    return bool(row["is_ml_eligible"]), row["ineligibility_reason"]


def test_sixty_continuous_months_is_eligible() -> None:
    assert _verdict(_series_obs(60)) == (True, None)


def test_fifty_nine_months_is_not() -> None:
    assert _verdict(_series_obs(59)) == (False, "SHORT_CONTINUOUS_SEGMENT")


@pytest.mark.parametrize(
    ("attrs", "reason"),
    [
        ({"is_food_security_basket": False}, "NOT_IN_FOOD_BASKET"),
        ({"price_type": "Wholesale"}, "NOT_RETAIL_PRICE"),
        ({"is_observed": False}, "NO_OBSERVED_VALUE"),
    ],
)
def test_rule_failures(attrs: dict, reason: str) -> None:
    assert _verdict(_series_obs(80, **attrs)) == (False, reason)


def test_stale_series_relative_to_country_latest_month() -> None:
    eligible = _series_obs(80, start=(2015, 1))  # ends 2021-08
    other = _series_obs(
        5, start=(2026, 1), series_natural_key="SEN|SEN_2|WFP_73|Retail|KG|XOF|MONTHLY|PRICE"
    )  # pushes the country's latest month to 2026-05
    catalog = build_series_catalog(pd.concat([eligible, other], ignore_index=True))
    first = catalog.set_index("series_natural_key").iloc[0]
    assert first["ineligibility_reason"] == "STALE_LAST_OBSERVATION"


def test_aggregate_months_do_not_count_towards_continuity() -> None:
    observed = _series_obs(40)
    aggregate = _series_obs(30, start=(2024, 5), is_observed=False)  # continues as aggregate
    catalog = build_series_catalog(pd.concat([observed, aggregate], ignore_index=True))
    row = catalog.iloc[0]
    assert row["total_observed_count"] == 40
    assert not row["is_ml_eligible"]
