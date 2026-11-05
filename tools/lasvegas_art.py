"""Small original, repeatable textures; no photographs or third-party artwork."""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

GLYPHS = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01111100001000010000100001000001111', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01111100001000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '11111001000010000100001000010011111', 'J': '00111000100001000010100101001001100',
    'K': '10001100101010011000101001001010001', 'L': '10000100001000010000100001000011111',
    'M': '10001110111010110101100011000110001', 'N': '10001110011010110011100011000110001',
    'O': '01110100011000110001100011000101110', 'P': '11110100011000111110100001000010000',
    'Q': '01110100011000110001101011001001101', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011101110001', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Z': '11111000010001000100010001000011111',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11110000010000101110000010000111110',
    '4': '00010001100101010010111110001000010', '5': '11111100001000011110000010000111110',
    '6': '01110100001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010000101110',
    ' ': '0' * 35,
}


def png(path: Path, width: int, height: int, pixels: bytes | bytearray) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload))
    rows = b''.join(b'\0' + pixels[row * width * 4:(row + 1) * width * 4] for row in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
                    + chunk(b'IDAT', zlib.compress(rows, 8)) + chunk(b'IEND', b''))


def sign(path: Path, text: str, background: tuple[int, int, int], foreground: tuple[int, int, int],
         width: int = 1024, height: int = 128) -> None:
    pixels = bytearray((*background, 255)) * (width * height)
    scale = min((width - 48) // (len(text) * 6), (height - 24) // 7)
    x0, y0 = (width - len(text) * 6 * scale) // 2, (height - 7 * scale) // 2
    for character, letter in enumerate(text):
        for index, bit in enumerate(GLYPHS[letter]):
            if bit != '1':
                continue
            for dy in range(scale):
                for dx in range(scale):
                    x = x0 + (character * 6 + index % 5) * scale + dx
                    y = y0 + (index // 5) * scale + dy
                    offset = (y * width + x) * 4
                    pixels[offset:offset + 4] = bytes((*foreground, 255))
    png(path, width, height, pixels)


def textures(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text, bg, fg in [
        ('WallDark', 'LAS VEGAS', (20, 27, 39), (228, 230, 225)),
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
        sign(directory / f'{name}.png', text, bg, fg)
    for name, wall, glass in [('CreamFacade', (189, 174, 145), (49, 66, 74)),
                               ('BlueFacade', (54, 60, 66), (35, 75, 96)),
                               ('BronzeFacade', (149, 122, 75), (82, 60, 38)),
                               ('Garage', (115, 121, 126), (26, 30, 36))]:
        pixels = bytearray()
        for y in range(128):
            for x in range(128):
                if name == 'Garage':
                    color = wall if y % 8 < 2 or x < 5 else glass
                else:
                    reflection = int(10 * math.sin(y * .02) + 5 * math.cos(x * .031))
                    color = wall if x < 7 or x > 120 or y < 8 or y > 108 else (max(0, glass[0] + reflection), max(0, glass[1] + reflection), max(0, glass[2] + reflection))
                pixels.extend((*color, 255))
        png(directory / f'{name}.png', 128, 128, pixels)
    pixels = bytearray()
    for y in range(128):
        for x in range(128):
            line = min((x + y) % 64, (x - y) % 64, 64 - (x + y) % 64, 64 - (x - y) % 64)
            pixels.extend((156, 165, 169, 255 if line < 2 else 0))
    png(directory / 'Fence.png', 128, 128, pixels)

    source = Path(__file__).resolve().parents[1] / 'Attribution/Sources/lasvegas/art/sphere-display-v1.png'
    (directory / 'Sphere.png').write_bytes(source.read_bytes())
