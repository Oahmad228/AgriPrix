"""Harvest estimates and trade measures from FAO-GIEWS country briefs (protocol section 2).

Each brief carries a "Reference Date", which is its publication date for the protocol's
dating rule. This module only PROPOSES rows: every row keeps the quoted sentence, the PDF
URL and the page, and starts with validated_by_ahmad = "no". Ahmad validates each row by
hand before anything is used by a model (protocol sections 2 and 13).

    python -m src.research.giews   # downloads the briefs, writes the two proposal files
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger("agriprix.research.giews")

COUNTRIES = ("SEN", "MLI", "BFA", "NER")
URLS = {
    "archive": "https://cb.apps.fao.org/country/{iso}/pdf_archive/{iso}_Archive.pdf",
    "current": "https://cb.apps.fao.org/country/{iso}/pdf/{iso}.pdf",
}
RAW_DIR = Path("data/raw/giews")
HARVEST_OUT = Path("data/external/harvest_giews.csv")
EVENTS_OUT = Path("data/external/events_proposed_giews.csv")
BULLETS_OUT = Path("data/processed/research/harvest_giews_all_bullets.csv")
USER_AGENT = "AgriPrix-research/1.0 (+https://github.com/Oahmad228/AgriPrix)"

_DATE = re.compile(r"Reference Date:\s*(\d{1,2}-[A-Za-z]+-\d{4})")
_SENTENCE = re.compile(r"[^.]*\.")
_PRODUCTION = re.compile(
    r"(aggregate cereal|cereal production|cereal output|cereal harvest)", re.IGNORECASE
)
_YEAR = re.compile(r"\b(20[0-3]\d)\b")
_PCT = re.compile(
    r"(\d+(?:\.\d+)?)\s*percent\s+(above|below|higher|lower)[^.]{0,80}?(average|previous year|last year|2\d{3})",
    re.IGNORECASE,
)
_TRADE = re.compile(
    r"(export ban|ban on (?:the )?export|exports? (?:were|was|has been|have been) (?:banned|suspended)"
    r"|suspension of (?:cereal |grain )?exports|border closure|closure of (?:the )?borders?"
    r"|borders?\b[^.]{0,40}\b(?:were|was|remained|are|is) closed|sanctions)",
    re.IGNORECASE,
)


@dataclass
class Brief:
    iso3: str
    reference_date: str  # ISO date
    url: str
    page: int  # 1-based page of the PDF where the brief starts
    text: str


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
)}  # fmt: skip


def parse_reference_date(value: str) -> str:
    """ISO date from "05-December-2024"; tolerant to typos in the month after its 3 letters
    (the archive contains "09-Sepetmber-2010")."""
    day, month, year = value.split("-")
    return datetime(int(year), _MONTHS[month[:3].lower()], int(day)).date().isoformat()


def split_briefs(pages: list[str], iso3: str, url: str) -> list[Brief]:
    """Cut the concatenated pages of a GIEWS PDF into briefs at each "Reference Date"."""
    joined, starts = "", []
    for number, page in enumerate(pages, 1):
        starts.append((len(joined), number))
        joined += page + "\n"
    matches = list(_DATE.finditer(joined))
    briefs = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(joined)
        page = max(n for offset, n in starts if offset <= match.start())
        date = parse_reference_date(match.group(1))
        briefs.append(Brief(iso3, date, url, page, joined[match.start() : end]))
    return briefs


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# GIEWS snapshot headline, e.g. "Cereal production in 2024 estimated at above-average level".
_HEADLINE = re.compile(
    r"(?:aggregate )?cereal (?:production|output|harvest) in (\d{4}) (?:was |is )?"
    r"(estimated|forecast|officially estimated|anticipated|expected)\s+(?:to be\s+)?(?:at\s+)?(?:an?\s+)?"
    r"((?:well |slightly |about |near[- ]|record |)(?:above|below|near|close to )?[- ]?average|record|bumper"
    r"|(?:well |slightly )?(?:above|below) (?:the )?(?:five-year )?average)",
    re.IGNORECASE,
)


def _direction(level: str) -> str:
    level = level.lower()
    if "above" in level or "record" in level or "bumper" in level:
        return "1"
    if "below" in level:
        return "-1"
    return "0"  # average, near-average, close to average


_BULLET = re.compile(r"[•]|\s{2,}")
_HARVEST_WORD = re.compile(r"\b(production|harvest|crops?|output)\b", re.IGNORECASE)
_UP = re.compile(
    r"above[- ]average|record|bumper|well above|increase|improved|higher", re.IGNORECASE
)
_DOWN = re.compile(r"below[- ]average|reduced|decline|drop|lower|decrease|deficit", re.IGNORECASE)
_AVERAGE = re.compile(r"near[- ]average|average", re.IGNORECASE)
_PROSPECT = re.compile(r"prospect|uncertain|planting|cropping season|rains", re.IGNORECASE)
_ANY_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*percent", re.IGNORECASE)


def snapshot(text: str) -> str:
    """The "FOOD SECURITY SNAPSHOT" headline block at the top of a brief."""
    match = re.search(r"SNAPSHOT(.{0,700})", text, re.S)
    return match.group(1) if match else text[:700]


def classify_bullet(bullet: str) -> tuple[str, str, str] | None:
    """(kind, direction, reference) for a harvest bullet, or None if not about the harvest.

    kind: estimate (harvest done), forecast (harvest expected) or prospect (season under
    way, no quantified view). reference: 5y_avg when the wording compares to the average,
    prev_year for an increase/decrease, record for record/bumper crops."""
    if not _HARVEST_WORD.search(bullet) or re.search(r"price|import|export", bullet, re.I):
        return None
    lower = bullet.lower()
    kind = (
        "estimate" if re.search(r"estimat|gathered|harvested|obtained|was|were", lower)
        else "forecast" if re.search(r"forecast|expected|anticipated|points to", lower)
        else "prospect"
    )  # fmt: skip
    if (
        "above-average" in lower
        or "above average" in lower
        or "below-average" in lower
        or ("below average" in lower)
    ):
        return kind, ("1" if "above" in lower else "-1"), "5y_avg"
    if re.search(r"record|bumper", lower):
        return kind, "1", "record"
    if _AVERAGE.search(lower):
        return kind, "0", "5y_avg"
    if _UP.search(lower):
        return kind, "1", "prev_year"
    if _DOWN.search(lower):
        return kind, "-1", "prev_year"
    if _PROSPECT.search(lower):
        return "prospect", "", ""
    return None


def harvest_rows(brief: Brief) -> list[dict[str, str]]:
    """Proposed rows from the snapshot bullets about the cereal harvest (one per bullet)."""
    text = re.sub(r"(above|below|near)-\s+average", r"\1-average", brief.text)
    rows = []
    for bullet in (_clean(b) for b in _BULLET.split(snapshot(text))):
        if len(bullet) < 15:
            continue
        found = classify_bullet(bullet)
        if not found:
            continue
        kind, direction, reference = found
        years = [int(y) for y in _YEAR.findall(bullet) if int(y) <= int(brief.reference_date[:4])]
        pct = _ANY_PCT.search(bullet)
        value = ""
        if pct and direction in ("1", "-1"):
            value = f"{float(pct.group(1)) * int(direction):g}"
        rows.append(
            {
                "country_iso3": brief.iso3,
                "reference_date": brief.reference_date,
                "harvest_year": str(max(years)) if years else "",
                "kind": kind,
                "direction": direction,
                "reference": reference,
                "pct_change": value,
                "statement": bullet[:300],
                "url": brief.url,
                "page": str(brief.page),
                "validated_by_ahmad": "no",
            }
        )
    return rows


_KIND_RANK = {"estimate": 0, "forecast": 1, "prospect": 2}


def consolidate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """One proposed row per brief for Ahmad's validation: the most informative bullet
    (an estimate before a forecast before a prospect; a bullet with a direction first; the
    latest harvest year first)."""
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["country_iso3"], row["reference_date"])
        rank = (
            row["direction"] == "",
            _KIND_RANK[row["kind"]],
            -int(row["harvest_year"] or 0),
        )
        if key not in best or rank < best[key][0]:
            best[key] = (rank, row)
    return [
        row
        for _, row in sorted(
            best.values(), key=lambda item: (item[1]["country_iso3"], item[1]["reference_date"])
        )
    ]


def event_rows(brief: Brief) -> list[dict[str, str]]:
    """Proposed trade-measure rows: sentences mentioning bans, border closures or sanctions."""
    rows = []
    for raw in _SENTENCE.findall(_clean(brief.text)):
        sentence = raw.strip()
        match = _TRADE.search(sentence)
        if not match or len(sentence) > 400:
            continue
        kind = "sanctions" if "sanction" in match.group(0).lower() else (
            "border_closure" if "border" in match.group(0).lower() else "export_ban"
        )  # fmt: skip
        rows.append(
            {
                "country_iso3": brief.iso3,
                "type": kind,
                "products": "",
                "start_date": "",
                "end_date": "",
                "publication_date": brief.reference_date,
                "statement": sentence,
                "url": brief.url,
                "page": str(brief.page),
                "validated_by_ahmad": "no",
            }
        )
    return rows


def _write(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def collect() -> tuple[int, int]:  # pragma: no cover - network and PDF parsing
    from pypdf import PdfReader

    briefs: dict[tuple[str, str], Brief] = {}
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True
    ) as client:
        for iso in COUNTRIES:
            for kind, template in URLS.items():
                url = template.format(iso=iso)
                path = RAW_DIR / f"{iso}_{kind}.pdf"
                if not path.exists():
                    response = client.get(url)
                    response.raise_for_status()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(response.content)
                    time.sleep(2)
                pages = [p.extract_text() or "" for p in PdfReader(path).pages]
                for brief in split_briefs(pages, iso, url):
                    briefs.setdefault(
                        (iso, brief.reference_date), brief
                    )  # archive and current overlap
    ordered = sorted(briefs.values(), key=lambda b: (b.iso3, b.reference_date))
    bullets = [row for brief in ordered for row in harvest_rows(brief)]
    _write(bullets, BULLETS_OUT)  # every candidate bullet, for reference (not versioned)
    harvest = consolidate(bullets)
    events = [row for brief in ordered for row in event_rows(brief)]
    _write(harvest, HARVEST_OUT)
    _write(events, EVENTS_OUT)
    logger.info(
        "%d briefs -> %d harvest rows, %d event rows proposed",
        len(ordered),
        len(harvest),
        len(events),
    )
    for iso in COUNTRIES:
        dates = [b.reference_date for b in ordered if b.iso3 == iso]
        logger.info("%s: %d briefs from %s to %s", iso, len(dates), min(dates), max(dates))
    return len(harvest), len(events)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    argparse.ArgumentParser(
        description="Propose harvest and trade rows from GIEWS briefs"
    ).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    collect()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
