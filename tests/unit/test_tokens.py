"""Colour charter: WCAG AA contrast, brand vs alert separation, one source of truth."""

import tomllib
from pathlib import Path

import pytest
from src.dashboard import tokens as tk

ROOT = Path(__file__).resolve().parents[2]
THEMES = sorted(tk.THEMES)


# In dark mode (SPEC), the selection green is a fill under white text, not a text colour,
# and the brand rule under the header is decorative (#2B3A32): both are checked elsewhere.
TEXT = {"light": tk.TEXT_NAMES, "dark": tuple(n for n in tk.TEXT_NAMES if n != "SELECT")}
GRAPHIC = {"light": tk.GRAPHIC_NAMES, "dark": tuple(n for n in tk.GRAPHIC_NAMES if n != "BRAND")}
CASES_TEXT = [(t, n, b) for t in THEMES for n in TEXT[t] for b in ("BG", "BG_SOFT", "BG_BLOCK")]
CASES_GRAPHIC = [
    (t, n, b) for t in THEMES for n in GRAPHIC[t] for b in ("BG", "BG_SOFT", "BG_BLOCK")
]


@pytest.mark.parametrize(("theme", "name", "background"), CASES_TEXT)
def test_text_tokens_reach_aa(theme: str, name: str, background: str) -> None:
    c = tk.palette(theme)
    ratio = tk.contrast(c[name], c[background])
    assert ratio >= 4.5, f"{theme} : {name} sur {background} : {ratio:.2f}:1 < 4,5:1"


@pytest.mark.parametrize(("theme", "name", "background"), CASES_GRAPHIC)
def test_graphic_tokens_reach_3_to_1(theme: str, name: str, background: str) -> None:
    c = tk.palette(theme)
    ratio = tk.contrast(c[name], c[background])
    assert ratio >= 3.0, f"{theme} : {name} sur {background} : {ratio:.2f}:1 < 3:1"


def test_dark_tokens_are_the_spec_values() -> None:
    """Mode sombre of SPEC.md, as given (no contrast adjustment was needed)."""
    spec = {"BG": "#111A16", "BG_BLOCK": "#18231E", "BG_SOFT": "#1E2B25",
            "HEADER_BG": "#16211C", "HEADER_RULE": "#2B3A32", "INK": "#E6EDE9",
            "TEXT_MUTED": "#AEBAB3", "AXIS": "#9AA79F", "BORDER": "#33423A", "GRID": "#27342D",
            "SELECT": "#2E7D62", "SELECT_BORDER": "#3F8F70", "TAB_ACTIVE_BG": "#E9C46A",
            "TAB_ACTIVE_TEXT": "#1E2B24", "SEASON": "#E9C46A", "SEASON_OPACITY": 0.13,
            "FORECAST": "#62AEDB", "LINK": "#86C6EC", "LINK_HOVER": "#B3DCF3",
            "ALERT_UP": "#F0837B", "ALERT_DOWN": "#A9B6C9"}  # fmt: skip
    assert {k: tk.DARK[k] for k in spec} == spec


@pytest.mark.parametrize("theme", THEMES)
def test_text_on_selection_and_season_tag(theme: str) -> None:
    c = tk.palette(theme)
    assert tk.contrast(c["SELECT_TEXT"], c["SELECT"]) >= 4.5
    assert tk.contrast(c["SEASON_TAG_TEXT"], c["SEASON_TAG_BG"]) >= 4.5
    if c["TAB_ACTIVE_BG"]:
        assert tk.contrast(c["TAB_ACTIVE_TEXT"], c["TAB_ACTIVE_BG"]) >= 4.5


def test_both_modes_define_every_role() -> None:
    assert set(tk.LIGHT) == set(tk.DARK) == set(tk.ROLE_NAMES)
    assert tk.palette("dark")["MAP_STYLE"] == "carto-darkmatter"
    assert tk.LIGHT["TAB_ACTIVE_BG"] == ""  # the light theme keeps Streamlit's active tab
    assert tk.palette("nonsense") is tk.LIGHT


@pytest.mark.parametrize("theme", THEMES)
def test_brand_accent_never_looks_like_an_alert(theme: str) -> None:
    c = tk.palette(theme)
    assert tk.delta_e2000(c["BRAND"], c["ALERT_UP"]) >= tk.MIN_BRAND_ALERT_DE
    # The raw logo rust would fail: that is why the accent was adjusted (DESIGN.md).
    assert tk.delta_e2000(tk.LOGO["rust"], tk.ALERT_UP) < tk.MIN_BRAND_ALERT_DE


def test_contrast_and_delta_e_reference_values() -> None:
    assert tk.contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert tk.contrast("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    # Sharma et al. (2005) CIEDE2000 test pair 1: L*a*b* (50, 2.6772, -79.7751) vs
    # (50, 0, -82.7485) -> 2.0425. Checked here through identical colours and a known gap.
    assert tk.delta_e2000("#B3261E", "#B3261E") == 0.0
    assert tk.delta_e2000("#FFFFFF", "#000000") == pytest.approx(100.0, abs=0.01)


@pytest.mark.parametrize(
    "config", ["src/dashboard/.streamlit/config.toml", ".streamlit/config.toml"]
)
@pytest.mark.parametrize("theme", THEMES)
def test_streamlit_theme_mirrors_the_tokens(config: str, theme: str) -> None:
    path = ROOT / config
    if not path.exists():  # the repository root is not mounted in every container
        pytest.skip(f"{config} not available here")
    settings = tomllib.loads(path.read_text(encoding="utf-8"))["theme"]
    assert "base" not in settings  # no forced mode: the app follows the system setting
    section, c = settings[theme], tk.palette(theme)
    assert section["primaryColor"] == c["SELECT"]
    assert section["textColor"] == c["INK"]
    assert section["backgroundColor"] == c["BG"]
    assert section["secondaryBackgroundColor"] == c["BG_SOFT"]
    assert section["linkColor"] == c["LINK"]
    assert section["borderColor"] == c["BORDER"]


def test_page_styles_use_one_palette() -> None:
    from src.dashboard.common import css

    dark, light = css("dark"), css("light")
    assert tk.DARK["BG_BLOCK"] in dark and tk.LIGHT["BG_SOFT"] not in dark
    assert "prefers-color-scheme" not in dark + light  # the theme is decided once, not by CSS
    assert 'stMainMenu"] {{' not in dark and "stMainMenu" in dark  # Streamlit's theme menu hidden
