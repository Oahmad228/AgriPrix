"""Country-level harvest statements in CILSS-PREGEC notices (cross-check of GIEWS, protocol §2).

PREGEC notices are mostly regional; only a few sentences name a country with a production
statement. This module proposes those sentences (validated_by_ahmad = "no"). The
publication date used for the dating rule is conservative: the last day of the month in
which the PDF was uploaded (from its URL), never earlier than the meeting itself.

    python -m src.research.pregec
"""

from __future__ import annotations

import calendar
import csv
import logging
import re
from pathlib import Path

logger = logging.getLogger("agriprix.research.pregec")

RAW_DIR = Path("data/raw/pregec")
OUTPUT = Path("data/external/harvest_pregec.csv")
# Notices found on 2026-11-17 (docs/journal); key = meeting month, value = source URL.
NOTICES = {
    "2017-03": "https://www.inter-reseaux.org/wp-content/uploads/avis_pregec_mars-2017_vfinale.pdf",
    "2023-09": "https://agrhymet.cilss.int/wp-content/uploads/2023/09/Avis-PREGEC-Ouaga_Sept_2023_FR.pdf",
    "2024-03": "https://www.cilss.int/wp-content/uploads/2024/03/Avis_PREGEC_Lome_Mars2024_FR.pdf",
    "2024-09": "https://www.cilss.int/wp-content/uploads/2024/09/Avis-PREGEC-Niamey_Septembre2024_FR.pdf",
    "2024-12": "https://agrhymet.cilss.int/wp-content/uploads/2025/01/Avis_PREGEC_dec-2024_FR.pdf",
    "2025-03": "https://www.cilss.int/wp-content/uploads/2025/04/Avis_PREGEC_Lome_Mars_2025_FR.pdf",
    "2025-09": "https://www.cilss.int/wp-content/uploads/2025/09/AVIS_PREGEC_OUAGADOUGOU_SEPT_2025_FR.pdf",
    "2025-11": "https://agrhymet.cilss.int/wp-content/uploads/2025/11/Avis-PREGEC-Nov2025_FR.pdf",
    "2026-03": "https://agrhymet.cilss.int/wp-content/uploads/2026/04/Avis-PREGEC-mars-2026.pdf",
}
COUNTRIES = {
    "BFA": r"Burkina",
    "MLI": r"\bMali\b",
    "NER": r"\bNiger\b(?!ia)",
    "SEN": r"S[ée]n[ée]gal",
}
_PRODUCTION = re.compile(r"production[s]? c[ée]r[ée]ali|r[ée]colte", re.IGNORECASE)
_PRICE = re.compile(r"\bprix\b|fourrag|biomasse|bétail|pâturage", re.IGNORECASE)


def publication_date(url: str, meeting_month: str) -> str:
    """Last day of the upload month found in the URL (or of the meeting month)."""
    match = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    year, month = (
        (int(match.group(1)), int(match.group(2))) if match else map(int, meeting_month.split("-"))
    )
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def country_sentences(text: str) -> list[tuple[str, str]]:
    """(iso3, sentence) for sentences that name a study country next to cereal production
    and are not about prices or pasture."""
    text = re.sub(r"\s+", " ", text)
    out = []
    for sentence in re.split(r"(?<=[.;])\s+(?=[A-ZÉÀ0-9])", text):
        if not _PRODUCTION.search(sentence) or _PRICE.search(sentence):
            continue
        for iso, pattern in COUNTRIES.items():
            if re.search(pattern, sentence):
                out.append((iso, sentence.strip()[:400]))
    return out


def build() -> int:  # pragma: no cover - PDF parsing
    from pypdf import PdfReader

    rows = []
    for meeting, url in NOTICES.items():
        path = RAW_DIR / f"pregec_{meeting}.pdf"
        if not path.exists():
            logger.warning("missing %s (download it from %s)", path, url)
            continue
        text = " ".join(page.extract_text() or "" for page in PdfReader(path).pages)
        for iso, sentence in country_sentences(text):
            rows.append(
                {
                    "country_iso3": iso,
                    "meeting_month": meeting,
                    "publication_date": publication_date(url, meeting),
                    "statement": sentence,
                    "direction": "",
                    "pct_change": "",
                    "reference": "",
                    "url": url,
                    "validated_by_ahmad": "no",
                }
            )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("%d notices, %d country sentences proposed", len(NOTICES), len(rows))
    return len(rows)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build()
