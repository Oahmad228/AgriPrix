"""Monthly rainfall around each market (protocol section 2): mean of the CHIRPS v3 pixels
whose centre lies within 25 km of the market's WFP coordinates.

This step only aggregates raw values per market and month. The publication-lag rule
(month m usable from origin m + 1) and the past-only climatology are applied later, when
features are built for a given origin, so this table can be audited on its own.

    python -m src.research.rain   # writes data/processed/research/rain_market_monthly.csv
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.chirps import RAW_DIR

logger = logging.getLogger("agriprix.research.rain")

EARTH_RADIUS_KM = 6371.0088
RADIUS_KM = 25.0
STUDY_COUNTRIES = ("SEN", "MLI", "BFA", "NER")
OUTPUT = Path("data/processed/research/rain_market_monthly.csv")


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (inputs in degrees, broadcastable arrays)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def pixel_centres(transform, height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    """Latitudes (rows) and longitudes (columns) of pixel centres for a north-up grid."""
    lons = transform.c + transform.a * (np.arange(width) + 0.5)
    lats = transform.f + transform.e * (np.arange(height) + 0.5)
    return lats, lons


def disk_masks(
    lats: np.ndarray, lons: np.ndarray, markets: pd.DataFrame, radius_km: float = RADIUS_KM
) -> dict[str, np.ndarray]:
    """For each market (columns market_code, latitude, longitude), the flat indices of the
    grid pixels whose centre is within ``radius_km``."""
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")
    masks = {}
    for row in markets.itertuples(index=False):
        distance = haversine_km(row.latitude, row.longitude, grid_lat, grid_lon)
        masks[row.market_code] = np.flatnonzero(distance.ravel() <= radius_km)
    return masks


def market_means(values: np.ndarray, masks: dict[str, np.ndarray]) -> dict[str, tuple[float, int]]:
    """Mean rainfall and number of valid pixels per market (NaN pixels ignored)."""
    flat = values.ravel()
    out = {}
    for code, index in masks.items():
        pixels = flat[index]
        valid = pixels[~np.isnan(pixels)]
        out[code] = (float(valid.mean()) if valid.size else float("nan"), int(valid.size))
    return out


def load_markets() -> pd.DataFrame:  # pragma: no cover - needs the warehouse
    from sqlalchemy import create_engine, text

    from src.config import get_settings

    engine = create_engine(get_settings().readonly_database_url)
    query = text(
        "SELECT market_code, country_iso3, latitude::float AS latitude,"
        " longitude::float AS longitude FROM dim_market"
        " WHERE country_iso3 = ANY(:countries) AND granularity_level = 'MARKET'"
        " ORDER BY market_code"
    )
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"countries": list(STUDY_COUNTRIES)})


def build(raw_dir: Path = RAW_DIR, output: Path = OUTPUT) -> pd.DataFrame:  # pragma: no cover
    import rasterio

    markets = load_markets()
    with_coords = markets.dropna(subset=["latitude", "longitude"])
    logger.info("%d markets, %d with coordinates", len(markets), len(with_coords))
    files = sorted(raw_dir.glob("chirps-v3.0.*.tif"))
    if not files:
        raise SystemExit(f"no CHIRPS file in {raw_dir}: run python -m src.research.chirps first")
    with rasterio.open(files[0]) as ref:
        lats, lons = pixel_centres(ref.transform, ref.height, ref.width)
        grid = (ref.transform, ref.height, ref.width)
    masks = disk_masks(lats, lons, with_coords)
    rows = []
    for path in files:
        month = "-".join(path.stem.split(".")[-2:])
        with rasterio.open(path) as src:
            if (src.transform, src.height, src.width) != grid:
                raise ValueError(f"{path.name}: grid differs from {files[0].name}")
            values = src.read(1, masked=True).astype("float64").filled(np.nan)
        values[values < 0] = np.nan  # CHIRPS uses negative nodata values
        for code, (mean, n_pixels) in market_means(values, masks).items():
            rows.append((code, month, mean, n_pixels))
    table = pd.DataFrame(rows, columns=["market_code", "month", "rain_mm", "n_pixels"])
    table = table.merge(markets[["market_code", "country_iso3"]], on="market_code")
    output.parent.mkdir(parents=True, exist_ok=True)
    table.sort_values(["market_code", "month"]).to_csv(output, index=False, float_format="%.3f")
    logger.info("%d rows (%d markets x %d months) written to %s", len(table),
                table.market_code.nunique(), table.month.nunique(), output)  # fmt: skip
    return table


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    argparse.ArgumentParser(description="Rainfall within 25 km of each market").parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
