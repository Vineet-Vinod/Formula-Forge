"""Original typesetting for the panels visible in the Jeddah reference."""

from __future__ import annotations

from pathlib import Path

from lasvegas_art import FONT, sign
from PIL import Image, ImageDraw, ImageFont


def artwork(directory: Path) -> None:
    for name, label, background, foreground in (
        ("PanelJeddahTag", "TAG HEUER", (12, 15, 16), (244, 245, 239)),
        ("PanelJeddahLV", "LOUIS VUITTON", (22, 25, 49), (222, 212, 184)),
        ("PanelJeddahSalesforce", "salesforce", (19, 34, 63), (146, 218, 244)),
        ("PanelJeddahGlobant", "Globant", (14, 16, 17), (244, 245, 239)),
        ("PanelJeddahCrypto", "crypto.com", (19, 30, 57), (244, 245, 239)),
        ("PanelJeddahSaudiGP", "#SaudiArabianGP", (14, 16, 17), (244, 245, 239)),
    ):
        sign(directory / (name + ".png"), label, background, foreground, 1024, 256)
    for distance in (50, 100, 150):
        image = Image.new("RGB", (256, 768), (244, 244, 239))
        draw = ImageDraw.Draw(image)
        digits = str(distance)
        font = ImageFont.truetype(str(FONT), 260)
        spacing = 210
        top = (768 - len(digits) * spacing) / 2
        for index, digit in enumerate(digits):
            draw.text((128, top + (index + .5) * spacing), digit,
                      font=font, fill=(18, 20, 21), anchor="mm", stroke_width=1)
        image.save(directory / f"JeddahDistance{distance}.png")
    for name in ("JeddahPitSpeed80", "JeddahPitLimitEnd"):
        image = Image.new("RGB", (600, 800), (245, 245, 240))
        draw = ImageDraw.Draw(image)
        if name == "JeddahPitSpeed80":
            draw.ellipse((44, 134, 556, 646), outline=(197, 21, 31), width=48)
            draw.text((300, 390), "80", font=ImageFont.truetype(str(FONT), 230),
                      fill=(13, 15, 17), anchor="mm", stroke_width=3)
        else:
            draw.ellipse((74, 164, 526, 616), outline=(22, 24, 25), width=25)
            draw.line((106, 628, 500, 150), fill=(22, 24, 25), width=64)
        image.save(directory / (name + ".png"))
