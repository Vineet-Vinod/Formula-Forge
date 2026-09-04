"""Create printable section and consecutive-frame contact sheets.

uv run --with pillow python tools/blender/tracks/monza_review_media.py
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "assets/tracks/monza/reconstruction"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def sheet(
    paths, destination, columns=4, size=(320, 180), title="Monza review", labels=None
):
    rows = (len(paths) + columns - 1) // columns
    w, h = size
    gap = 12
    header = 60
    caption = 26
    im = Image.new(
        "RGB",
        (columns * (w + gap) + gap, header + rows * (h + caption + gap) + gap),
        "#142126",
    )
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 13)
    tf = ImageFont.truetype(FONT, 24)
    d.text((gap, 15), title, font=tf, fill="#ebeee4")
    for i, p in enumerate(paths):
        x = gap + (i % columns) * (w + gap)
        y = header + (i // columns) * (h + caption + gap)
        with Image.open(p) as src:
            im.paste(src.convert("RGB").resize(size, Image.Resampling.LANCZOS), (x, y))
        d.text(
            (x, y + h + 5),
            labels[i] if labels else p.stem.replace("_", " "),
            font=f,
            fill="#dae2d4",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.save(destination)


def main():
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--lap", action="store_true")
    args = parser.parse_args()
    survey = json.loads((OUT / "survey.json").read_text())
    if args.lap:
        paths = sorted((OUT / "qa/lap").glob("*.png"))
        groups = {}
        for path in paths:
            groups.setdefault(int(path.stem) // 96, []).append(path)
        for group, part in sorted(groups.items()):
            labels = [
                f"F{int(p.stem) + 1:04d} / {int(p.stem) * 5793 / 1931:.0f} m"
                for p in part
            ]
            sheet(
                part,
                OUT / f"qa/lap_sheets/lap_{group + 1:02d}.jpg",
                8,
                (160, 90),
                f"Monza / consecutive lap frames {int(part[0].stem) + 1}-{int(part[-1].stem) + 1}",
                labels,
            )
        print(f"{len(paths)} rendered frames, {len(groups)} contact sheets")
    else:
        names = [s["name"] for s in survey["sections"]]
        for view in ["DRIVER", "ELEVATED"]:
            paths = [OUT / f"qa/sections/{view}_{n}.png" for n in names]
            sheet(
                paths,
                OUT / f"qa/{view.lower()}_contact_sheet.jpg",
                2,
                (640, 360),
                "Monza / "
                + (
                    "driver views at 1.2 m"
                    if view == "DRIVER"
                    else "elevated section views"
                ),
            )


if __name__ == "__main__":
    main()
