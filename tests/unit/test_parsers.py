"""Source parsers: schema gate (DQ-03), row quarantine (DQ-04) and FAOSTAT flags."""

import json
from pathlib import Path

import pytest
from src.etl.parsers import SourceSchemaError, parse_faostat_zip, parse_wfp_csv

from tests.conftest import (
    WFP_HEADER,
    cpi_rows,
    producer_row,
    wfp_row,
    write_faostat_zip,
    write_wfp_csv,
)


def test_wfp_valid_rows_are_parsed(tmp_path: Path) -> None:
    path = write_wfp_csv(tmp_path / "w.csv", [wfp_row(2024, 1), wfp_row(2024, 2, unit="100 KG")])
    result = parse_wfp_csv(path, "SEN", "wfp_SEN")
    obs = result.observations
    assert result.rows_read == 2
    assert result.rejects.empty
    assert list(obs["market_code"]) == ["SEN_447", "SEN_447"]
    assert list(obs["commodity_code"]) == ["WFP_73", "WFP_73"]
    assert obs["is_food_security_basket"].all()
    assert list(obs["line_number"]) == [2, 3]


def test_wfp_hxl_row_is_skipped(tmp_path: Path) -> None:
    hxl = dict.fromkeys(WFP_HEADER, "#tag") | {"date": "#date"}
    path = write_wfp_csv(tmp_path / "w.csv", [hxl, wfp_row(2024, 1)])
    result = parse_wfp_csv(path, "SEN", "wfp_SEN")
    assert result.rows_read == 1
    assert result.observations["line_number"].tolist() == [3]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"price": -5}, "NON_POSITIVE_PRICE"),
        ({"price": 0}, "NON_POSITIVE_PRICE"),
        ({"price": "n/a"}, "INVALID_PRICE"),
        ({"date": "2024-13-45"}, "INVALID_DATE"),
        ({"latitude": "123"}, "INVALID_GPS"),
        ({"unit": "Bag"}, "UNKNOWN_UNIT"),
        ({"priceflag": "forecast"}, "UNKNOWN_PRICEFLAG"),
    ],
)
def test_wfp_invalid_rows_are_quarantined(tmp_path: Path, overrides: dict, reason: str) -> None:
    path = write_wfp_csv(tmp_path / "w.csv", [wfp_row(2024, 1), wfp_row(2024, 2, **overrides)])
    result = parse_wfp_csv(path, "SEN", "wfp_SEN")
    assert len(result.observations) == 1
    assert result.rejects["reason_code"].tolist() == [reason]
    assert result.rejects["line_number"].tolist() == [3]
    assert json.loads(result.rejects["raw_payload_json"].iloc[0])["market"] == "Tilene"


def test_wfp_missing_column_is_blocking(tmp_path: Path) -> None:
    header = [c for c in WFP_HEADER if c != "priceflag"]
    path = write_wfp_csv(tmp_path / "w.csv", [wfp_row(2024, 1)], header=header)
    with pytest.raises(SourceSchemaError, match="priceflag"):
        parse_wfp_csv(path, "SEN", "wfp_SEN")


def test_faostat_cpi_flags_map_to_observed_or_not(tmp_path: Path) -> None:
    years = range(2006, 2008)
    rows = cpi_rows(23013, 6125, range(2006, 2007), flag="I")
    rows = [r | {"Y2007": "", "Y2007F": ""} for r in rows]  # 2007 missing
    rows += cpi_rows(23014, 6121, years, flag="E", value=-2010)  # negative inflation allowed
    rows += cpi_rows(99999, 6125, years)  # not a registered CPI series: ignored
    zip_path = write_faostat_zip(
        tmp_path / "c.zip", "ConsumerPriceIndices_E_Africa.csv", rows, years
    )
    result = parse_faostat_zip(zip_path, "cpi", "faostat_cpi")
    obs = result.observations
    assert result.rejects.empty
    by_code = obs.groupby("commodity_code")["source_flag"].agg(set).to_dict()
    assert by_code == {"FAO_CPI_23013": {"fao_imputed"}, "FAO_CPI_23014": {"fao_estimated"}}
    assert (obs[obs["commodity_code"] == "FAO_CPI_23014"]["raw_value"] < 0).all()
    assert len(obs[obs["commodity_code"] == "FAO_CPI_23013"]) == 12  # 2007 empty: not invented
    assert obs["is_food_security_basket"].tolist().count(True) == 12


def test_faostat_producer_prices_keep_local_currency_only(tmp_path: Path) -> None:
    years = range(2020, 2022)
    rows = [
        producer_row(15, 5530, years),
        producer_row(15, 5532, years),
        producer_row(15, 5539, years),
    ]
    rows.append(producer_row(16, 5530, years, flag="Z"))
    zip_path = write_faostat_zip(tmp_path / "p.zip", "Prices_E_Africa.csv", rows, years)
    result = parse_faostat_zip(zip_path, "prices", "faostat_prices")
    obs = result.observations
    assert set(obs["currency_code"]) == {"MAD", "NONE"}  # USD element 5532 not loaded
    assert set(obs["frequency"]) == {"ANNUAL"}
    assert obs["reference_month"].isna().all()  # never an invented month
    assert result.rejects["reason_code"].tolist() == ["UNKNOWN_FAO_FLAG"] * 2


def test_faostat_corrupted_zip_is_blocking(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(Exception, match="zip"):
        parse_faostat_zip(bad, "cpi", "faostat_cpi")
