"""Colour charter: WCAG AA contrast, brand vs alert separation, one source of truth."""

import tomllib
from pathlib import Path

import pytest
from src.dashboard import tokens as tk

ROOT = Path(__file__).resolve().parents[2]
BACKGROUNDS = {"blanc": tk.BG, "fond doux": tk.BG_SOFT}


@pytest.mark.parametrize("name", sorted(tk.TEXT_TOKENS))
@pytest.mark.parametrize("background", sorted(BACKGROUNDS))
def test_text_tokens_reach_aa(name: str, background: str) -> None:
    ratio = tk.contrast(tk.TEXT_TOKENS[name], BACKGROUNDS[background])
    assert ratio >= 4.5, f"{name} sur {background} : {ratio:.2f}:1 < 4,5:1"


@pytest.mark.parametrize("name", sorted(tk.GRAPHIC_TOKENS))
@pytest.mark.parametrize("background", sorted(BACKGROUNDS))
def test_graphic_tokens_reach_3_to_1(name: str, background: str) -> None:
    ratio = tk.contrast(tk.GRAPHIC_TOKENS[name], BACKGROUNDS[background])
    assert ratio >= 3.0, f"{name} sur {background} : {ratio:.2f}:1 < 3:1"


def test_white_text_on_selection_and_ink_on_season_tag() -> None:
    assert tk.contrast(tk.SELECT_TEXT, tk.SELECT) >= 4.5
    assert tk.contrast(tk.INK, tk.SEASON_TAG_BG) >= 4.5


def test_brand_accent_never_looks_like_an_alert() -> None:
    assert tk.delta_e2000(tk.BRAND, tk.ALERT_UP) >= tk.MIN_BRAND_ALERT_DE
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
def test_streamlit_theme_mirrors_the_tokens(config: str) -> None:
    path = ROOT / config
    if not path.exists():  # the repository root is not mounted in every container
        pytest.skip(f"{config} not available here")
    theme = tomllib.loads(path.read_text(encoding="utf-8"))["theme"]
    assert theme["primaryColor"] == tk.SELECT
    assert theme["textColor"] == tk.INK
    assert theme["backgroundColor"] == tk.BG
    assert theme["secondaryBackgroundColor"] == tk.BG_SOFT
    assert theme["linkColor"] == tk.LINK
    assert theme["borderColor"] == tk.BORDER
