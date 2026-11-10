"""Shared fixtures: synthetic source files and an isolated warehouse schema.

Tests never download anything and never touch the real `public` schema: integration
tests run the full ETL in a throw-away PostgreSQL schema that is dropped afterwards.
"""

from __future__ import annotations

import csv
import io
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from src.config import get_settings
from src.etl.db import make_writer_engine
from src.etl.parsers import WFP_REQUIRED_COLUMNS
from src.etl.reference import month_add

WFP_HEADER = list(WFP_REQUIRED_COLUMNS) + ["usdprice"]


def wfp_row(
    year: int,
    month: int,
    *,
    market: str = "Tilene",
    market_id: int = 447,
    commodity: str = "Millet",
    commodity_id: int = 73,
    unit: str = "KG",
    priceflag: str = "actual",
    pricetype: str = "Retail",
    price: float | str = 200.0,
    latitude: str = "14.68",
    longitude: str = "-17.46",
    date: str | None = None,
) -> dict[str, str]:
    return {
        "date": date or f"{year:04d}-{month:02d}-15",
        "admin1": "Dakar",
        "admin2": "Dakar",
        "market": market,
        "market_id": str(market_id),
        "latitude": latitude,
        "longitude": longitude,
        "category": "cereals and tubers",
        "commodity": commodity,
        "commodity_id": str(commodity_id),
        "unit": unit,
        "priceflag": priceflag,
        "pricetype": pricetype,
        "currency": "XOF",
        "price": str(price),
        "usdprice": "0.3",
    }


def monthly_rows(start: tuple[int, int], count: int, skip: set[int] = frozenset(), **kw) -> list:
    """``count`` consecutive monthly rows from ``start``, omitting offsets in ``skip``."""
    rows = []
    for offset in range(count):
        if offset in skip:
            continue
        year, month = month_add(start[0], start[1], offset)
        rows.append(wfp_row(year, month, price=100 + offset, **kw))
    return rows


def write_wfp_csv(path: Path, rows: list[dict[str, str]], header: list[str] | None = None) -> Path:
    header = header or WFP_HEADER
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_faostat_zip(path: Path, member: str, rows: list[dict[str, str]], years: range) -> Path:
    """Write a FAOSTAT-like bulk zip whose flagged CSV is named ``member``."""
    columns = [
        "Area Code",
        "Area Code (M49)",
        "Area",
        "Item Code",
        "Item",
        "Element Code",
        "Element",
        "Months Code",
        "Months",
        "Unit",
    ]
    for year in years:
        columns += [f"Y{year}", f"Y{year}F"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, restval="")
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(member, buffer.getvalue())
        zf.writestr(member.replace(".csv", "_NOFLAG.csv"), "unused")
    return path


def cpi_rows(item: int, element: int, years: range, flag: str = "X", value: float = 100.0):
    rows = []
    for month in range(1, 13):
        row = {
            "Area Code": "143",
            "Area Code (M49)": "'504",
            "Area": "Morocco",
            "Item Code": str(item),
            "Item": f"Item {item}",
            "Element Code": str(element),
            "Element": "Value",
            "Months Code": str(7000 + month),
            "Months": "M",
            "Unit": "",
        }
        for year in years:
            row[f"Y{year}"] = str(value + year - 2000 + month / 100)
            row[f"Y{year}F"] = flag
        rows.append(row)
    return rows


def producer_row(item: int, element: int, years: range, flag: str = "A", value: float = 3000.0):
    row = {
        "Area Code": "143",
        "Area Code (M49)": "'504",
        "Area": "Morocco",
        "Item Code": str(item),
        "Item": f"Crop {item}",
        "Element Code": str(element),
        "Element": "Producer Price",
        "Months Code": "7021",
        "Months": "Annual value",
        "Unit": "LCU",
    }
    for year in years:
        row[f"Y{year}"] = str(value)
        row[f"Y{year}F"] = flag
    return row


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """A complete, small raw directory with all 7 registered sources.

    Content (used by integration assertions):
      SEN: 1 eligible retail millet series (93 months to 2026-09), 1 wholesale series in
           100 KG, 1 stale series (ends 2020), 1 tomato series (outside basket), 1 row with a
           negative price (rejected).
      MLI/BFA/NER/CIV: one short series each (not eligible).
      MAR: CPI 23013 (2019-2026, flag X, eligible), 23012, 23014; producer prices (annual).
    """
    sen = monthly_rows((2019, 1), 93)
    sen += monthly_rows((2019, 1), 93, pricetype="Wholesale", unit="100 KG")
    sen += monthly_rows((2015, 1), 72, commodity="Rice (imported)", commodity_id=64)
    sen += monthly_rows((2022, 1), 30, commodity="Tomatoes", commodity_id=114)
    sen.append(wfp_row(2026, 9, market="Kaolack", market_id=448, price=-5))
    write_wfp_csv(tmp_path / "wfp_SEN.csv", sen)
    for iso, market_id in (("MLI", 247), ("BFA", 141), ("NER", 546), ("CIV", 127)):
        rows = monthly_rows((2024, 1), 12, market_id=market_id, market=f"M{market_id}")
        write_wfp_csv(tmp_path / f"wfp_{iso}.csv", rows)

    years = range(2019, 2027)
    write_faostat_zip(
        tmp_path / "ConsumerPriceIndices_E_Africa.zip",
        "ConsumerPriceIndices_E_Africa.csv",
        cpi_rows(23013, 6125, years)
        + cpi_rows(23012, 6125, years)
        + cpi_rows(23014, 6121, years, "E", -3),
        years,
    )
    write_faostat_zip(
        tmp_path / "Prices_E_Africa.zip",
        "Prices_E_Africa.csv",
        [producer_row(15, 5530, range(2020, 2024)), producer_row(15, 5532, range(2020, 2024))],
        range(2020, 2024),
    )
    return tmp_path


@pytest.fixture
def warehouse() -> Iterator[Engine]:
    """Writer engine bound to a fresh schema, dropped after the test."""
    schema = f"test_{uuid.uuid4().hex[:10]}"
    admin = make_writer_engine()
    readonly_user = get_settings().dw_readonly_user
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO {readonly_user}'))
        conn.execute(
            text(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" GRANT SELECT ON TABLES TO {readonly_user}'
            )
        )
    engine = make_writer_engine(schema)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            # Fail fast instead of hanging if a test leaked an open transaction.
            conn.execute(text("SET LOCAL lock_timeout = '15s'"))
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
