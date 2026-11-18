"""Charts of the "Calendrier des saisons" direction.

Signature: every time chart carries the Sahel lean season (soudure) as a millet-straw band,
so a price is always read against the farming calendar. Alerts use shape AND colour
(▲ red up, ▼ slate down); forecasts are dashed with their 80 % interval as a pale fan.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go

from src.dashboard import tokens as tk  # noqa: E402

INK = tk.INK
MUTED = tk.AXIS
GRID = tk.GRID
STRAW = tk.SEASON
FORECAST = tk.FORECAST
ALERT_UP = tk.ALERT_UP
ALERT_DOWN = tk.ALERT_DOWN
FONT = "Public Sans, system-ui, sans-serif"
MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]  # fmt: skip


def lean_months(spec: str | None) -> list[int]:
    return sorted(int(m) for m in spec.split(",")) if spec else []


def in_lean_season(period: date, spec: str | None) -> bool:
    return period.month in lean_months(spec)


def unit_label(unit: str, currency: str) -> str:
    if currency == "NONE":
        return "indice (base 2015 = 100)" if unit.startswith("INDEX_2015") else unit
    return f"{currency}/{'kg' if unit == 'KG' else unit}"


def fmt_value(value: float, unit: str, currency: str) -> str:
    if currency == "NONE":
        return f"{value:,.1f}".replace(",", " ").replace(".", ",")
    return f"{value:,.0f}".replace(",", " ") + f" {unit_label(unit, currency)}"


def month_label(period: date) -> str:
    return f"{MONTHS_FR[period.month - 1]} {period.year}"


def _season_bands(
    fig: go.Figure, start: pd.Timestamp, end: pd.Timestamp, months: list[int], c: dict
) -> None:
    if not months:
        return
    first, last = min(months), max(months)
    for year in range(start.year, end.year + 1):
        x0 = pd.Timestamp(year, first, 1)
        x1 = pd.Timestamp(year, last, 1) + pd.offsets.MonthEnd(1)
        if x1 < start or x0 > end:
            continue
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=c["SEASON"],
            opacity=c["SEASON_OPACITY"],
            line_width=0,
            layer="below",
        )
    # Legend entry for the bands (vrects have none of their own).
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None], mode="markers", name="Période de soudure",
            marker={"symbol": "square", "size": 12, "color": c["SEASON"], "opacity": 0.6},
        )
    )  # fmt: skip


def _date_ticks(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Fixed tick spacing: Plotly's automatic ticks kept a single year on narrow screens."""
    span_years = (end - start).days / 365.25
    if span_years <= 2:
        # Explicit French labels: Plotly's French locale is not loaded inside Streamlit.
        ticks = pd.date_range(pd.Timestamp(start.year, 1, 1), end, freq="QS")
        ticks = ticks[ticks >= start]
        return {
            "tickmode": "array",
            "tickvals": list(ticks),
            "ticktext": [f"{MONTHS_FR[t.month - 1]}<br>{t.year}" for t in ticks],
        }
    step = 1 if span_years <= 8 else 2 if span_years <= 16 else 4
    return {"dtick": f"M{12 * step}", "tick0": f"{start.year}-01-01", "tickformat": "%Y"}


def price_figure(
    observations: list[dict],
    alerts: list[dict],
    forecasts: list[dict],
    unit: str,
    currency: str,
    lean_spec: str | None,
    years: int | None = 5,
    theme: str | None = None,
) -> go.Figure:
    """years: 1, 5 or None (whole history). Every year (or quarter on one year) is labelled.

    theme: "light" or "dark" (colours from tokens.palette)."""
    c = tk.palette(theme)
    obs = pd.DataFrame(observations)
    obs["period"] = pd.to_datetime(obs["period"])
    measured = obs[obs["is_observed"]]
    other = obs[~obs["is_observed"]]
    label = unit_label(unit, currency)

    end = obs["period"].max()
    if forecasts:
        end = max(end, pd.to_datetime(max(f["target_period"] for f in forecasts)))
    first = obs["period"].min()
    start = first if years is None else max(first, obs["period"].max() - pd.DateOffset(years=years))

    fig = go.Figure()
    _season_bands(fig, start, end, lean_months(lean_spec), c)
    fig.add_trace(
        go.Scatter(
            x=measured["period"], y=measured["value"], mode="lines", name="Prix relevé",
            line={"color": c["INK"], "width": 2},
            hovertemplate="%{x|%b %Y} : %{y:,.0f} " + label + "<extra></extra>",
        )
    )  # fmt: skip
    if not other.empty:
        fig.add_trace(
            go.Scatter(
                x=other["period"], y=other["value"], mode="markers",
                name="Valeur agrégée ou estimée (non utilisée par les modèles)",
                marker={"symbol": "circle-open", "size": 6, "color": c["AXIS"]},
                hovertemplate="%{x|%b %Y} : %{y:,.0f} " + label + " (non mesurée)<extra></extra>",
            )
        )  # fmt: skip
    for direction, symbol, colour, name in (
        ("UP", "triangle-up", c["ALERT_UP"], "Alerte : hausse anormale"),
        ("DOWN", "triangle-down", c["ALERT_DOWN"], "Alerte : baisse anormale"),
    ):
        points = [a for a in alerts if a["direction"] == direction]
        if points:
            fig.add_trace(
                go.Scatter(
                    x=pd.to_datetime([a["period"] for a in points]),
                    y=[a["observed_value"] for a in points],
                    mode="markers", name=name,
                    marker={"symbol": symbol, "size": 12, "color": colour,
                            "line": {"color": c["BG"], "width": 1.5}},
                    customdata=[[a["deviation_pct"], a["severity"]] for a in points],
                    hovertemplate="%{x|%b %Y} : %{y:,.0f} " + label
                    + "<br>%{customdata[0]:+.0f} % par rapport au niveau attendu<extra></extra>",
                )
            )  # fmt: skip
    if forecasts:
        fc = pd.DataFrame(sorted(forecasts, key=lambda f: f["horizon_months"]))
        origin = pd.to_datetime(fc["origin_period"].iloc[0])
        anchor = measured.loc[measured["period"] == origin, "value"]
        x = pd.to_datetime(fc["target_period"])
        if not anchor.empty:
            x = pd.concat([pd.Series([origin]), x], ignore_index=True)
            point = [float(anchor.iloc[0]), *fc["yhat"]]
            low = [float(anchor.iloc[0]), *fc["lower_80"]]
            high = [float(anchor.iloc[0]), *fc["upper_80"]]
        else:
            point, low, high = list(fc["yhat"]), list(fc["lower_80"]), list(fc["upper_80"])
        fig.add_trace(
            go.Scatter(
                x=x, y=high, mode="lines", line={"width": 0}, hoverinfo="skip", showlegend=False
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x, y=low, mode="lines", line={"width": 0}, fill="tonexty",
                fillcolor=c["FORECAST_FAN"], name="Intervalle à 80 %", hoverinfo="skip",
            )
        )  # fmt: skip
        fig.add_trace(
            go.Scatter(
                x=x, y=point, mode="lines+markers", name="Prévision (1, 3 et 6 mois)",
                line={"color": c["FORECAST"], "width": 2, "dash": "dash"},
                marker={"size": 7, "color": c["FORECAST"]},
                hovertemplate="%{x|%b %Y} : %{y:,.0f} " + label + " (prévision)<extra></extra>",
            )
        )  # fmt: skip
        fig.add_vline(x=origin, line={"color": c["AXIS"], "width": 1, "dash": "dot"})

    ticks = _date_ticks(start, end)
    fig.update_layout(
        # The legend (6 entries) wraps onto up to 5 lines on a phone: it sits at the bottom
        # of the figure frame (yref "container") in a reserved margin, never cut off.
        height=500,
        margin={"l": 8, "r": 8, "t": 8, "b": 130},
        paper_bgcolor=c["BG_BLOCK"],
        plot_bgcolor=c["BG_BLOCK"],
        font={"family": FONT, "color": c["INK"], "size": 13},
        separators=", ",
        hovermode="closest",
        hoverlabel={"font": {"family": FONT}},
        legend={"orientation": "h", "yref": "container", "yanchor": "bottom", "y": 0.01,
                "x": 0, "font": {"size": 12}},
        # Explicit date axis: the legend-only trace of the season bands has no x data, and
        # Plotly would otherwise infer a numeric axis from it and hide every price.
        xaxis={"type": "date", "range": [start, end + pd.DateOffset(days=20)], "showgrid": False,
               "linecolor": c["GRID"], **ticks},
        yaxis={"title": {"text": label, "font": {"size": 12, "color": c["AXIS"]}},
               "gridcolor": c["GRID"], "zeroline": False, "tickformat": ",.0f"},
    )  # fmt: skip
    return fig


def gain_figure(rows: list[dict], theme: str | None = None) -> go.Figure:
    """Gain of each model vs persistence per horizon (positive = better than 'last price')."""
    c = tk.palette(theme)
    frame = pd.DataFrame(rows)
    # Only the learned models: "same month last year" is far worse at short horizons and would
    # crush the scale (its figures stay in the table below the chart).
    frame = frame[frame["model_name"].isin(["LightGBM_Global", "Ridge_Seasonal"])]
    names = {"LightGBM_Global": "Modèle appris sur tous les marchés (LightGBM)",
             "Ridge_Seasonal": "Tendance et saison par marché (Ridge)",
             "SeasonalNaive": "Même mois l'an passé"}  # fmt: skip
    colours = {
        "LightGBM_Global": c["FORECAST"],
        "Ridge_Seasonal": c["TAB_ACTIVE_BG"] or c["BRAND"],
        "SeasonalNaive": c["AXIS"],
    }
    fig = go.Figure()
    for model, block in frame.groupby("model_name"):
        fig.add_trace(
            go.Bar(
                x=[f"{h} mois" for h in block["horizon_months"]], y=block["gain_vs_naive_pct"],
                name=names.get(model, model), marker_color=colours.get(model, c["INK"]),
                text=[f"{v:+.0f} %" for v in block["gain_vs_naive_pct"]], textposition="outside",
                hovertemplate="%{x} : %{y:+.1f} %<extra>" + names.get(model, model) + "</extra>",
            )
        )  # fmt: skip
    fig.add_hline(y=0, line={"color": c["INK"], "width": 1})
    fig.update_layout(
        barmode="group", height=380, margin={"l": 8, "r": 8, "t": 8, "b": 90},
        paper_bgcolor=c["BG_BLOCK"], plot_bgcolor=c["BG_BLOCK"], separators=", ",
        font={"family": FONT, "color": c["INK"], "size": 13},
        legend={"orientation": "h", "yref": "container", "yanchor": "bottom", "y": 0.01, "x": 0},
        yaxis={"title": {"text": "écart d'erreur vs « dernier prix connu » (%)", "font": {"size": 12}},
               "gridcolor": c["GRID"], "zeroline": False},
    )  # fmt: skip
    return fig
