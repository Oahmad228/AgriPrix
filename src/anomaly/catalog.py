"""Reference catalog of documented price shocks, FIXED A PRIORI (ADR-003 section 2.6).

This file was committed before the detector was run on real data (see git history):
the episodes, the (country, commodity group) couples, the periods and the detection
criterion below must never be edited to improve the validation result. A shock that is
not detected is an empirical result to report, not a reason to change this file.

Sources (verified links): docs/adr/003-strategie-ml-globale-fenetre-historique-rolling-origin.md
"""

from __future__ import annotations

from dataclasses import dataclass

# Alert thresholds on the robust z-score (ADR-003, docs/05-conception.md section 3.2).
WARNING_Z = 2.5
CRITICAL_Z = 3.5
# A couple is detected when, in at least one month of the episode, at least this share
# of its markets with a score that month raise an upward alert (z >= WARNING_Z).
# Chosen by Ahmad on 2026-11-10, before any run on real data.
MIN_SHARE_OF_MARKETS = 0.25
# KPI-M4 calm period and maximum alert rate (|z| >= WARNING_Z), both directions.
CALM_PERIOD = ((2015, 1), (2018, 12))
MAX_CALM_ALERT_RATE = 0.05
# Recall objective on the catalog (KPI-M4).
MIN_EPISODE_RECALL = 0.80

CEREALS = ("Rice", "Millet", "Sorghum", "Maize")


@dataclass(frozen=True)
class Episode:
    code: str
    title_fr: str
    start: tuple[int, int]  # (year, month), inclusive
    end: tuple[int, int]
    couples: tuple[tuple[str, str], ...]  # (country_iso3, commodity_group)
    source: str


CATALOG: tuple[Episode, ...] = (
    Episode(
        "SHOCK-01",
        "Crise alimentaire mondiale 2007-2008",
        (2008, 3),
        (2008, 9),
        (("SEN", "Rice"), ("NER", "Millet"), ("NER", "Sorghum")),
        "https://www.fao.org/4/i0291e/i0291e00.pdf",
    ),
    Episode(
        "SHOCK-02",
        "Crise alimentaire et pastorale sahélienne de 2012",
        (2012, 3),
        (2012, 9),
        tuple((c, g) for c in ("MLI", "NER", "BFA") for g in ("Millet", "Sorghum")),
        "https://reliefweb.int/report/mali/joint-special-report-grain-market-outlook-west-africa",
    ),
    Episode(
        "SHOCK-03",
        "Choc COVID-19 et fermetures de frontières (2020)",
        (2020, 4),
        (2020, 8),
        tuple((c, g) for c in ("SEN", "MLI", "BFA", "NER") for g in CEREALS),
        "https://reliefweb.int/report/burkina-faso/west-and-central-africa-market-situation-2020-and-2021-outlooks-march-2021",
    ),
    Episode(
        "SHOCK-04",
        "Choc inflationniste mondial et guerre en Ukraine (2022)",
        (2022, 3),
        (2022, 11),
        tuple((c, g) for c in ("BFA", "MLI", "SEN") for g in CEREALS) + (("MAR", "CPI_Food"),),
        "https://www.fao.org/3/cb9236en/cb9236en.pdf",
    ),
    Episode(
        "SHOCK-05",
        "Crise politique et sanctions CEDEAO au Niger (2023-2024)",
        (2023, 8),
        (2024, 3),
        (("NER", "Rice"), ("NER", "Maize"), ("NER", "Millet")),
        "https://reliefweb.int/report/niger/niger-preliminary-analysis-impacts-political-crisis-and-sanctions-food-security-and-markets-12-august-2023",
    ),
)
