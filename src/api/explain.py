"""Plain-French explanation of an alert, for NGO coordinators and cooperative managers."""

from __future__ import annotations

from datetime import date

MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip
UNITS_FR = {"KG": "kg", "L": "litre", "INDEX_2015_100": "point d'indice (base 2015 = 100)"}


def format_value(value: float, currency: str, unit: str) -> str:
    if currency == "NONE":
        return f"{value:,.1f}".replace(",", " ") + " points"
    return f"{value:,.0f}".replace(",", " ") + f" {currency}/{UNITS_FR.get(unit, unit)}"


def explain_anomaly(
    *,
    commodity: str,
    market: str,
    country: str,
    period: date,
    observed: float,
    expected: float,
    currency: str,
    unit: str,
    severity: str,
) -> str:
    deviation = (observed / expected - 1) * 100
    sense = "au-dessus" if deviation > 0 else "en dessous"
    level = "Alerte forte" if severity == "CRITICAL" else "Alerte modérée"
    return (
        f"{level} : en {MONTHS_FR[period.month - 1]} {period.year}, le prix de « {commodity} » "
        f"à {market} ({country}) était de {format_value(observed, currency, unit)}, soit "
        f"{abs(deviation):.0f} % {sense} du niveau attendu ({format_value(expected, currency, unit)}) "
        "compte tenu de la tendance de l'année écoulée et de la saison."
    )
