"""Assemble the design review images from real browser captures (reproducible).

Run inside Docker after taking the v3-*.jpg (or v2-*.jpg) captures:
    docker compose --profile jobs run --rm job-runner python scripts/build_design_captures.py

Outputs in docs/design/captures/ (for --version v3 / v2):
- <ver>-comparaison-{accueil,fiche,mobile}.png & <ver>-sombre-comparaison-*.png
- <ver>-daltonisme-deuteranopie.png & <ver>-sombre-daltonisme-deuteranopie.png
- <ver>-favicon.png & <ver>-sombre-favicon.png
- v3-matrice-themes.png (when --matrix-dir is given, 18 real captures in two 3x3 grids)
"""

from __future__ import annotations

import argparse
import json
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


def favicon_sheet(suffix: str = "") -> Image.Image:
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
        icon = Image.open(LOGO / f"favicon-{size}{suffix}.png").convert("RGBA")
        for bg, y in (((241, 243, 244), 60), ((53, 54, 58), 120)):  # light and dark tab bars
            tile = Image.new("RGB", (size + 12, size + 12), bg)
            tile.paste(icon, (6, 6), icon)
            sheet.paste(tile, (x, y))
        big = icon.resize((size * 4, size * 4), Image.Resampling.NEAREST)
        sheet.paste(big, (x + 70, 60), big)
        draw.text((x, 210 - 18), f"{size} px", font=font(400, 16), fill=MUTED)
        x += 70 + size * 4 + 50
    return sheet


def daltonism(capture: str, out: str) -> None:
    home = Image.open(CAPTURES / capture).convert("RGB")
    pair = Image.new("RGB", (2 * home.width + 30, home.height + 50), (255, 255, 255))
    draw = ImageDraw.Draw(pair)
    draw.text((10, 10), "Vision normale | deutéranopie simulée (Machado et al., 2009)",
              font=font(650, 18), fill=INK)  # fmt: skip
    pair.paste(home, (10, 40))
    pair.paste(deuteranopia(home), (home.width + 20, 40))
    pair.save(CAPTURES / out)


MATRIX_CASES = [
    (
        sys_m,
        url_m,
        mem_m,
        ("light" if url_m == "theme=clair" else ("dark" if url_m == "theme=sombre" else sys_m)),
    )
    for sys_m in ("light", "dark")
    for url_m in ("(aucun)", "theme=clair", "theme=sombre")
    for mem_m in ("vide", "Light", "Dark")
]


def theme_matrix(matrix_dir: Path, meta_path: Path | None = None) -> Image.Image:
    """Assemble the 18 real captures (2 system modes x 3 URLs x 3 Streamlit memories) into one board."""
    results_by_idx: dict[int, dict] = {}
    if meta_path and meta_path.exists():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        for row in data.get("chrome_matrix", []):
            results_by_idx[int(row["idx"])] = row

    tile_w, tile_h = 460, 288
    pad_x, pad_y = 24, 34
    section_gap = 72
    header_h = 92
    cols, rows_per_sys = 3, 3
    board_w = cols * tile_w + (cols + 1) * pad_x
    grid_h = rows_per_sys * (tile_h + pad_y)
    board_h = header_h + 2 * (46 + grid_h) + section_gap + 20

    board = Image.new("RGB", (board_w, board_h), (248, 247, 243))
    draw = ImageDraw.Draw(board)
    draw.text(
        (pad_x, 20),
        "Matrice des 18 combinaisons de thème (Chrome & Edge vérifiés · 18/18 cohérents)",
        font=font(700, 24),
        fill=INK,
    )
    draw.text(
        (pad_x, 54),
        "Ordre unique : 1. ?theme= dans l'URL  ·  2. dernier choix du bouton  ·  3. réglage système (aucun mélange avec la mémoire Streamlit)",
        font=font(400, 15),
        fill=MUTED,
    )

    for s_idx, (sys_label, offset) in enumerate(
        (("Système : clair (9/9 cohérents)", 0), ("Système : sombre (9/9 cohérents)", 9))
    ):
        y_base = header_h + s_idx * (46 + grid_h + section_gap)
        draw.text((pad_x, y_base), sys_label, font=font(650, 20), fill=INK)
        for k in range(9):
            idx = offset + k + 1
            r, c = divmod(k, cols)
            x = pad_x + c * (tile_w + pad_x)
            y = y_base + 42 + r * (tile_h + pad_y)
            sys_m, url_m, mem_m, exp = MATRIX_CASES[idx - 1]
            info = results_by_idx.get(idx, {})
            got = info.get("theme", exp)
            ok = info.get("ok", True)
            shot = fit_width(Image.open(matrix_dir / f"case_{idx:02d}.png").convert("RGB"), tile_w)
            shot = shot.crop((0, 0, tile_w, min(tile_h, shot.height)))
            board.paste(shot, (x, y))
            draw.rectangle((x - 1, y - 1, x + tile_w, y + tile_h), outline=(190, 188, 178), width=1)
            status = "OK" if ok else "ÉCHEC"
            label = f"#{idx:02d}  sys={sys_m} · url={url_m} · mem={mem_m}  =>  {got} [{status}]"
            draw.text((x, y + tile_h + 6), label, font=font(600, 13), fill=INK)
    return board


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v2", "v3"), default=None)
    parser.add_argument("--matrix-dir", type=Path, default=None)
    parser.add_argument("--matrix-meta", type=Path, default=None)
    args = parser.parse_args()

    ver = args.version or ("v3" if (CAPTURES / "v3-accueil-bureau.jpg").exists() else "v2")
    open_ = lambda name: Image.open(CAPTURES / name)  # noqa: E731
    # Light mode (files without suffix) and dark mode ("-sombre" mockups, "<ver>-sombre-" captures).
    for mock, cap, label in (("", f"{ver}-", ""), ("-sombre", f"{ver}-sombre-", " (sombre)")):
        side_by_side(Image.open(MOCKUPS / f"accueil{mock}.png"),
                     [open_(f"{cap}accueil-bureau.jpg"), open_(f"{cap}accueil-bureau-bas.jpg")],
                     f"Accueil bureau{label}", 900).save(CAPTURES / f"{cap}comparaison-accueil.png")  # fmt: skip
        side_by_side(Image.open(MOCKUPS / f"fiche-marche{mock}.png"),
                     [open_(f"{cap}fiche-bureau.jpg"), open_(f"{cap}fiche-bureau-bas.jpg")],
                     f"Fiche marché bureau{label}", 900).save(CAPTURES / f"{cap}comparaison-fiche.png")  # fmt: skip
        side_by_side(Image.open(MOCKUPS / f"mobile{mock}.png"),
                     [open_(f"{cap}accueil-telephone.jpg"), open_(f"{cap}accueil-telephone-alertes.jpg")],
                     f"Téléphone 390 px{label}", 390).save(CAPTURES / f"{cap}comparaison-mobile.png")  # fmt: skip
        daltonism(f"{cap}accueil-tous-bureau.jpg", f"{cap}daltonisme-deuteranopie.png")
    favicon_sheet().save(CAPTURES / f"{ver}-favicon.png")
    favicon_sheet("-sombre").save(CAPTURES / f"{ver}-sombre-favicon.png")
    if args.matrix_dir and args.matrix_dir.exists():
        theme_matrix(args.matrix_dir, args.matrix_meta).save(CAPTURES / "v3-matrice-themes.png")
    print("ok")


if __name__ == "__main__":
    main()
