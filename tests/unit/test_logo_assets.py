"""Logo pipeline: only the outside white becomes transparent, the shape is never changed."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_logo_assets.py"
if not SCRIPT.exists():  # pragma: no cover - scripts/ not mounted
    pytest.skip("scripts/build_logo_assets.py not available here", allow_module_level=True)
spec = importlib.util.spec_from_file_location("build_logo_assets", SCRIPT)
logo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logo)


def _eye(size: int = 400) -> Image.Image:
    """A synthetic eye: navy iris inside a rust almond whose corners leave narrow gaps."""
    image = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.arc((40, 110, 360, 330), 186, 354, fill=(165, 63, 18), width=14)  # upper lid
    draw.arc((40, 70, 360, 290), 6, 174, fill=(165, 63, 18), width=14)  # lower lid
    draw.ellipse((150, 150, 250, 250), fill=(33, 37, 74))  # iris
    draw.ellipse((185, 185, 215, 215), fill=(105, 145, 59))  # green centre
    return image


def test_outside_becomes_transparent_and_the_white_of_the_eye_stays() -> None:
    image = _eye()
    rgba = np.asarray(logo.transparent_logo(image))
    assert rgba[5, 5, 3] == 0  # corner: outside
    assert rgba[200, 200, 3] == 255  # iris
    # White between the iris and the lids (inside the eye) stays opaque white.
    assert rgba[145, 175, 3] == 255 and rgba[145, 175, :3].min() > 230
    # Colours of opaque pixels are untouched.
    assert tuple(rgba[200, 200, :3]) == (105, 145, 59)


def test_iris_is_found_from_its_pixels() -> None:
    cx, cy, radius = logo.iris_geometry(np.asarray(_eye()))
    assert abs(cx - 200) <= 2 and abs(cy - 200) <= 2
    assert 40 <= radius <= 52


def test_crop_keeps_a_four_percent_margin() -> None:
    cropped = logo.crop(logo.transparent_logo(_eye()))
    alpha = np.asarray(cropped)[..., 3]
    ys, xs = np.nonzero(alpha > 8)
    margin = round(logo.MARGIN * max(cropped.size))
    assert xs.min() == pytest.approx(margin, abs=2) and ys.min() == pytest.approx(margin, abs=2)


def test_icons_are_the_whole_logo_never_a_cut_out() -> None:
    whole = logo.crop(logo.transparent_logo(_eye()))
    for size in (16, 32, 48, 192):
        icon = logo.square(whole, size)
        assert icon.size == (size, size)
        # The whole logo is scaled, not cropped: its width fills the square.
        xs = np.nonzero(np.asarray(icon)[..., 3].max(axis=0) > 8)[0]
        assert xs.max() - xs.min() + 1 >= 0.85 * size  # only the 4 % margin around it
