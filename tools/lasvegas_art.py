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


def textures(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text, bg, fg in [
        ('WallDark', 'LAS VEGAS', (20, 27, 39), (228, 230, 225)),
        ('WallBlue', 'FORMULA FORGE', (15, 37, 82), (235, 238, 246)),
        ('WallPink', 'LAS VEGAS', (154, 15, 105), (249, 233, 246)),
        ('WallGold', 'STRIP CIRCUIT', (223, 177, 44), (24, 24, 23)),
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
        ('Planet', 'PLANET HOLLYWOOD', (34, 43, 59), (232, 219, 189)),
    ]:
        sign(directory / f'{name}.png', text, bg, fg, 256 if text.isdigit() else 1024, 256 if text.isdigit() else 128)
    for name, wall, glass in [('CreamFacade', (189, 174, 145), (49, 66, 74)),
                               ('BlueFacade', (54, 60, 66), (35, 75, 96)),
                               ('BronzeFacade', (149, 122, 75), (82, 60, 38)),
                               ('Garage', (115, 121, 126), (26, 30, 36))]:
        if name != 'Garage':
            from PIL import Image

            source_name = {'CreamFacade': 'cream', 'BlueFacade': 'blue', 'BronzeFacade': 'bronze'}[name]
            source = FONT.parent / (source_name + '-facade-v1.png')
            image = Image.open(source).convert('RGB').resize((1024, 1024), Image.Resampling.LANCZOS)
            facade = bytearray()
            rgb_pixels = image.tobytes()
            for y in range(1024):
                for x in range(1024):
                    offset = (y * 1024 + x) * 3
                    red, green, blue = rgb_pixels[offset:offset + 3]
                    in_window = 44 < x % 256 < 218 and 42 < y % 256 < 230
                    warmth = max(0.0, min(1.0, (red - blue * 1.18 - 12) / 80))
                    alpha = round(warmth * 190) if in_window else 0
                    facade.extend((red, green, blue, alpha))
            png(directory / f'{name}.png', 1024, 1024, facade)
            continue
        pixels = bytearray()
        for y in range(512):
            for x in range(512):
                column, floor = x // 128, y // 128
                wx, wy = x % 128, y % 128
                frame = wx < 8 or wy < 8 or wy > 112
                if name == 'CreamFacade':
                    frame = frame or wx < 28 or wx > 100 or wy < 20
                lit = (column * 19 + floor * 11 + column * floor * 5) % 11 < 4
                alpha = 0
                if name == 'Garage':
                    color = wall if wy % 32 < 3 or wx < 5 else (125, 143, 157)
                    alpha = 150 if wy % 128 < 10 else 0
                elif frame:
                    color = wall
                elif lit:
                    warm = {'CreamFacade': (164, 142, 99), 'BronzeFacade': (136, 111, 68),
                            'BlueFacade': (100, 132, 158)}[name]
                    shade = (.65 + .22 * math.sin(wy * .018)) * (.75 + .25 * math.sin(wx * .13 + floor))
                    if wx % 19 < 3 or wy % 23 < 2:
                        shade *= .55
                    color = round(warm[0] * shade), round(warm[1] * shade), round(warm[2] * shade)
                    alpha = 110 if column % 2 else 155
                else:
                    color = glass
                pixels.extend((*color, alpha))
        png(directory / f'{name}.png', 512, 512, pixels)
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
    from array import array

    root = Path(__file__).resolve().parents[1]
    lights = [tuple(float(v) for v in row) for row in csv.reader((root / 'Content/Generated/LasVegas/Data/night_lights.csv').open())]
    minimum_x, minimum_y = min(p[0] for p in lights) - 9000, min(p[1] for p in lights) - 9000
    width = max(p[0] for p in lights) + 9000 - minimum_x
    height = max(p[1] for p in lights) + 9000 - minimum_y
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
