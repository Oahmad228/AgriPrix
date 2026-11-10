"""Source registry and integrity-checked downloads (quality gates DQ-01 and DQ-02).

DQ-01 (anti-WAF): HDX sits behind an AWS WAF that answers burst downloads with an empty
``HTTP 202`` challenge instead of the file. Such responses are retried with exponential
backoff and never parsed.

DQ-02 (anti-truncation): every file is checked against the size and MD5 published by
its provider *before* any parsing: the CKAN ``package_show`` API for HDX, the S3 ``ETag``
(the MD5 of single-part uploads) for FAOSTAT. A truncated ``wfp_NER.csv`` was observed
during the Phase 0 audit; this gate makes that failure loud instead of silent.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger("agriprix.etl.sources")

HDX_API = "https://data.humdata.org/api/3/action/package_show"
FAOSTAT_BULK = "https://bulks-faostat.fao.org/production"
USER_AGENT = "agriprix-observatory-etl/0.1 (+https://github.com/Oahmad228/AgriPrix)"
_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


class SourceIntegrityError(RuntimeError):
    """Raised when a source file cannot be retrieved intact (blocking DQ-01/DQ-02)."""


@dataclass(frozen=True)
class SourceSpec:
    name: str
    kind: str  # "hdx" or "faostat"
    locator: str  # HDX dataset id, or FAOSTAT bulk zip file name
    filename: str
    country_iso3: str


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec("wfp_SEN", "hdx", "wfp-food-prices-for-senegal", "wfp_SEN.csv", "SEN"),
    SourceSpec("wfp_MLI", "hdx", "wfp-food-prices-for-mali", "wfp_MLI.csv", "MLI"),
    SourceSpec("wfp_BFA", "hdx", "wfp-food-prices-for-burkina-faso", "wfp_BFA.csv", "BFA"),
    SourceSpec("wfp_NER", "hdx", "wfp-food-prices-for-niger", "wfp_NER.csv", "NER"),
    SourceSpec("wfp_CIV", "hdx", "wfp-food-prices-for-cote-d-ivoire", "wfp_CIV.csv", "CIV"),
    SourceSpec(
        "faostat_cpi",
        "faostat",
        "ConsumerPriceIndices_E_Africa.zip",
        "ConsumerPriceIndices_E_Africa.zip",
        "MAR",
    ),
    SourceSpec("faostat_prices", "faostat", "Prices_E_Africa.zip", "Prices_E_Africa.zip", "MAR"),
)


@dataclass(frozen=True)
class ExpectedFile:
    url: str
    size_bytes: int
    md5: str
    last_modified: str | None


@dataclass(frozen=True)
class RetrievedFile:
    spec: SourceSpec
    path: Path
    url: str
    size_bytes: int
    md5: str
    last_modified: str | None
    from_cache: bool


def md5_of(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def resolve_expected(client: httpx.Client, spec: SourceSpec) -> ExpectedFile:
    """Ask the provider which file version is current and what it should look like."""
    if spec.kind == "hdx":
        response = client.get(HDX_API, params={"id": spec.locator})
        response.raise_for_status()
        resources = response.json()["result"]["resources"]
        matches = [
            r
            for r in resources
            if "wfp_food_prices_" in (r.get("download_url") or "")
            and (r.get("format") or "").upper() == "CSV"
        ]
        if len(matches) != 1:
            raise SourceIntegrityError(
                f"{spec.name}: expected exactly one WFP price CSV in {spec.locator}, "
                f"found {len(matches)}"
            )
        res = matches[0]
        md5 = (res.get("hash") or "").lower()
        if not _MD5_RE.match(md5) or not res.get("size"):
            raise SourceIntegrityError(f"{spec.name}: HDX metadata has no usable size/MD5")
        return ExpectedFile(res["download_url"], int(res["size"]), md5, res.get("last_modified"))

    if spec.kind == "faostat":
        url = f"{FAOSTAT_BULK}/{spec.locator}"
        head = client.head(url)
        head.raise_for_status()
        etag = (head.headers.get("etag") or "").strip('"').lower()
        size = int(head.headers.get("content-length") or 0)
        if not _MD5_RE.match(etag) or size <= 0:
            raise SourceIntegrityError(
                f"{spec.name}: FAOSTAT did not publish a single-part MD5 ETag and size"
            )
        return ExpectedFile(url, size, etag, head.headers.get("last-modified"))

    raise ValueError(f"Unknown source kind: {spec.kind}")


def fetch(
    client: httpx.Client,
    spec: SourceSpec,
    raw_dir: Path,
    *,
    max_attempts: int = 4,
    backoff_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> RetrievedFile:
    """Return a verified local copy of ``spec``, downloading it only when needed."""
    expected = resolve_expected(client, spec)
    target = raw_dir / spec.filename

    if target.exists():
        local = target.read_bytes()
        if len(local) == expected.size_bytes and md5_of(local) == expected.md5:
            logger.info("%s: local copy matches provider MD5, download skipped", spec.name)
            return RetrievedFile(
                spec, target, expected.url, len(local), expected.md5, expected.last_modified, True
            )

    last_problem = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        response = client.get(expected.url)
        body = response.content
        if response.status_code == 202 or len(body) == 0:
            last_problem = f"DQ-01 empty/WAF response (HTTP {response.status_code})"
        elif response.status_code != 200:
            last_problem = f"DQ-01 HTTP {response.status_code}"
        elif len(body) != expected.size_bytes:
            last_problem = f"DQ-02 size {len(body)} != expected {expected.size_bytes} (truncated?)"
        elif md5_of(body) != expected.md5:
            last_problem = "DQ-02 MD5 mismatch with provider metadata"
        else:
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(body)
            tmp.replace(target)
            logger.info("%s: downloaded and verified (%d bytes)", spec.name, len(body))
            return RetrievedFile(
                spec, target, expected.url, len(body), expected.md5, expected.last_modified, False
            )
        logger.warning(
            "%s: attempt %d/%d failed: %s", spec.name, attempt, max_attempts, last_problem
        )
        if attempt < max_attempts:
            sleep(backoff_seconds * 2 ** (attempt - 1))

    raise SourceIntegrityError(f"{spec.name}: {last_problem} after {max_attempts} attempts")


def fetch_all(
    raw_dir: Path,
    *,
    delay_between_files: float = 2.0,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[RetrievedFile]:
    """Retrieve every registered source, spacing requests to stay under the HDX WAF limit."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=120.0, follow_redirects=True
    )
    try:
        results = []
        for index, spec in enumerate(SOURCES):
            if index:
                sleep(delay_between_files)
            results.append(fetch(client, spec, raw_dir, sleep=sleep))
        return results
    finally:
        if own_client:
            client.close()
