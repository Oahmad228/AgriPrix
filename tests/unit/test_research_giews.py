"""GIEWS brief parsing: dates, harvest bullets, one proposed row per brief, trade measures."""

from src.research.giews import (
    Brief,
    classify_bullet,
    consolidate,
    event_rows,
    harvest_rows,
    parse_reference_date,
    split_briefs,
)


def test_reference_date_tolerates_typos_in_the_month() -> None:
    assert parse_reference_date("05-December-2024") == "2024-12-05"
    assert parse_reference_date("09-Sepetmber-2010") == "2010-09-09"  # real typo in the archive


def test_split_briefs_keeps_date_and_start_page() -> None:
    pages = [
        "Reference Date: 05-December-2024 first brief",
        "more text",
        "Reference Date: 21-February-2024 second",
    ]
    briefs = split_briefs(pages, "BFA", "url")
    assert [(b.reference_date, b.page) for b in briefs] == [("2024-12-05", 1), ("2024-02-21", 3)]
    assert "more text" in briefs[0].text


def test_classify_bullet_directions_and_references() -> None:
    assert classify_bullet("Cereal production in 2024 estimated at above-average level") == (
        "estimate", "1", "5y_avg",
    )  # fmt: skip
    assert classify_bullet("Below-average cereal production expected in 2022") == (
        "forecast",
        "-1",
        "5y_avg",
    )
    assert classify_bullet("Cereal output in 2025 estimated at near-average level") == (
        "estimate",
        "0",
        "5y_avg",
    )
    assert classify_bullet("Cereal production is estimated to decline by 20 percent in 2011") == (
        "estimate", "-1", "prev_year",
    )  # fmt: skip
    assert classify_bullet("A record crop was gathered in 2012") == ("estimate", "1", "record")
    assert (
        classify_bullet("Prices of coarse grains below year-earlier levels") is None
    )  # prices, not harvest


def test_harvest_rows_read_the_snapshot_with_percentages() -> None:
    brief = Brief(
        "SEN",
        "2015-03-09",
        "url",
        4,
        "Reference Date: 09-March-2015 FOOD SECURITY SNAPSHOT • Cereal production estimated to have "
        "dropped 38 percent in 2014 due to insufficient rains • About 927 000 people in need",
    )
    (row,) = harvest_rows(brief)
    assert (row["harvest_year"], row["direction"], row["reference"], row["pct_change"]) == (
        "2014", "-1", "prev_year", "-38",
    )  # fmt: skip
    assert row["validated_by_ahmad"] == "no"


def test_consolidate_prefers_estimates_with_a_direction() -> None:
    base = {"country_iso3": "NER", "reference_date": "2026-01-30"}
    rows = [
        base | {"kind": "prospect", "direction": "", "harvest_year": "2026", "statement": "p"},
        base | {"kind": "forecast", "direction": "1", "harvest_year": "2025", "statement": "f"},
        base | {"kind": "estimate", "direction": "1", "harvest_year": "2025", "statement": "e"},
    ]
    assert [r["statement"] for r in consolidate(rows)] == ["e"]


def test_event_rows_detect_bans_closures_and_sanctions() -> None:
    brief = Brief(
        "NER",
        "2024-01-25",
        "url",
        2,
        "Prices rose. The elevated prices are underpinned by the sanctions imposed by ECOWAS. "
        "An export ban on grains has been in place since 2021. The border with Benin remained closed.",
    )
    assert [r["type"] for r in event_rows(brief)] == ["sanctions", "export_ban", "border_closure"]
