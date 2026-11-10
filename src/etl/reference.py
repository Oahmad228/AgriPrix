"""Static reference data: countries, unit conversions, commodity groups, calendar."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

FOOD_BASKET_GROUPS = ("Rice", "Millet", "Sorghum", "Maize", "Beans")
MOROCCO_FOOD_CPI_ITEM = 23013


@dataclass(frozen=True)
class Country:
    iso3: str
    name_fr: str
    currency: str
    primary_source: str
    lean_season_months: str | None


# Sahel lean season (soudure) June-September; not defined for the coastal/Maghreb countries.
COUNTRIES: tuple[Country, ...] = (
    Country("SEN", "Sénégal", "XOF", "WFP_HDX", "06,07,08,09"),
    Country("MLI", "Mali", "XOF", "WFP_HDX", "06,07,08,09"),
    Country("BFA", "Burkina Faso", "XOF", "WFP_HDX", "06,07,08,09"),
    Country("NER", "Niger", "XOF", "WFP_HDX", "06,07,08,09"),
    Country("CIV", "Côte d'Ivoire", "XOF", "WFP_HDX", None),
    Country("MAR", "Maroc", "MAD", "FAOSTAT", None),
)


@dataclass(frozen=True)
class UnitConversion:
    raw_unit: str
    canonical_unit: str
    multiplier: float
    is_metric_convertible: bool


# A price "per 100 KG" becomes a price per KG by multiplying by 0.01; a price per 500 G
# becomes per KG by multiplying by 2. Local units (Pile, Head...) are never converted:
# inventing a weight for "a pile of tomatoes" would fabricate data.
UNIT_CONVERSIONS: tuple[UnitConversion, ...] = (
    UnitConversion("KG", "KG", 1.0, True),
    UnitConversion("100 KG", "KG", 0.01, True),
    UnitConversion("500 G", "KG", 2.0, True),
    UnitConversion("70 G", "KG", round(1000 / 70, 6), True),
    UnitConversion("L", "L", 1.0, True),
    UnitConversion("TONNE", "TONNE", 1.0, True),
    UnitConversion("Pile", "Pile", 1.0, False),
    UnitConversion("Head", "Head", 1.0, False),
    UnitConversion("Day", "Day", 1.0, False),
    UnitConversion("Unit", "Unit", 1.0, False),
    UnitConversion("INDEX_2015_100", "INDEX_2015_100", 1.0, False),
    UnitConversion("INDEX_2014_2016_100", "INDEX_2014_2016_100", 1.0, False),
    UnitConversion("PCT", "PCT", 1.0, False),
)
UNIT_BY_RAW = {u.raw_unit: u for u in UNIT_CONVERSIONS}


def commodity_group(commodity_name: str) -> str:
    """Map a WFP commodity label to one of the food-basket groups (or 'Other').

    Processed products (flour) are excluded from the basket: their price dynamics
    follow milling costs, not the grain market.
    """
    name = commodity_name.lower()
    if "flour" in name:
        return "Other"
    for prefix, group in (
        ("rice", "Rice"),
        ("millet", "Millet"),
        ("sorghum", "Sorghum"),
        ("maize", "Maize"),
        ("beans", "Beans"),
        ("cowpea", "Beans"),
    ):
        if name.startswith(prefix):
            return group
    return "Other"


def month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    """Return (year, month) shifted by ``delta`` months."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_index(d: date) -> int:
    """Absolute month number, so that consecutive months differ by exactly 1."""
    return d.year * 12 + d.month - 1


def calendar_rows(first_year: int = 1990, last_year: int = 2035) -> list[tuple]:
    """Build dim_calendar rows: one ANNUAL row (YYYY00) and 12 MONTHLY rows per year."""
    rows: list[tuple] = []
    for year in range(first_year, last_year + 1):
        rows.append((year * 100, "ANNUAL", year, None, date(year, 1, 1), None, None))
        for month in range(1, 13):
            mid = min(15, calendar.monthrange(year, month)[1])
            rows.append(
                (
                    year * 100 + month,
                    "MONTHLY",
                    year,
                    month,
                    date(year, month, 1),
                    date(year, month, mid),
                    (month - 1) // 3 + 1,
                )
            )
    return rows
