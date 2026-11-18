"""Assemble the design review images from real browser captures (reproducible).

Run inside Docker after taking the v2-*.jpg captures:
    docker compose --profile jobs run --rm job-runner python scripts/build_design_captures.py

Outputs in docs/design/captures/:
- v2-comparaison-{accueil,fiche,mobile}.png : mockup (left) | result (right);
- v2-daltonisme-deuteranopie.png : home as seen with full deuteranopia (Machado et al., 2009);
- v2-favicon.png : the favicon (whole logo) at 16, 32, 48 px on light and dark tab bars.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "docs" / "design" / "captures"
MOCKUPS = ROOT / "docs" / "design" / "maquette-v2" / "export"
LOGO = ROOT / "docs" / "design" / "logo"
FONT = ROOT / "src" / "dashboard" / "static" / "fonts" / "PublicSans-Variable.ttf"
INK, MUTED = (33, 37, 74), (79, 83, 107)

# Machado, Oliveira & Fernandes (2009), deuteranopia, severity 1.0, applied in linear RGB.
DEUTERANOPIA = np.array(
    [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881],
    ]
)


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size)
    face.set_variation_by_axes([weight])
    return face


def fit_width(image: Image.Image, width: int) -> Image.Image:
    return image.resize(
        (width, round(image.height * width / image.width)), Image.Resampling.LANCZOS
    )


def side_by_side(
    left: Image.Image, rights: list[Image.Image], title: str, width: int
) -> Image.Image:
    """Mockup on the left, the real captures stacked on the right, both at the same width."""
    left = fit_width(left.convert("RGB"), width)
    rights = [fit_width(r.convert("RGB"), width) for r in rights]
    right_h = sum(r.height for r in rights) + 10 * (len(rights) - 1)
    height = max(left.height, right_h) + 70
    sheet = Image.new("RGB", (2 * width + 60, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (20, 14), f"{title} : maquette (gauche) | réalisé (droite)", font=font(650, 24), fill=INK
    )
    sheet.paste(left, (20, 60))
    y = 60
    for r in rights:
        sheet.paste(r, (width + 40, y))
        y += r.height + 10
    draw.line((width + 30, 60, width + 30, height - 10), fill=(217, 214, 204), width=2)
    return sheet


def deuteranopia(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB")).astype(float) / 255
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    seen = np.clip(linear @ DEUTERANOPIA.T, 0, 1)
    srgb = np.where(seen <= 0.0031308, 12.92 * seen, 1.055 * seen ** (1 / 2.4) - 0.055)
    return Image.fromarray((srgb * 255).round().astype(np.uint8))


def favicon_sheet() -> Image.Image:
    sheet = Image.new("RGB", (760, 230), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (20, 14),
        "Favicon : le logo complet, réduit (taille réelle et ×4)",
        font=font(650, 22),
        fill=INK,
    )
    x = 20
    for size in (16, 32, 48):
        icon = Image.open(LOGO / f"favicon-{size}.png").convert("RGBA")
        for bg, y in (((241, 243, 244), 60), ((53, 54, 58), 120)):  # light and dark tab bars
            tile = Image.new("RGB", (size + 12, size + 12), bg)
            tile.paste(icon, (6, 6), icon)
            sheet.paste(tile, (x, y))
        big = icon.resize((size * 4, size * 4), Image.Resampling.NEAREST)
        sheet.paste(big, (x + 70, 60), big)
        draw.text((x, 210 - 18), f"{size} px", font=font(400, 16), fill=MUTED)
        x += 70 + size * 4 + 50
    return sheet


def main() -> None:
    open_ = lambda name: Image.open(CAPTURES / name)  # noqa: E731
    side_by_side(Image.open(MOCKUPS / "accueil.png"),
                 [open_("v2-accueil-bureau.jpg"), open_("v2-accueil-bureau-bas.jpg")],
                 "Accueil bureau", 900).save(CAPTURES / "v2-comparaison-accueil.png")  # fmt: skip
    side_by_side(Image.open(MOCKUPS / "fiche-marche.png"),
                 [open_("v2-fiche-bureau.jpg"), open_("v2-fiche-bureau-bas.jpg")],
                 "Fiche marché bureau", 900).save(CAPTURES / "v2-comparaison-fiche.png")  # fmt: skip
    side_by_side(Image.open(MOCKUPS / "mobile.png"),
                 [open_("v2-accueil-telephone.jpg"), open_("v2-accueil-telephone-alertes.jpg")],
                 "Téléphone 390 px", 390).save(CAPTURES / "v2-comparaison-mobile.png")  # fmt: skip
    home = Image.open(CAPTURES / "v2-accueil-tous-bureau.jpg").convert("RGB")  # rises and falls
    pair = Image.new("RGB", (2 * home.width + 30, home.height + 50), (255, 255, 255))
    draw = ImageDraw.Draw(pair)
    draw.text((10, 10), "Vision normale | deutéranopie simulée (Machado et al., 2009)",
              font=font(650, 18), fill=INK)  # fmt: skip
    pair.paste(home, (10, 40))
    pair.paste(deuteranopia(home), (home.width + 20, 40))
    pair.save(CAPTURES / "v2-daltonisme-deuteranopie.png")
    favicon_sheet().save(CAPTURES / "v2-favicon.png")
    print("ok")


if __name__ == "__main__":
    main()
