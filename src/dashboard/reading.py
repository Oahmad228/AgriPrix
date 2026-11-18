"""Plain-French readings computed from the API numbers (PRODUCT.md: a sentence before a number).

Pure functions, tested in tests/unit/test_dashboard_reading.py. Nothing here invents a
value: every sentence is built from fields the API returned.
"""

from __future__ import annotations

from dataclasses import dataclass

# Reliability of the 80 % interval, from its coverage measured out of sample (ADR-004 §3.3).
# Target 80 %: "correcte" from 70 %, "moyenne" from 50 %, "faible" below (validated values
# in DESIGN.md). Word + symbol: never colour alone.
RELIABILITY_LEVELS = ((0.70, "correcte", "●"), (0.50, "moyenne", "◐"), (0.0, "faible", "○"))
BIAS_THRESHOLD_PCT = 10.0  # decided by Ahmad on 2026-11-18


@dataclass(frozen=True)
class Reliability:
    word: str
    symbol: str
    times_in_100: int

    @property
    def label(self) -> str:
        return f"{self.symbol} Fiabilité {self.word}"

    @property
    def detail(self) -> str:
        return f"la fourchette a été juste {self.times_in_100} fois sur 100 en test"


def reliability(coverage: float | None) -> Reliability | None:
    if coverage is None:
        return None
    for threshold, word, symbol in RELIABILITY_LEVELS:
        if coverage >= threshold:
            return Reliability(word, symbol, round(100 * coverage))
    return None  # pragma: no cover - the last threshold is 0


def bias_sentence(bias_pct: float | None, horizon: int) -> str | None:
    """Shown under a forecast when the model's recent median error is >= 10 % either way."""
    if bias_pct is None or abs(bias_pct) < BIAS_THRESHOLD_PCT:
        return None
    verb = "surestimé" if bias_pct < 0 else "sous-estimé"
    return (
        f"Ces derniers mois, ce modèle a {verb} le prix de {abs(bias_pct):.0f} % "
        f"(erreur médiane) à {horizon} mois. La prévision affichée n'est pas corrigée."
    )


def fr_number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return text.replace("-", "−")


def situation_sentence(last_value: float | None, unit: str, month: str, alert: dict | None) -> str:
    """First sentence of a market sheet: where the price stands against its usual level."""
    if last_value is None:
        return "Aucun relevé de terrain récent pour ce marché."
    price = f"{fr_number(last_value)} {unit} en {month}"
    if alert is None:
        return (
            f"Le dernier prix relevé ({price}) est dans sa plage habituelle pour la saison : "
            "aucune alerte ces trois derniers mois."
        )
    deviation = alert["deviation_pct"]
    side = "au-dessus de" if deviation > 0 else "sous"
    if alert["month_label"] == month:
        return f"Le prix est {abs(deviation):.0f} % {side} son niveau habituel pour la saison ({price})."
    # The alert is older than the last price: date each figure, never mix two months.
    return (
        f"Dernier prix relevé : {price}. En {alert['month_label']}, il était "
        f"{abs(deviation):.0f} % {side} son niveau habituel pour la saison "
        f"({fr_number(alert['observed_value'])} {unit})."
    )


def forecast_sentence(forecast: dict, unit: str, target_month: str) -> str:
    return (
        f"Dans {forecast['horizon_months']} mois ({target_month}), il devrait se situer autour de "
        f"{fr_number(forecast['yhat'])} {unit}, probablement entre "
        f"{fr_number(forecast['lower_80'])} et {fr_number(forecast['upper_80'])} {unit}."
    )


STALE_MONTHS = 6  # a neighbour's last reading older than this is greyed: "relevé ancien"
QUIET_MONTHS = 12  # no alert for longer than this: say so in "Ce qui s'est passé"
MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre")  # fmt: skip


def months_between(earlier: str, later: str) -> int:
    """Whole months from earlier to later (ISO dates, day ignored)."""
    y1, m1 = int(earlier[:4]), int(earlier[5:7])
    y2, m2 = int(later[:4]), int(later[5:7])
    return (y2 - y1) * 12 + (m2 - m1)


def is_stale(last_obs_date: str | None, data_until: str, months: int = STALE_MONTHS) -> bool:
    """True when a market's last reading is more than `months` older than the data date."""
    return last_obs_date is None or months_between(last_obs_date, data_until) > months


def quiet_sentence(
    last_alert_period: str | None, data_until: str, months: int = QUIET_MONTHS
) -> str | None:
    """'Aucune alerte depuis <mois année>.' when the last alert is over `months` old."""
    if last_alert_period is None:
        return "Aucune alerte enregistrée pour ce marché."
    if months_between(last_alert_period, data_until) <= months:
        return None
    month = MONTHS_FR[int(last_alert_period[5:7]) - 1]
    return f"Aucune alerte depuis {month} {last_alert_period[:4]}."
