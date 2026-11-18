"""Build every logo asset from the single source image (reproducible, no redrawing).

Run inside Docker:
    docker compose --profile jobs run --rm job-runner python scripts/build_logo_assets.py

Input : docs/design/logo/agriprix-logo-source.png (white background).
Output: docs/design/logo/ (transparent logo and sizes, horizontal lock-up, iris favicons,
        favicon comparison sheet, measured palette) and src/dashboard/static/brand/ (the
        files the dashboard serves).

The logo shape is never modified: the script only makes the OUTSIDE white transparent
(flood fill from the image border), crops, scales, and cuts the iris out as a circle.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from sklearn.cluster import KMeans

ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "docs" / "design" / "logo"
STATIC = ROOT / "src" / "dashboard" / "static" / "brand"
CAPTURES = ROOT / "docs" / "design" / "captures"
SOURCE = LOGO_DIR / "agriprix-logo-source.png"  # light mode: transparent, as given
# Dark mode: Ahmad's version with an opaque white eye (2026-11-18), used as given.
SOURCE_DARK = LOGO_DIR / "agriprix-logo-source-sombre.png"
FONT = ROOT / "src" / "dashboard" / "static" / "fonts" / "PublicSans-Variable.ttf"

WHITE_LEVEL = 232  # a pixel is "background white" when its darkest channel is above this
SEAL_RADIUS = 16  # px at 2000 px: closes hairline gaps along the outline
EYE_SEAL_RADIUS = 28  # px: closes the corners of the eye, only around the iris
MARGIN = 0.04  # crop margin, share of the longest side
INK = (33, 37, 74)  # tokens.INK #21254A
MUTED = (79, 83, 107)  # tokens.TEXT_MUTED #4F536B
INK_DARK = (243, 239, 230)  # tokens.DARK["INK"] #F3EFE6
MUTED_DARK = (189, 186, 203)  # tokens.DARK["TEXT_MUTED"] #BDBACB
SUBTITLE = "Observatoire des prix agricoles"


def load_source() -> Image.Image:
    """The source on a white background.

    The file received on 2026-11-18 is a 2000 px RGBA image whose white had already been
    removed everywhere, the white of the eye included. Laying it on white restores the
    white-background original; outside_mask() then removes only the outside white.
    """
    image = Image.open(SOURCE)
    if image.mode in ("RGBA", "LA", "P"):
        white = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, image.convert("RGBA"))
    return image.convert("RGB")


def prepared_logo(source: Path | None = None) -> Image.Image:
    """The logo exactly as Ahmad gave it when it already has transparency (decision of
    2026-11-18: use the logo directly, no white added inside the eye). Only a source on a
    white background goes through transparent_logo()."""
    image = Image.open(source or SOURCE)
    if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
        return image.copy()
    return transparent_logo(load_source())


def silhouette(white: np.ndarray, radius: int) -> np.ndarray:
    """Shapes closed with a disc of `radius` px, then holes filled: a flood fill from the
    border that cannot leak through gaps narrower than 2 x radius."""
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    disc = (xx**2 + yy**2) <= radius**2
    pad = radius + 2
    closed = ndimage.binary_closing(np.pad(~white, pad), structure=disc)[pad:-pad, pad:-pad]
    return ndimage.binary_fill_holes(closed)


def iris_geometry(rgb: np.ndarray) -> tuple[float, float, float]:
    """Centre and radius of the iris, from its largest dark-navy area (no hand coordinates)."""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    navy = (b > r + 25) & (b > g + 10) & (rgb.max(axis=2) < 120)
    labels, _ = ndimage.label(navy)
    biggest = np.argmax(np.bincount(labels.ravel())[1:]) + 1
    ys, xs = np.nonzero(labels == biggest)
    radius = (xs.max() - xs.min() + ys.max() - ys.min()) / 4
    return (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2, radius


def outside_mask(rgb: np.ndarray) -> np.ndarray:
    """True where the white is background reached from the border (to make transparent).

    A plain flood fill leaks into the white of the eye through the eye's corners. So:
    a 16 px seal everywhere (keeps the outline tight), plus a 28 px seal inside an ellipse
    of 1.5 x 1.2 iris radii around the iris, which closes the eye's corners.
    """
    white = rgb.min(axis=2) > WHITE_LEVEL
    cx, cy, radius = iris_geometry(rgb)
    yy, xx = np.mgrid[0 : rgb.shape[0], 0 : rgb.shape[1]]
    eye = ((xx - cx) / (1.5 * radius)) ** 2 + ((yy - cy) / (1.2 * radius)) ** 2 <= 1
    keep = silhouette(white, SEAL_RADIUS) | (silhouette(white, EYE_SEAL_RADIUS) & eye)
    return ~keep


def transparent_logo(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image).astype(np.float32)
    outside = outside_mask(rgb.astype(np.uint8))
    alpha = np.where(outside, 0.0, 255.0)
    # Soft edge: a 2 px band along the outside keeps anti-aliasing (whiter = more transparent).
    band = ndimage.binary_dilation(outside, iterations=2) & ~outside
    lightness = rgb.min(axis=2)
    soft = np.clip((255.0 - lightness) / (255.0 - 150.0), 0.0, 1.0) * 255.0
    alpha[band] = soft[band]
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def crop(logo: Image.Image) -> Image.Image:
    box = logo.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    cropped = logo.crop(box)
    pad = round(MARGIN * max(cropped.size))
    canvas = Image.new("RGBA", (cropped.width + 2 * pad, cropped.height + 2 * pad), (0, 0, 0, 0))
    canvas.paste(cropped, (pad, pad), cropped)
    return canvas


def square(logo: Image.Image, size: int) -> Image.Image:
    scale = size / max(logo.size)
    resized = logo.resize(
        (round(logo.width * scale), round(logo.height * scale)), Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2), resized)
    return canvas


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size)
    face.set_variation_by_axes([weight])
    return face


def horizontal(
    logo: Image.Image,
    height: int = 256,
    subtitle_text: str | None = SUBTITLE,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]] = (INK, MUTED),
) -> Image.Image:
    mark = logo.resize((round(logo.width * height / logo.height), height), Image.Resampling.LANCZOS)
    title, subtitle = font(700, round(height * 0.40)), font(400, round(height * 0.15))
    gap = round(height * 0.12)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    t_box = probe.textbbox((0, 0), "AgriPrix", font=title)
    s_box = (
        probe.textbbox((0, 0), subtitle_text or "", font=subtitle)
        if subtitle_text
        else (0, 0, 0, 0)
    )
    width = mark.width + gap + max(t_box[2], s_box[2]) + round(height * 0.06)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    spacing = round(height * 0.08) if subtitle_text else 0
    block = (t_box[3] - t_box[1]) + spacing + (s_box[3] - s_box[1])
    top = (height - block) // 2
    draw.text((mark.width + gap, top - t_box[1]), "AgriPrix", font=title, fill=colors[0])
    if subtitle_text:
        y_sub = top + (t_box[3] - t_box[1]) + spacing - s_box[1]
        draw.text((mark.width + gap, y_sub), subtitle_text, font=subtitle, fill=colors[1])
    return canvas


def palette(logo: Image.Image, clusters: int = 9) -> list[dict]:
    """k-means on the opaque, non-white pixels of the logo (measured, not guessed)."""
    data = np.asarray(logo)
    keep = (data[..., 3] == 255) & (data[..., :3].min(axis=2) < 200)
    pixels = data[keep][:, :3].astype(float)
    rng = np.random.default_rng(0)
    sample = pixels[rng.choice(len(pixels), size=min(60000, len(pixels)), replace=False)]
    model = KMeans(n_clusters=clusters, n_init=10, random_state=0).fit(sample)
    shares = np.bincount(model.labels_, minlength=clusters) / len(sample)
    out = []
    for centre, share in sorted(
        zip(model.cluster_centers_, shares, strict=True), key=lambda x: -x[1]
    ):
        hex_code = "#{:02X}{:02X}{:02X}".format(*(round(c) for c in centre))
        out.append({"hex": hex_code, "share_pct": round(100 * float(share), 1)})
    return out


def export(logo: Image.Image, suffix: str, colors: tuple) -> None:
    """Every size of one logo version (suffix "" = light mode, "-sombre" = dark mode)."""
    logo.save(LOGO_DIR / f"agriprix-logo{suffix}.png", optimize=True)
    for size in (1024, 512, 256):
        square(logo, size).save(LOGO_DIR / f"agriprix-logo{suffix}-{size}.png", optimize=True)
    horizontal(logo, colors=colors).save(
        LOGO_DIR / f"agriprix-logo-horizontal{suffix}.png", optimize=True
    )
    # Always the whole logo (decision of 2026-11-18): header, favicons, app icons.
    horizontal(logo, height=128, subtitle_text=None, colors=colors).save(
        LOGO_DIR / f"agriprix-lockup{suffix}.png", optimize=True
    )
    for size in (16, 32, 48):
        square(logo, size).save(LOGO_DIR / f"favicon-{size}{suffix}.png")
    square(logo, 48).save(LOGO_DIR / f"favicon{suffix}.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for size in (192, 512):
        square(logo, size).save(LOGO_DIR / f"icon-{size}{suffix}.png", optimize=True)
    for name in (f"agriprix-logo-horizontal{suffix}.png", f"agriprix-logo{suffix}-256.png",
                 f"favicon-32{suffix}.png", f"icon-192{suffix}.png", f"agriprix-lockup{suffix}.png"):  # fmt: skip
        shutil.copy(LOGO_DIR / name, STATIC / name)


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    logo = crop(prepared_logo())
    export(logo, "", (INK, MUTED))
    if SOURCE_DARK.exists():
        export(crop(prepared_logo(SOURCE_DARK)), "-sombre", (INK_DARK, MUTED_DARK))
    measured = palette(logo)
    (LOGO_DIR / "palette-mesuree.json").write_text(
        json.dumps(measured, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(measured, ensure_ascii=False))


if __name__ == "__main__":
    main()
