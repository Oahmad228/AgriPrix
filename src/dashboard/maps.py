"""Real market map (Plotly Scattermap on OpenStreetMap tiles, MapLibre, no API key).

Positions are only the coordinates published by WFP; markets without coordinates are left
out and counted by the caller. Borders: geoBoundaries files in ./geo (see geo/SOURCES.md).
Every covered country is a clickable outline: a click on a country selects it.
A market state is carried by colour, symbol and word together (DESIGN.md).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import plotly.graph_objects as go

from src.dashboard import tokens as tk

GEO_DIR = Path(__file__).parent / "geo"
INK, ALERT_UP, ALERT_DOWN, NORMAL = tk.INK, tk.ALERT_UP, tk.ALERT_DOWN, tk.NORMAL
FONT = "Public Sans, system-ui, sans-serif"
STATES = {
    # state: (legend words, symbol in labels, colour, marker size)
    "UP": ("▲ Hausse anormale", "▲", ALERT_UP, 16),
    "DOWN": ("▼ Baisse anormale", "▼", ALERT_DOWN, 16),
    "NORMAL": ("○ Prix dans la normale", "○", NORMAL, 10),
}
ATTRIBUTION = (
    "Fond de carte © contributeurs OpenStreetMap · frontières geoBoundaries (CC BY, CC BY-SA "
    "ou ODbL selon le pays) · positions des marchés : WFP"
)
NATIONAL_ONLY = {"MAR": "Indice national des prix alimentaires"}
# The mouse wheel scrolls the page (it would otherwise be trapped by the map): zoom with the
# + / - buttons or a pinch on a touch screen; pan by dragging.
CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "locale": "fr",
    "modeBarButtons": [["zoomInMap", "zoomOutMap", "resetViewMap"]],
}


@lru_cache(maxsize=16)
def _geojson(iso3: str, level: str) -> dict | None:
    path = GEO_DIR / f"{iso3}-{level}.geojson"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _coordinates(geometry: dict) -> list[tuple[float, float]]:
    rings = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        rings = [rings]
    return [tuple(pt) for polygon in rings for ring in polygon for pt in ring]


@lru_cache(maxsize=16)
def bounds(iso3: str) -> tuple[float, float, float, float] | None:
    """(min lon, min lat, max lon, max lat) of the country outline."""
    geo = _geojson(iso3, "ADM0")
    if not geo:
        return None
    pts = [pt for f in geo["features"] for pt in _coordinates(f["geometry"])]
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def borders(iso3: str | None) -> list[dict]:
    """Line layers: regions (Burkina Faso) and the outline of the selected country."""
    layers: list[dict] = []
    if iso3 is None:
        return layers
    for level, width, color in (("ADM1", 0.8, "#8A8C9C"), ("ADM0", 2.2, INK)):
        geo = _geojson(iso3, level)
        if geo:
            layers.append({"source": geo, "type": "line", "color": color,
                           "line": {"width": width}, "below": "traces"})  # fmt: skip
    return layers


def view(countries: list[str], points: list[dict]) -> tuple[dict, float]:
    """Centre and zoom that fit the countries' outlines (or the markets if no outline)."""
    boxes = [b for b in (bounds(c) for c in countries) if b]
    if boxes:
        lon0, lat0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        lon1, lat1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    elif points:
        lats = [p["latitude"] for p in points]
        lons = [p["longitude"] for p in points]
        lon0, lat0, lon1, lat1 = min(lons), min(lats), max(lons), max(lats)
    else:
        return {"lat": 14.0, "lon": -2.0}, 3.0
    boxes = boxes or [(lon0, lat0, lon1, lat1)]
    extent = max(lat1 - lat0, lon1 - lon0, 1.0)
    # One country: a wide margin so it fits a phone-width map too; several: tighter.
    margin = 2.0 if len(boxes) <= 1 else 1.25
    zoom = round(max(2.0, min(9.0, math.log2(360 / (extent * margin)))), 2)
    return {"lat": (lat0 + lat1) / 2, "lon": (lon0 + lon1) / 2}, zoom


def _country_trace(countries: dict[str, str], selected: str | None) -> go.Choroplethmap | None:
    """All covered countries as clickable areas: the selected one clear, the others tinted."""
    features, ids, names, fills = [], [], [], []
    for iso3, name in countries.items():
        geo = _geojson(iso3, "ADM0")
        if not geo:
            continue
        for feature in geo["features"]:
            features.append({**feature, "id": iso3})
        ids.append(iso3)
        label = NATIONAL_ONLY.get(iso3)
        extra = f"<br>{label}" if label else ""
        names.append(f"<b>{name}</b>{extra}<br><i>Cliquer pour choisir ce pays</i>")
        fills.append(0 if iso3 == selected else (2 if iso3 in NATIONAL_ONLY else 1))
    if not ids:
        return None
    return go.Choroplethmap(
        geojson={"type": "FeatureCollection", "features": features},
        locations=ids, z=fills, zmin=0, zmax=2,
        colorscale=[[0, "rgba(255,255,255,0)"], [0.5, "rgba(246,244,238,0.55)"],
                    [1, "rgba(218,148,53,0.30)"]],
        showscale=False, marker={"line": {"width": 1.2, "color": "#8A8C9C"}},
        hovertext=names, hovertemplate="%{hovertext}<extra></extra>",
        name="Pays", showlegend=False,
    )  # fmt: skip


def market_map(
    points: list[dict],
    selected: str | None,
    countries: dict[str, str] | None = None,
    height: int = 480,
) -> go.Figure:
    """points: dicts with series_id, latitude, longitude, state (UP/DOWN/NORMAL), label, hover.

    selected: ISO3 of the chosen country, None for every covered country ("Tous").
    countries: {ISO3: French name} of the covered countries (clickable outlines).
    """
    countries = countries or {}
    fig = go.Figure()
    area = _country_trace(countries, selected)
    if area is not None:
        fig.add_trace(area)
    for iso3, label in NATIONAL_ONLY.items():
        box = bounds(iso3)
        if box and iso3 in countries and selected in (None, iso3):
            fig.add_trace(go.Scattermap(
                # In the northern third of the outline, where the cities and the index are.
                lat=[box[3] - 0.3 * (box[3] - box[1])], lon=[box[2] - 0.4 * (box[2] - box[0])],
                mode="text", text=[label], textfont={"size": 12, "color": INK},
                hoverinfo="skip", showlegend=False,
            ))  # fmt: skip
    for state, (words, _symbol, color, size) in STATES.items():
        subset = [p for p in points if p["state"] == state]
        if not subset:
            continue
        lat = [p["latitude"] for p in subset]
        lon = [p["longitude"] for p in subset]
        common = {
            "customdata": [[p["series_id"]] for p in subset],
            "hovertext": [p["hover"] for p in subset],
            "hovertemplate": "%{hovertext}<extra></extra>",
        }
        if state == "NORMAL":
            # Scattermap markers have no outline: a grey disc under a white one draws
            # "a white circle with a grey edge" (DESIGN.md).
            fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="markers", name=words,
                                        marker={"size": size, "color": color}, **common))  # fmt: skip
            fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="markers", showlegend=False,
                                        marker={"size": size - 4, "color": "#FFFFFF"}, **common))  # fmt: skip
        else:
            fig.add_trace(go.Scattermap(
                lat=lat, lon=lon, mode="markers+text", name=words,
                marker={"size": size, "color": color, "opacity": 0.95},
                text=[p["label"] for p in subset], textposition="top right",
                # MapLibre's map fonts have no ▲/▼ glyphs: the map label carries the word
                # ("hausse"/"baisse") and the sign; the legend, list and hover carry the symbol.
                textfont={"size": 13, "color": color, "family": "Open Sans Bold"},
                **common,
            ))  # fmt: skip
    center, zoom = view([selected] if selected else list(countries), points)
    fig.update_layout(
        map={"style": "open-street-map", "center": center, "zoom": zoom,
             "layers": borders(selected)},
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        legend={
            "orientation": "v", "yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01,
            "bgcolor": "rgba(255,255,255,0.94)", "bordercolor": tk.BORDER, "borderwidth": 1,
            "font": {"family": FONT, "size": 13, "color": INK},
        },
        hoverlabel={"bgcolor": "white", "bordercolor": tk.BORDER,
                    "font": {"family": FONT, "size": 13, "color": INK}},
        font={"family": FONT},
        clickmode="event+select",
        dragmode="pan",
    )  # fmt: skip
    return fig


def clicked(points: list[dict]) -> tuple[str, str | int] | None:
    """Read a map click: ("market", series_id) or ("country", ISO3), else None.

    A click on a marker also hits the country area under it: the market wins.
    """
    for point in points:
        data = point.get("customdata")
        if data and not isinstance(point.get("location"), str):
            return "market", int(data[0] if isinstance(data, list) else data)
    for point in points:
        location = point.get("location")
        if isinstance(location, str) and len(location) == 3:
            return "country", location
    return None
