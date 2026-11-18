"""Colour tokens of the AgriPrix charter: the ONE place colours are defined in code.

DESIGN.md mirrors this file; .streamlit/config.toml repeats the theme colours (TOML cannot
import Python) and tests/unit/test_tokens.py fails if the two drift apart or if a token
falls below its WCAG AA contrast threshold.

Brand colours were measured on the logo (k-means on its pixels, see
docs/design/logo/palette-mesuree.json, scripts/build_logo_assets.py), not guessed.
"""

from __future__ import annotations

import math

# --- Measured on the logo (k-means centres) -------------------------------------------
LOGO = {
    "navy": "#21254A",  # iris, dark blue
    "teal_deep": "#1E5066",  # iris, deep blue-green
    "teal_light": "#529492",  # iris, light blue-green rings
    "rust": "#A53F12",  # eyelids
    "ochre": "#DA9435",  # wheat ears
    "leaf": "#69913B",  # leaves and forecast line
    "orange": "#E68638",  # orange family: forecast point and orange ears (pixel median)
}

# --- Roles ------------------------------------------------------------------------------
INK = "#21254A"  # text, observed price line: logo navy
TEXT_MUTED = "#4F536B"  # notes, secondary text: navy-tinted grey
AXIS = "#5D6175"  # chart axes and legends
BG = "#FFFFFF"
BG_SOFT = "#F6F4EE"  # filter bar, light cream
BORDER = "#D9D6CC"
GRID = "#ECEAE3"
SELECT = "#3F6A1F"  # selection, active pill and tab: dark leaf green (logo leaf, darkened)
SELECT_TEXT = "#FFFFFF"
FORECAST = "#1E5066"  # forecast line: logo deep blue-green
FORECAST_FAN = "rgba(82, 148, 146, 0.22)"  # 80 % interval: logo light blue-green
LINK = "#1E5066"
SEASON = "#DA9435"  # lean season band: logo ochre, drawn at SEASON_OPACITY
SEASON_OPACITY = 0.22
SEASON_TAG_BG = "#F6E2BC"  # "soudure" tag background (ochre tint), text in INK
BRAND = "#97570D"  # brand accent (header rule, details). Never an alert.
# The logo rust #A53F12 is only CIEDE2000 8.6 from ALERT_UP: too close. #97570D is the colour
# nearest to it with dE2000 >= 20 from ALERT_UP and 4.5:1 on white (exhaustive search).
ALERT_UP = "#B3261E"  # abnormal rise: always with ▲ and the word "Hausse"
ALERT_DOWN = "#4A5568"  # abnormal fall: always with ▼ and the word "Baisse"
NORMAL = "#6B7085"  # normal market: white disc with this outline
MIN_BRAND_ALERT_DE = 20.0

# Contrast thresholds (WCAG 2.1 AA): text 4.5:1, graphical objects 3:1.
TEXT_TOKENS = {"INK": INK, "TEXT_MUTED": TEXT_MUTED, "LINK": LINK, "AXIS": AXIS,
               "ALERT_UP": ALERT_UP, "ALERT_DOWN": ALERT_DOWN, "SELECT": SELECT}  # fmt: skip
GRAPHIC_TOKENS = {"FORECAST": FORECAST, "BRAND": BRAND, "NORMAL": NORMAL}


def _rgb(hex_code: str) -> tuple[float, float, float]:
    h = hex_code.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(hex_code: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_code))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _lab(hex_code: str) -> tuple[float, float, float]:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_code))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e2000(c1: str, c2: str) -> float:
    """CIEDE2000 colour difference (the perceptual standard; CIE76 overstates it)."""
    l1, a1, b1 = _lab(c1)
    l2, a2, b2 = _lab(c2)
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dlp, dcp = l2 - l1, c2p - c1p
    dh = h2p - h1p
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dhp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lbp, cbp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) > 180:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    else:
        hbp = (h1p + h2p) / 2
    t = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))  # fmt: skip
    sl = 1 + 0.015 * (lbp - 50) ** 2 / math.sqrt(20 + (lbp - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = (
        -2
        * math.sqrt(cbp**7 / (cbp**7 + 25**7))
        * math.sin(math.radians(60 * math.exp(-(((hbp - 275) / 25) ** 2))))
    )
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp / sh) ** 2
                     + rt * (dcp / sc) * (dhp / sh))  # fmt: skip
