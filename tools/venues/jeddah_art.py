"""Original typesetting for the panels visible in the Jeddah reference."""

from __future__ import annotations

import math
from pathlib import Path

from lasvegas_art import FONT, sign
from PIL import Image, ImageDraw, ImageFont


def night_environment(directory: Path) -> None:
    width, height = 512, 256
    payload = bytearray(f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {height} +X {width}\n".encode())
    for row in range(height):
        elevation = math.cos(math.pi * (row + .5) / height)
        horizon = (.024, .043, .075)
        pole = (.010, .022, .046) if elevation >= 0 else (.003, .005, .006)
        blend = abs(elevation) ** .45
        color = tuple(a * (1 - blend) + b * blend for a, b in zip(horizon, pole, strict=True))
        maximum = max(color)
        mantissa, exponent = math.frexp(maximum)
        scale = mantissa * 256 / maximum
        channels = (*(min(255, int(value * scale)) for value in color), exponent + 128)
        payload.extend((2, 2, width >> 8, width & 255))
        for value in channels:
            remaining = width
            while remaining:
                run = min(127, remaining)
                payload.extend((128 + run, value))
                remaining -= run
    (directory / "JeddahNightReflection.hdr").write_bytes(payload)


def artwork(directory: Path) -> None:
    night_environment(directory)
    dhl = Image.new("RGB", (1024, 128), (238, 201, 85))
    ink = Image.new("L", (500, 180))
    letters = ImageDraw.Draw(ink)
    letters.text((250, 90), "DHL", font=ImageFont.truetype(str(FONT), 140),
                 fill=255, anchor="mm", stroke_width=3)
    bounds = ink.getbbox()
    if bounds is None:
        raise ValueError("Missing DHL fascia lettering")
    ink = ink.crop(bounds).resize((460, 82), Image.Resampling.LANCZOS)
    ink = ink.transform((484, 82), Image.Transform.AFFINE,
                        (1, .25, -21, 0, 1, 0), Image.Resampling.BICUBIC)
    dhl.paste((192, 24, 25), (270, 23), ink)
    drawing = ImageDraw.Draw(dhl)
    for stripe_top in (43, 61, 79):
        drawing.polygon(((124, stripe_top), (294, stripe_top), (291, stripe_top + 10), (124, stripe_top + 10)), fill=(192, 24, 25))
        drawing.polygon(((746, stripe_top), (900, stripe_top), (900, stripe_top + 10), (743, stripe_top + 10)), fill=(192, 24, 25))
    dhl.save(directory / "PanelDHL.png")
    aramco = Image.new("RGB", (1024, 128), (20, 163, 86))
    drawing = ImageDraw.Draw(aramco)
    drawing.rectangle((512, 0, 1024, 128), fill=(30, 143, 195))
    font = ImageFont.truetype(str(FONT), 96)
    for center in (256, 768):
        drawing.text((center, 62), "aramco", font=font, fill=(245, 247, 241), anchor="mm")
    aramco.save(directory / "PanelJeddahAramco.png")
    for name, label, background, foreground in (
        ("PanelJeddahTag", "TAG HEUER", (12, 15, 16), (244, 245, 239)),
        ("PanelJeddahLV", "LOUIS VUITTON", (22, 25, 49), (222, 212, 184)),
        ("PanelJeddahSalesforce", "salesforce", (19, 34, 63), (146, 218, 244)),
        ("PanelJeddahGlobant", "Globant", (14, 16, 17), (244, 245, 239)),
        ("PanelJeddahCrypto", "crypto.com", (19, 30, 57), (244, 245, 239)),
        ("PanelJeddahSaudiGP", "#SaudiArabianGP", (14, 16, 17), (244, 245, 239)),
    ):
        sign(directory / (name + ".png"), label, background, foreground, 1024, 256)
    entry = Image.new("RGB", (1024, 256), (25, 44, 130))
    drawing = ImageDraw.Draw(entry)
    for bounds in ((60, 86, 172, 190), (106, 48, 218, 174),
                   (170, 79, 278, 190), (84, 116, 264, 201)):
        drawing.ellipse(bounds, fill=(246, 249, 255))
    drawing.text((634, 128), "salesforce", font=ImageFont.truetype(str(FONT), 104),
                 fill=(246, 249, 255), anchor="mm")
    entry.save(directory / "PanelJeddahEntrySalesforce.png")
    msc = Image.new("RGB", (1024, 128), (16, 27, 60))
    drawing = ImageDraw.Draw(msc)
    rays = []
    for point in range(32):
        angle = point * math.tau / 32
        radius = 54 if point % 4 == 0 else 39 if point % 2 == 0 else 15
        rays.append((300 + radius * math.sin(angle), 64 + radius * math.cos(angle)))
    drawing.polygon(rays, fill=(241, 242, 238))
    drawing.ellipse((290, 54, 310, 74), fill=(16, 27, 60))
    drawing.text((640, 64), "MSC", font=ImageFont.truetype(str(FONT), 125),
                 fill=(241, 242, 238), anchor="mm")
    msc.save(directory / "PanelJeddahMsc.png")
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
