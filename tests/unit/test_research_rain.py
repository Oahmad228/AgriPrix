"""Research data collection: CHIRPS listing parsing and 25 km market rainfall (no network)."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
from src.research.chirps import parse_listing, read_manifest, write_manifest
from src.research.rain import disk_masks, haversine_km, market_means, pixel_centres

LISTING = """
<tr><td><a href="chirps-v3.0.1981.01.tif">chirps-v3.0.1981.01.tif</a></td><td>5.4 MiB</td><td>2024-Nov-28 10:02</td></tr>
<tr><td><a href="chirps-v3.0.2026.10.tif">chirps-v3.0.2026.10.tif</a></td><td>5.5 MiB</td><td>2026-Nov-13 20:19</td></tr>
<tr><td><a href="pngs/">pngs/</a></td></tr>
"""


def test_parse_listing_keeps_month_and_posting_date() -> None:
    files = parse_listing(LISTING)
    assert [(f.month, f.posted_at) for f in files] == [
        ("1981-01", "2024-11-28T10:02"),
        ("2026-10", "2026-11-13T20:19"),
    ]


def test_manifest_round_trip(tmp_path) -> None:
    rows = {
        "2026-10": {
            "month": "2026-10",
            "file": "chirps-v3.0.2026.10.tif",
            "server_posted_at": "2026-11-13T20:19",
            "downloaded_at_utc": "2026-11-17T22:40",
            "sha256_original": "ab" * 32,
            "bytes": "5767168",
        }
    }
    path = tmp_path / "manifest.csv"
    write_manifest(rows, path)
    assert read_manifest(path) == rows


def test_haversine_one_degree_of_latitude() -> None:
    assert abs(haversine_km(14.0, -17.0, 15.0, -17.0) - 111.2) < 0.2


def test_disk_mask_selects_pixels_within_25_km() -> None:
    # 0.05 degree grid around Dakar-like coordinates (north-up, like CHIRPS).
    transform = SimpleNamespace(a=0.05, c=-18.0, e=-0.05, f=15.5)  # rasterio Affine fields
    lats, lons = pixel_centres(transform, height=40, width=40)
    markets = pd.DataFrame({"market_code": ["M"], "latitude": [14.7], "longitude": [-17.0]})
    index = disk_masks(lats, lons, markets)["M"]
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")
    distances = haversine_km(14.7, -17.0, grid_lat.ravel()[index], grid_lon.ravel()[index])
    assert distances.max() <= 25.0
    # A 25 km disc on a ~5.4 x 5.5 km grid holds roughly pi * 25^2 / 30 ~ 65 pixels.
    assert 55 <= index.size <= 75


def test_market_means_ignore_missing_pixels() -> None:
    values = np.array([[10.0, np.nan], [30.0, 50.0]])
    out = market_means(values, {"A": np.array([0, 1, 2]), "B": np.array([1])})
    assert out["A"] == (20.0, 2)
    assert np.isnan(out["B"][0]) and out["B"][1] == 0
