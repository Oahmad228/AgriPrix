"""Real market map (Plotly Scattermap on OpenStreetMap tiles, MapLibre, no API key).

Positions are only the coordinates published by WFP; markets without coordinates are left
out and counted by the caller. Borders: geoBoundaries files in ./geo (see geo/SOURCES.md).
A state is carried by colour, symbol and word together (DESIGN.md).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import plotly.graph_objects as go

GEO_DIR = Path(__file__).parent / "geo"
INK, ALERT_UP, ALERT_DOWN, NORMAL = "#1E2B24", "#B3261E", "#4A5568", "#5B6660"
STATES = {
    # state: (legend words, symbol in labels, colour, marker size)
    "UP": ("▲ Hausse anormale", "▲", ALERT_UP, 15),
    "DOWN": ("▼ Baisse anormale", "▼", ALERT_DOWN, 15),
    "NORMAL": ("● Prix dans la normale", "●", NORMAL, 9),
}
ATTRIBUTION = (
    "Fond de carte © contributeurs OpenStreetMap · frontières geoBoundaries (CC BY / CC BY-SA, "
    "selon le pays) · positions des marchés : WFP"
)


@lru_cache(maxsize=16)
def borders(iso3: str) -> list[dict]:
    """Country outline, plus regions for Burkina Faso, as line layers (empty if no file)."""
    layers = []
    for level, width, color in (("ADM1", 0.8, "#8A968F"), ("ADM0", 2.0, INK)):
        path = GEO_DIR / f"{iso3}-{level}.geojson"
        if path.exists():
            layers.append(
                {
                    "source": json.loads(path.read_text(encoding="utf-8")),
                    "type": "line",
                    "color": color,
                    "line": {"width": width},
                    "below": "traces",
                }
            )
    return layers


def view(points: list[dict]) -> tuple[dict, float]:
    """Centre and zoom that fit every plotted market."""
    lats = [p["latitude"] for p in points]
    lons = [p["longitude"] for p in points]
    center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
    extent = max(max(lats) - min(lats), max(lons) - min(lons), 1.0)
    return center, round(max(3.0, min(9.0, math.log2(360 / (extent * 1.8)))), 2)


def market_map(points: list[dict], iso3: str, height: int = 460) -> go.Figure:
    """points: dicts with series_id, latitude, longitude, state (UP/DOWN/NORMAL), label, hover."""
    fig = go.Figure()
    for state, (words, _symbol, color, size) in STATES.items():
        subset = [p for p in points if p["state"] == state]
        if not subset:
            continue
        fig.add_trace(
            go.Scattermap(
                lat=[p["latitude"] for p in subset],
                lon=[p["longitude"] for p in subset],
                mode="markers+text" if state != "NORMAL" else "markers",
                marker={"size": size, "color": color, "opacity": 0.95},
                text=[p["label"] for p in subset],
                textposition="top right",
                # MapLibre's map fonts have no ▲/▼ glyphs: the map label carries the word
                # ("hausse"/"baisse") and the sign; the legend, list and hover carry the symbol.
                textfont={"size": 13, "color": color, "family": "Open Sans Bold"},
                customdata=[[p["series_id"]] for p in subset],
                hovertext=[p["hover"] for p in subset],
                hovertemplate="%{hovertext}<extra></extra>",
                name=words,
            )
        )
    center, zoom = view(points) if points else ({"lat": 14.0, "lon": -2.0}, 4.0)
    fig.update_layout(
        map={"style": "open-street-map", "center": center, "zoom": zoom, "layers": borders(iso3)},
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        legend={
            "orientation": "v", "yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01,
            "bgcolor": "rgba(255,255,255,0.92)", "bordercolor": "#D6DDD8", "borderwidth": 1,
            "font": {"family": "Public Sans, system-ui, sans-serif", "size": 13, "color": INK},
        },
        hoverlabel={"bgcolor": "white", "bordercolor": "#D6DDD8",
                    "font": {"family": "Public Sans, system-ui, sans-serif", "size": 13, "color": INK}},
        font={"family": "Public Sans, system-ui, sans-serif"},
        clickmode="event+select",
        dragmode="pan",
    )  # fmt: skip
    return fig
