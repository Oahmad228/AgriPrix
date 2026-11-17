"""Download CHIRPS v3 monthly rainfall for the study area (protocol section 2, CHIRPS v3).

The Climate Hazards Center serves one ~5.5 MB GeoTIFF per month for Africa and rate-limits
clients (HTTP 429). We download politely (one file at a time, pause between files, backoff
on 429), keep only the study box around the markets, and record for every month the
server posting date and the SHA-256 of the original file in a versioned manifest.

The posting date matters: the archive was reprocessed (most files posted in Nov. 2024),
so the values are today's final ones, not what was published at the time. The protocol's
publication-lag rule (month m usable from m + 1) is applied later, at feature time.

    python -m src.research.chirps            # download what is missing, update the manifest
    python -m src.research.chirps --dry-run  # list what would be downloaded
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

logger = logging.getLogger("agriprix.research.chirps")

BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/"
USER_AGENT = "AgriPrix-research/1.0 (+https://github.com/Oahmad228/AgriPrix)"
# Markets of SEN, MLI, BFA, NER span lat 9.88-20.20 and lon -17.46-13.11 (dim_market);
# the box adds a margin larger than the 25 km extraction radius.
STUDY_BOX = (-18.5, 8.5, 14.5, 21.5)  # west, south, east, north (degrees)
RAW_DIR = Path("data/raw/chirps_v3")
MANIFEST = Path("data/external/chirps_v3_manifest.csv")
PAUSE_SECONDS = 4.0
MAX_ATTEMPTS = 6

_ROW = re.compile(
    r'href="(chirps-v3\.0\.(\d{4})\.(\d{2})\.tif)".*?(\d{4}-[A-Z][a-z]{2}-\d{2} \d{2}:\d{2})',
    re.S,
)


@dataclass(frozen=True)
class RemoteFile:
    name: str
    month: str  # "YYYY-MM"
    posted_at: str  # server "Last modified", ISO format, UTC as shown by the server


def parse_listing(html: str) -> list[RemoteFile]:
    """Monthly files and their posting dates from the server's directory listing."""
    files = {}
    for row in html.split("\n"):
        match = _ROW.search(row)
        if match:
            name, year, month, posted = match.groups()
            iso = datetime.strptime(posted, "%Y-%b-%d %H:%M").strftime("%Y-%m-%dT%H:%M")
            files[name] = RemoteFile(name, f"{year}-{month}", iso)
    return sorted(files.values(), key=lambda f: f.month)


def _get(client: httpx.Client, url: str) -> httpx.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.get(url)
        if response.status_code == 200:
            return response
        if response.status_code in (429, 500, 502, 503, 504) and attempt < MAX_ATTEMPTS:
            wait = 60 * attempt
            logger.warning(
                "HTTP %s on %s, retry %d in %ds", response.status_code, url, attempt, wait
            )
            time.sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError(f"giving up on {url}")  # pragma: no cover - loop always returns/raises


def clip_to_box(source: Path, target: Path, box: tuple[float, float, float, float]) -> None:
    """Write the study box of a GeoTIFF (compressed), keeping its grid and nodata value."""
    import rasterio
    from rasterio.windows import from_bounds

    with rasterio.open(source) as src:
        window = from_bounds(*box, transform=src.transform).round_offsets().round_lengths()
        data = src.read(1, window=window)
        profile = src.profile | {
            "height": data.shape[0],
            "width": data.shape[1],
            "transform": src.window_transform(window),
            "compress": "deflate",
            "tiled": False,
        }
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
    target.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(target, "w", **profile) as dst:
        dst.write(data, 1)


def read_manifest(path: Path = MANIFEST) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["month"]: row for row in csv.DictReader(handle)}


def write_manifest(rows: dict[str, dict[str, str]], path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["month", "file", "server_posted_at", "downloaded_at_utc", "sha256_original", "bytes"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows[m] for m in sorted(rows))


def sync(dry_run: bool = False) -> int:  # pragma: no cover - network, exercised manually
    manifest = read_manifest()
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True
    ) as client:
        remote = parse_listing(_get(client, BASE_URL).text)
        todo = [f for f in remote if f.month not in manifest or not (RAW_DIR / f.name).exists()]
        logger.info("%d monthly files on the server, %d to download", len(remote), len(todo))
        if dry_run:
            return len(todo)
        for index, item in enumerate(todo, 1):
            content = _get(client, BASE_URL + item.name).content
            with tempfile.TemporaryDirectory() as tmp:
                original = Path(tmp) / item.name
                original.write_bytes(content)
                clip_to_box(original, RAW_DIR / item.name, STUDY_BOX)
            manifest[item.month] = {
                "month": item.month,
                "file": item.name,
                "server_posted_at": item.posted_at,
                "downloaded_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M"),
                "sha256_original": hashlib.sha256(content).hexdigest(),
                "bytes": str(len(content)),
            }
            if index % 10 == 0 or index == len(todo):
                write_manifest(manifest)
                logger.info("%d/%d downloaded (last: %s)", index, len(todo), item.month)
            time.sleep(PAUSE_SECONDS)
    write_manifest(manifest)
    return len(todo)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Download CHIRPS v3 monthly rainfall")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sync(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
