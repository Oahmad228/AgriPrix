"""Colour charter: WCAG AA contrast, brand vs alert separation, one source of truth."""

import tomllib
from pathlib import Path

import pytest
from src.dashboard import tokens as tk

ROOT = Path(__file__).resolve().parents[2]
THEMES = sorted(tk.THEMES)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("name", tk.TEXT_NAMES)
@pytest.mark.parametrize("background", ["BG", "BG_SOFT"])
def test_text_tokens_reach_aa(theme: str, name: str, background: str) -> None:
    c = tk.palette(theme)
    ratio = tk.contrast(c[name], c[background])
    assert ratio >= 4.5, f"{theme} : {name} sur {background} : {ratio:.2f}:1 < 4,5:1"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("name", tk.GRAPHIC_NAMES)
@pytest.mark.parametrize("background", ["BG", "BG_SOFT"])
def test_graphic_tokens_reach_3_to_1(theme: str, name: str, background: str) -> None:
    c = tk.palette(theme)
    ratio = tk.contrast(c[name], c[background])
    assert ratio >= 3.0, f"{theme} : {name} sur {background} : {ratio:.2f}:1 < 3:1"


@pytest.mark.parametrize("theme", THEMES)
def test_text_on_selection_and_season_tag(theme: str) -> None:
    c = tk.palette(theme)
    assert tk.contrast(c["SELECT_TEXT"], c["SELECT"]) >= 4.5
    assert tk.contrast(c["INK"], c["SEASON_TAG_BG"]) >= 4.5


def test_both_modes_define_every_role() -> None:
    assert set(tk.LIGHT) == set(tk.DARK) == set(tk.ROLE_NAMES)
    assert tk.palette("dark")["MAP_STYLE"] == "carto-darkmatter"
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


def test_page_styles_carry_both_modes() -> None:
    from src.dashboard.common import css

    styles = css()
    assert tk.LIGHT["BG_SOFT"] in styles and tk.DARK["BG_SOFT"] in styles
    assert "@media (prefers-color-scheme: dark)" in styles
