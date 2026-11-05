"""Small original, repeatable textures; no photographs or third-party artwork."""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

FONT = Path(__file__).resolve().parents[1] / 'Attribution/Sources/lasvegas/art/DejaVuSans.ttf'


def png(path: Path, width: int, height: int, pixels: bytes | bytearray) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload))
    rows = b''.join(b'\0' + pixels[row * width * 4:(row + 1) * width * 4] for row in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
                    + chunk(b'IDAT', zlib.compress(rows, 8)) + chunk(b'IEND', b''))


def sign(path: Path, text: str, background: tuple[int, int, int], foreground: tuple[int, int, int],
         width: int = 1024, height: int = 128) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new('RGBA', (width * 2, height * 2), (*background, 255))
    draw = ImageDraw.Draw(image)
    size = height
    while size > 12:
        font = ImageFont.truetype(str(FONT), size)
        bounds = draw.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] < width * 1.78 and bounds[3] - bounds[1] < height * 1.4:
            break
        size -= 2
    draw.text((width, height), text, font=font, fill=(*foreground, 255), anchor='mm')
    image.resize((width, height), Image.Resampling.LANCZOS).save(path)


def hotel_facades(directory: Path) -> None:
    from PIL import Image, ImageDraw

    for name, wall, glass, style in [
        ('CreamFacade', (150, 145, 130), (28, 38, 45), 'plain'),
        ('BlueFacade', (48, 59, 68), (24, 45, 63), 'glass'),
        ('BronzeFacade', (84, 65, 46), (43, 39, 33), 'glass'),
        ('PalazzoFacade', (177, 159, 124), (32, 43, 48), 'classical'),
        ('VenetianFacade', (186, 165, 126), (30, 41, 44), 'classical'),
        ('BellagioFacade', (184, 171, 144), (29, 41, 47), 'classical'),
        ('ParisFacade', (160, 155, 145), (30, 42, 52), 'french'),
        ('CaesarsFacade', (188, 182, 166), (33, 42, 48), 'classical'),
        ('TIFacade', (170, 144, 113), (32, 45, 50), 'classical'),
        ('WynnFacade', (77, 55, 36), (66, 49, 32), 'glass'),
        ('CosmoFacade', (42, 48, 56), (24, 51, 71), 'glass'),
        ('PlanetFacade', (71, 79, 87), (28, 47, 65), 'glass'),
        ('FlamingoFacade', (162, 143, 132), (36, 43, 52), 'modern'),
    ]:
        image = Image.new('RGBA', (1024, 1024), (*wall, 0))
        draw = ImageDraw.Draw(image)
        for floor in range(8):
            for room in range(8):
                x, y = room * 128, floor * 128
                seed = (floor * 53 + room * 71 + floor * room * 17) % 97
                lit = seed < (12 if style in ('glass', 'plain') else 27)
                color = (120 + seed, 104 + seed, 77 + seed) if lit else glass
                alpha = 82 if lit else 0
                inset = 2 if style == 'glass' else 26
                top, bottom = (8, 119) if style == 'glass' else (19, 110)
                draw.rectangle((x + inset, y + top, x + 127 - inset, y + bottom), fill=(*color, alpha))
                draw.line((x + 64, y + top, x + 64, y + bottom), fill=(*wall, 0), width=3)
                draw.line((x + inset, y + 58, x + 127 - inset, y + 58), fill=(*wall, 0), width=2)
                if style in ('classical', 'french'):
                    draw.rectangle((x + 19, y + 111, x + 109, y + 117), fill=(max(0, wall[0] - 38), max(0, wall[1] - 38), max(0, wall[2] - 38), 0))
                    draw.line((x + 19, y + 16, x + 109, y + 16), fill=(min(255, wall[0] + 20), min(255, wall[1] + 20), min(255, wall[2] + 20), 0), width=4)
                if lit and seed % 3 == 0:
                    draw.rectangle((x + 77, y + top, x + 127 - inset, y + bottom), fill=(*glass, 0))
        image.save(directory / (name + '.png'))


def textures(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    hotel_facades(directory)
    for name, text, bg, fg in [
        ('RaceSign', 'FORMULA FORGE', (28, 54, 61), (235, 237, 225)),
        ('VegasSign', 'LAS VEGAS STRIP CIRCUIT', (15, 24, 35), (232, 206, 143)),
        ('50', '50', (237, 236, 227), (22, 24, 28)),
        ('100', '100', (237, 236, 227), (22, 24, 28)),
        ('150', '150', (237, 236, 227), (22, 24, 28)),
        ('Bellagio', 'BELLAGIO', (94, 79, 53), (237, 218, 170)),
        ('Venetian', 'THE VENETIAN', (82, 64, 41), (243, 223, 173)),
        ('Palazzo', 'PALAZZO', (82, 64, 41), (243, 223, 173)),
        ('Wynn', 'WYNN LAS VEGAS', (68, 44, 28), (241, 218, 159)),
        ('Paris', 'PARIS', (28, 40, 54), (244, 221, 168)),
        ('Cosmopolitan', 'COSMOPOLITAN', (24, 33, 45), (231, 224, 222)),
        ('Linq', 'THE LINQ', (40, 44, 53), (224, 224, 224)),
        ('Horseshoe', 'HORSESHOE LAS VEGAS', (36, 48, 68), (230, 221, 193)),
        ('Elara', 'ELARA', (24, 35, 46), (228, 225, 211)),
        ('Encore', 'ENCORE', (54, 37, 24), (237, 219, 164)),
        ('TreasureIsland', 'TREASURE ISLAND', (66, 47, 33), (241, 221, 175)),
        ('Caesars', 'CAESARS PALACE', (48, 43, 37), (238, 225, 198)),
        ('Flamingo', 'FLAMINGO', (75, 15, 44), (246, 144, 191)),
        ('EastHarmon', 'EAST HARMON', (22, 43, 52), (232, 226, 197)),
        ('WestHarmon', 'WEST HARMON', (22, 43, 52), (232, 226, 197)),
        ('SphereZone', 'SPHERE ZONE', (97, 18, 68), (240, 215, 234)),
        ('Sands', 'SANDS AVENUE', (22, 43, 52), (232, 226, 197)),
        ('Strip', 'LAS VEGAS BOULEVARD', (22, 43, 52), (232, 226, 197)),
        ('Planet', 'PLANET HOLLYWOOD', (34, 43, 59), (232, 219, 189)),
    ]:
        sign(directory / f'{name}.png', text, bg, fg, 256 if text.isdigit() else 1024, 256 if text.isdigit() else 128)
    from PIL import Image, ImageDraw, ImageFont

    for name, background, accent, title in [
        ('WallDark', (17, 28, 38), (51, 184, 177), 'LAS VEGAS'),
        ('WallBlue', (14, 38, 83), (125, 187, 221), 'FORMULA FORGE'),
        ('WallPink', (135, 15, 84), (242, 169, 217), 'NEVADA NIGHT RACE'),
        ('WallGold', (190, 151, 57), (44, 35, 26), 'STRIP CIRCUIT'),
    ]:
        image = Image.new('RGBA', (1024, 128), (*background, 255))
        draw = ImageDraw.Draw(image)
        for index in range(3):
            x = 30 + index * 24
            draw.polygon([(x, 98), (x + 42, 30), (x + 56, 30), (x + 14, 98)], fill=(*accent, 255))
        font = ImageFont.truetype(str(FONT), 47 if name != 'WallPink' else 38)
        draw.text((160, 57), title, font=font, fill=(237, 235, 220, 255), anchor='lm')
        draw.line((160, 91, 795, 91), fill=(*accent, 255), width=3)
        draw.text((160, 111), 'LAS VEGAS  //  NIGHT GRAND PRIX', font=ImageFont.truetype(str(FONT), 15),
                  fill=(*accent, 255), anchor='lm')
        draw.line((900, 20, 900, 108), fill=(*accent, 255), width=3)
        image.save(directory / (name + '.png'))
    pixels = bytearray()
    for y in range(512):
        for x in range(512):
            wx, wy = x % 128, y % 128
            color = (115, 121, 126) if wy % 32 < 3 or wx < 5 else (125, 143, 157)
            pixels.extend((*color, 150 if wy < 10 else 0))
    png(directory / 'Garage.png', 512, 512, pixels)
    pixels = bytearray()
    for y in range(128):
        for x in range(128):
            line = min((x + y) % 64, (x - y) % 64, 64 - (x + y) % 64, 64 - (x - y) % 64)
            pixels.extend((156, 165, 169, 255 if line < 2 else 0))
    png(directory / 'Fence.png', 128, 128, pixels)

    halo = bytearray()
    for y in range(128):
        for x in range(128):
            radius = ((x - 63.5) / 63.5) ** 2 + ((y - 63.5) / 63.5) ** 2
            halo.extend((255, 250, 235, round(255 * math.exp(-radius * 8))))
    png(directory / 'LightHalo.png', 128, 128, halo)

    pixels = bytearray()
    for y in range(256):
        for x in range(64):
            edge = max(0.0, 1 - abs(x - 31.5) / 31.5)
            noise = ((x * 73 + y * 37 + x * y * 19) % 101) / 100
            pixels.extend((30, 30, 30, 255 if noise < edge * .38 else 0))
    png(directory / 'Rubber.png', 64, 256, pixels)

    source = Path(__file__).resolve().parents[1] / 'Attribution/Sources/lasvegas/art/sphere-display-v1.png'
    (directory / 'Sphere.png').write_bytes(source.read_bytes())


def lightfield(directory: Path) -> tuple[float, float, float, float]:
    import csv
    import json
    from array import array

    root = Path(__file__).resolve().parents[1]
    lights = [tuple(float(v) for v in row) for row in csv.reader((root / 'Content/Generated/LasVegas/Data/night_lights.csv').open())]
    minimum_x, minimum_y, width, height = json.loads((root / 'Attribution/Sources/lasvegas/night-field.json').read_text())['world_bounds_cm']
    size = 2048
    radiance = array('f', [0.0]) * (size * size)
    elevation = array('f', [0.0]) * (size * size)
    for x, y, z in lights:
        col0 = max(0, int((x - 7000 - minimum_x) / width * size))
        col1 = min(size, int((x + 7000 - minimum_x) / width * size) + 1)
        row0 = max(0, int((y - 7000 - minimum_y) / height * size))
        row1 = min(size, int((y + 7000 - minimum_y) / height * size) + 1)
        for row in range(row0, row1):
            dy = minimum_y + (row + .5) * height / size - y
            for col in range(col0, col1):
                dx = minimum_x + (col + .5) * width / size - x
                weight = (1200 ** 2 / (1200 ** 2 + dx * dx + dy * dy)) ** 1.5
                index = row * size + col
                radiance[index] += weight
                elevation[index] += weight * (z - 1120)
    pixels = bytearray()
    for index, value in enumerate(radiance):
        ground = elevation[index] / value if value > .0001 else 0
        brightness = min(1.0, value * .65) ** 1.4
        pixels.extend((round(brightness * 255), round(max(0, min(1, (ground + 3200) / 6400)) * 255), 0, 255))
    png(directory / 'FloodlightField.png', size, size, pixels)
    return minimum_x, minimum_y, width, height


if __name__ == '__main__':
    textures(Path(__file__).resolve().parents[1] / 'build/lasvegas/art')
