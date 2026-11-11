---
name: AgriPrix Observatory
description: Staple food prices of the Sahel and Morocco, read against the farming calendar.
colors:
  ink: "#1E2B24"
  muted: "#5B6660"
  note: "#4E5A53"
  surface: "#FFFFFF"
  surface-soft: "#F1F4F1"
  border: "#D6DDD8"
  grid: "#E6EBE7"
  rail: "#24453A"
  rail-soft: "#2F5649"
  rail-border: "#3E6658"
  rail-note: "#D8E3DD"
  straw: "#E9C46A"
  forecast: "#2A6F97"
  link: "#1F5A7A"
  alert-up: "#B3261E"
  alert-down: "#4A5568"
typography:
  body:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  heading-1:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
  heading-2:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 650
  heading-3:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
  note:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 400
rounded:
  base: "6px"
  tag: "4px"
components:
  sidebar:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.surface}"
  sidebar-input:
    backgroundColor: "{colors.rail-soft}"
    textColor: "{colors.surface}"
    rounded: "{rounded.base}"
  season-tag:
    backgroundColor: "{colors.straw}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tag}"
---

# Design System: AgriPrix Observatory

> Documented from the built dashboard (src/dashboard/, theme in src/dashboard/.streamlit/config.toml) on 2026-11-11. Direction contract: .impeccable/surfaces/dashboard.md.

## Overview

"Calendrier des saisons": an Operate surface where every price is read against the Sahel farming calendar. The shell is a standard Streamlit layout (filter rail, tabs, data tables); the world contributes only its palette, one typeface and one signature move, the lean-season band (soudure, June–September) drawn on every time chart.

## Colors

### Primary
- **Rainy-season green** `#24453A`: the filter rail and primary selection in the main area.
- **Millet straw** `#E9C46A`: the lean-season band (28 % opacity on charts), selection inside the rail, text selection.

### Secondary
- **Forecast blue** `#2A6F97`: forecasts (dashed line, markers) and their 80 % fan (16 % opacity), focus ring.

### Neutral
- Ink `#1E2B24` on white `#FFFFFF`; notes `#4E5A53`; axis titles `#5B6660`; borders `#D6DDD8`; grid `#E6EBE7`; rail notes `#D8E3DD` on the green.

### Named Rules
- **State colours carry meaning only**: red `#B3261E` = abnormal rise, slate `#4A5568` = abnormal fall, always paired with a shape (▲ / ▼) and words ("Hausse", "Baisse").

## Typography

Public Sans (OFL, self-hosted in src/dashboard/static/fonts) for everything: one family, tight scale (1.75 / 1.375 / 1.125 rem), weights 700 / 650 / 600 for headings. Tabular numerals in every data table. Notes are capped at 75 characters per line.

## Layout

Wide layout: green filter rail on the left (collapses on mobile), three tabs ("Situation", "Prévisions par marché", "Méthode & qualité"). The first tab opens on the alerts of the last three months, then the selected market's chart, then its forecast table. On narrow screens tables scroll inside their frame, with the deviation column placed right after the market name.

## Elevation & Depth

Flat: depth comes from the green rail against the white work area; no shadows, no cards.

## Shapes

Base radius 6 px on inputs and tables; 4 px on the season tag.

## Components

### Navigation
Streamlit tabs and select boxes, unmodified affordances.

### Season chart (signature)
Plotly chart: observed prices as a 2 px ink line; aggregated or estimated values as hollow grey circles labelled "non mesurée"; alerts as ▲ / ▼ markers with a white outline; forecast as a dashed blue line from the last observed price with its 80 % fan; a dotted vertical line at the forecast origin; straw lean-season bands behind everything; explicit date axis; French separators (1 464,5).

### Tables
Streamlit dataframes; prices rounded to whole XOF (one decimal for indices), deviations signed in percent.

## Do's and Don'ts

### Do:
- Draw the lean season on every time chart of a Sahel series.
- State the date and source of the data next to it, and the measured reliability next to every forecast.
- Compute every explanatory sentence from the numbers it describes.

### Don't:
- Use colour alone for a state, or a red/green pair.
- Add KPI tiles, cards, gradients or decorative motion.
- Write a claim the API cannot back (no invented users, partners or accuracy figures).
