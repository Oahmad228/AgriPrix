"""Parse WFP (HDX) and FAOSTAT source files into one normalized long table.

Every output row is one observation with all the attributes needed to build the series
catalog. Invalid rows are not dropped silently: they are returned as *rejects* with a
reason code and their raw payload (quality gate DQ-04, quarantine).
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.etl.reference import MOROCCO_FOOD_CPI_ITEM, UNIT_BY_RAW, commodity_group

WFP_REQUIRED_COLUMNS = (
    "date",
    "admin1",
    "admin2",
    "market",
    "market_id",
    "latitude",
    "longitude",
    "category",
    "commodity",
    "commodity_id",
    "unit",
    "priceflag",
    "pricetype",
    "currency",
    "price",
)
FAOSTAT_REQUIRED_COLUMNS = ("Area Code", "Item Code", "Item", "Element Code", "Months Code")
MOROCCO_FAOSTAT_AREA_CODE = 143

OBS_COLUMNS = [
    "source_file",
    "line_number",
    "country_iso3",
    "market_code",
    "source_market_id",
    "market_name",
    "admin1_region",
    "admin2_district",
    "latitude",
    "longitude",
    "granularity_level",
    "commodity_code",
    "source_commodity_id",
    "commodity_name_en",
    "commodity_group",
    "category",
    "is_food_security_basket",
    "price_type",
    "raw_unit",
    "currency_code",
    "frequency",
    "value_type",
    "reference_year",
    "reference_month",
    "raw_value",
    "source_flag",
]
REJECT_COLUMNS = ["source_file", "line_number", "reason_code", "raw_payload_json"]

# FAOSTAT quality flags (see the *_Flags.csv shipped in each bulk zip).
FAO_FLAG_TO_SOURCE_FLAG = {
    "": "fao_official",
    "A": "fao_official",
    "X": "fao_external",
    "B": "fao_break",
    "E": "fao_estimated",
    "I": "fao_imputed",
}


class SourceSchemaError(RuntimeError):
    """Blocking DQ-03 failure: a mandatory column is missing from a source file."""


@dataclass
class ParseResult:
    observations: pd.DataFrame
    rejects: pd.DataFrame
    rows_read: int


def _payload(row: pd.Series) -> str:
    return json.dumps({k: (None if pd.isna(v) else str(v)) for k, v in row.items()})


def _rejects(frame: pd.DataFrame, mask: pd.Series, reason: str, source: str) -> pd.DataFrame:
    bad = frame[mask]
    return pd.DataFrame(
        {
            "source_file": source,
            "line_number": bad["_line"].astype(int).to_numpy(),
            "reason_code": reason,
            "raw_payload_json": [_payload(r.drop(labels="_line")) for _, r in bad.iterrows()],
        },
        columns=REJECT_COLUMNS,
    )


def _check_columns(columns: pd.Index, required: tuple[str, ...], source: str) -> None:
    missing = [c for c in required if c not in columns]
    if missing:
        raise SourceSchemaError(f"{source}: missing mandatory columns {missing} (DQ-03)")


def parse_wfp_csv(path: Path, country_iso3: str, source_name: str) -> ParseResult:
    """Parse one WFP country CSV. Line numbers refer to the physical file (header = 1)."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    _check_columns(raw.columns, WFP_REQUIRED_COLUMNS, source_name)
    raw["_line"] = np.arange(2, len(raw) + 2)
    # Older HDX exports carry an HXL hashtag row (#date, #adm1...) right after the header.
    raw = raw[~raw["date"].str.startswith("#")]
    rows_read = len(raw)

    dates = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    price = pd.to_numeric(raw["price"], errors="coerce")
    lat = pd.to_numeric(raw["latitude"].replace("", np.nan), errors="coerce")
    lon = pd.to_numeric(raw["longitude"].replace("", np.nan), errors="coerce")
    market_id = pd.to_numeric(raw["market_id"], errors="coerce")
    commodity_id = pd.to_numeric(raw["commodity_id"], errors="coerce")

    checks = [
        ("INVALID_DATE", dates.isna()),
        ("INVALID_PRICE", price.isna()),
        ("NON_POSITIVE_PRICE", price.notna() & (price <= 0)),
        ("INVALID_GPS", ~(lat.between(-90, 90) & lon.between(-180, 180))),
        ("UNKNOWN_UNIT", ~raw["unit"].isin(UNIT_BY_RAW.keys())),
        ("UNKNOWN_PRICEFLAG", ~raw["priceflag"].isin(["actual", "aggregate"])),
        ("INVALID_MARKET_ID", market_id.isna()),
        ("INVALID_COMMODITY_ID", commodity_id.isna()),
        ("UNEXPECTED_CURRENCY", raw["currency"] != "XOF"),
    ]
    rejected = pd.Series(False, index=raw.index)
    reject_frames = []
    for reason, mask in checks:
        new = mask & ~rejected  # one reason per row: the first failing check
        if new.any():
            reject_frames.append(_rejects(raw, new, reason, source_name))
        rejected |= mask

    ok = ~rejected
    good = raw[ok]
    groups = good["commodity"].map(commodity_group)
    obs = pd.DataFrame(
        {
            "source_file": source_name,
            "line_number": good["_line"].astype(int),
            "country_iso3": country_iso3,
            "market_code": country_iso3 + "_" + market_id[ok].astype(int).astype(str),
            "source_market_id": market_id[ok].astype(int),
            "market_name": good["market"],
            "admin1_region": good["admin1"].replace("", None),
            "admin2_district": good["admin2"].replace("", None),
            "latitude": lat[ok],
            "longitude": lon[ok],
            "granularity_level": "MARKET",
            "commodity_code": "WFP_" + commodity_id[ok].astype(int).astype(str),
            "source_commodity_id": commodity_id[ok].astype(int),
            "commodity_name_en": good["commodity"],
            "commodity_group": groups,
            "category": good["category"],
            "is_food_security_basket": groups != "Other",
            "price_type": good["pricetype"],
            "raw_unit": good["unit"],
            "currency_code": good["currency"],
            "frequency": "MONTHLY",
            "value_type": "PRICE",
            "reference_year": dates[ok].dt.year.astype(int),
            "reference_month": dates[ok].dt.month.astype(int),
            "raw_value": price[ok],
            "source_flag": good["priceflag"],
        },
        columns=OBS_COLUMNS,
    )
    rejects = (
        pd.concat(reject_frames, ignore_index=True)
        if reject_frames
        else pd.DataFrame(columns=REJECT_COLUMNS)
    )
    return ParseResult(obs.reset_index(drop=True), rejects, rows_read)


def _read_faostat_zip(path: Path, member_suffix: str) -> pd.DataFrame:
    """Read the flagged (not *_NOFLAG) CSV of a FAOSTAT bulk zip."""
    with zipfile.ZipFile(path) as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise SourceSchemaError(f"{path.name}: corrupted zip member {bad_member}")
        name = next(n for n in zf.namelist() if n.endswith(member_suffix))
        data = zf.read(name)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)


# (item_code, element_code) -> (value_type, unit, currency, commodity_group, is_basket)
CPI_SERIES = {
    (23013, 6125): ("INDEX", "INDEX_2015_100", "NONE", "CPI_Food", True),
    (23012, 6125): ("INDEX", "INDEX_2015_100", "NONE", "CPI_General", False),
    (23014, 6121): ("INFLATION_RATE", "PCT", "NONE", "CPI_Food_Inflation", False),
}
# Producer prices: local currency (5530 = LCU/tonne = MAD/tonne) and price index (5539).
# 5531 (SLC, identical to LCU for Morocco) and 5532 (USD) are deliberately not loaded:
# values are stored in local currency only (ADR-006).
PRODUCER_ELEMENTS = {
    5530: ("PRICE", "TONNE", "MAD"),
    5539: ("INDEX", "INDEX_2014_2016_100", "NONE"),
}


def parse_faostat_zip(path: Path, kind: str, source_name: str) -> ParseResult:
    """Parse the Morocco rows of a FAOSTAT bulk zip (kind = 'cpi' or 'prices')."""
    member = "ConsumerPriceIndices_E_Africa.csv" if kind == "cpi" else "Prices_E_Africa.csv"
    wide = _read_faostat_zip(path, member)
    _check_columns(wide.columns, FAOSTAT_REQUIRED_COLUMNS, source_name)
    wide["_line"] = np.arange(2, len(wide) + 2)
    wide = wide[pd.to_numeric(wide["Area Code"], errors="coerce") == MOROCCO_FAOSTAT_AREA_CODE]

    item = pd.to_numeric(wide["Item Code"], errors="coerce").astype("Int64")
    element = pd.to_numeric(wide["Element Code"], errors="coerce").astype("Int64")
    if kind == "cpi":
        keep = [(i, e) in CPI_SERIES for i, e in zip(item, element, strict=True)]
    else:
        keep = element.isin(list(PRODUCER_ELEMENTS)).fillna(False).to_numpy()
    wide = wide[keep]

    year_cols = [c for c in wide.columns if len(c) == 5 and c.startswith("Y") and c[1:].isdigit()]
    records = []
    reject_frames = []
    for _, row in wide.iterrows():
        item_code = int(row["Item Code"])
        element_code = int(row["Element Code"])
        if kind == "cpi":
            value_type, unit, currency, group, basket = CPI_SERIES[(item_code, element_code)]
            month = int(row["Months Code"]) - 7000
            frequency, price_type, code = "MONTHLY", "CPI", f"FAO_CPI_{item_code}"
            if not 1 <= month <= 12:
                continue
        else:
            value_type, unit, currency = PRODUCER_ELEMENTS[element_code]
            group, basket, month = "Producer_Prices", False, None
            frequency, price_type, code = "ANNUAL", "Producer", f"FAO_PP_{item_code}"

        for col in year_cols:
            raw_value = row[col]
            if raw_value == "":
                continue  # missing value: nothing was published, nothing to reject
            flag = row.get(f"{col}F", "")
            value = pd.to_numeric(raw_value, errors="coerce")
            reason = None
            if pd.isna(value):
                reason = "INVALID_PRICE"
            elif value_type != "INFLATION_RATE" and value <= 0:
                reason = "NON_POSITIVE_PRICE"
            elif flag not in FAO_FLAG_TO_SOURCE_FLAG:
                reason = "UNKNOWN_FAO_FLAG"
            if reason:
                payload = row.drop(labels="_line").to_dict() | {"year_column": col}
                reject_frames.append(
                    pd.DataFrame(
                        [[source_name, int(row["_line"]), reason, json.dumps(payload)]],
                        columns=REJECT_COLUMNS,
                    )
                )
                continue
            records.append(
                {
                    "source_file": source_name,
                    "line_number": int(row["_line"]),
                    "country_iso3": "MAR",
                    "market_code": "MAR_NATIONAL",
                    "source_market_id": None,
                    "market_name": "Maroc (national)",
                    "admin1_region": None,
                    "admin2_district": None,
                    "latitude": None,
                    "longitude": None,
                    "granularity_level": "NATIONAL",
                    "commodity_code": code,
                    "source_commodity_id": item_code,
                    "commodity_name_en": row["Item"],
                    "commodity_group": group,
                    "category": "FAOSTAT consumer price indices"
                    if kind == "cpi"
                    else "FAOSTAT producer prices",
                    "is_food_security_basket": basket and item_code == MOROCCO_FOOD_CPI_ITEM,
                    "price_type": price_type,
                    "raw_unit": unit,
                    "currency_code": currency,
                    "frequency": frequency,
                    "value_type": value_type,
                    "reference_year": int(col[1:]),
                    "reference_month": month,
                    "raw_value": float(value),
                    "source_flag": FAO_FLAG_TO_SOURCE_FLAG[flag],
                }
            )
    obs = pd.DataFrame(records, columns=OBS_COLUMNS)
    rejects = (
        pd.concat(reject_frames, ignore_index=True)
        if reject_frames
        else pd.DataFrame(columns=REJECT_COLUMNS)
    )
    rows_read = len(obs) + len(rejects)
    return ParseResult(obs, rejects, rows_read)
