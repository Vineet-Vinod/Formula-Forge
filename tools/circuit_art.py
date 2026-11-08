"""Original trackside lettering and registered illumination for newly authored venues."""

from __future__ import annotations

import json
import math

import numpy as np
from circuit_mesh import add, world
from circuit_scene import CircuitScene
from lasvegas_art import sign
from PIL import Image

NIGHT = {"bahrain", "jeddah", "singapore"}


def artwork(scene: CircuitScene) -> None:
    directory = scene.scratch / "art"
    directory.mkdir(exist_ok=True)
    for name in ("50", "100", "150", "200"):
        sign(directory / (name + ".png"), name, (241, 241, 231), (15, 17, 18), 256, 256)
    sign(
        directory / "VenueSign.png",
        (scene.provenance.circuit or scene.slug).upper(),
        (13, 32, 29),
        (235, 237, 228),
        1024,
        128,
    )
    sign(
        directory / "EventPanel.png",
        "FORMULA FORGE",
        (20, 86, 64),
        (235, 237, 228),
        1024,
        128,
    )
    for name, label, background, foreground in (
        ("PanelGreen", "aramco", (19, 139, 105), (238, 244, 239)),
        ("PanelYellow", "PIRELLI", (235, 198, 20), (190, 24, 24)),
        ("PanelNavy", "MSC CRUISES", (16, 27, 60), (241, 239, 226)),
        ("PanelPurple", "QATAR AIRWAYS", (90, 19, 49), (243, 237, 225)),
        ("PanelRed", "EMIRATES", (190, 20, 25), (245, 243, 235)),
        ("PanelWhite", "FORMULA FORGE", (229, 229, 217), (20, 26, 29)),
        ('PanelLenovo','Lenovo',(206,29,35),(246,244,237)),
        ('PanelDHL','DHL',(238,201,17),(192,24,25)),
        ('PanelGulfAir','GULF AIR',(17,28,52),(218,197,140)),
        ('PanelPetronas','PETRONAS',(10,158,148),(245,247,239)),
        ('PanelSingapore','SINGAPORE AIRLINES',(9,24,52),(220,188,113)),
        ('PanelAirtel','airtel',(200,15,28),(246,244,237)),
        ('PanelAmericanExpress','AMERICAN EXPRESS',(26,130,184),(246,246,239)),
    ):
        sign(directory / (name + ".png"), label, background, foreground, 1024, 128)
    if scene.slug not in NIGHT:
        return
    lights = []
    for index in range(math.ceil(scene.length / 24)):
        sample = scene.at(index * 24)
        for side in (-1, 1):
            shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
            p = sample.point(side * (sample.half_width + shoulder + 2))
            base = (p[0], p[1], scene.ground(p[0], p[1]))
            top = add(base, (0, 0, 14))
            inward = add(top, (-sample.ty * side * 3, sample.tx * side * 3, 0))
            scene.beam("Building_Lighting", "Steel", base, top, 0.16)
            scene.beam("Building_Lighting", "Steel", top, inward, 0.12)
            scene.box(
                "Building_Lighting",
                "Lamp",
                inward,
                1.8,
                0.65,
                0.15,
                math.atan2(sample.ty, sample.tx),
            )
            lights.append(world(inward))
    minimum_x = min(p[0] for p in lights) - 10000
    minimum_y = min(p[1] for p in lights) - 10000
    width = max(p[0] for p in lights) - minimum_x + 10000
    height = max(p[1] for p in lights) - minimum_y + 10000
    size = 2048
    radiance = np.zeros((size, size), dtype=np.float32)
    elevation = np.zeros((size, size), dtype=np.float32)
    for x, y, z in lights:
        c0 = max(0, int((x - 7000 - minimum_x) / width * size))
        c1 = min(size, int((x + 7000 - minimum_x) / width * size) + 1)
        r0 = max(0, int((y - 7000 - minimum_y) / height * size))
        r1 = min(size, int((y + 7000 - minimum_y) / height * size) + 1)
        dx = minimum_x + (np.arange(c0, c1) + 0.5) * width / size - x
        dy = minimum_y + (np.arange(r0, r1) + 0.5) * height / size - y
        weight = (850**2 / (850**2 + dx[None, :] ** 2 + dy[:, None] ** 2)) ** 1.5
        radiance[r0:r1, c0:c1] += weight
        elevation[r0:r1, c0:c1] += weight * (z - 1400)
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, 0] = np.rint(np.minimum(1, radiance * 0.72) ** 3.4 * 255).astype(
        np.uint8
    )
    ground = np.divide(
        elevation, radiance, out=np.zeros_like(elevation), where=radiance > 0.0001
    )
    pixels[:, :, 1] = np.rint(np.clip((ground + 3200) / 6400, 0, 1) * 255).astype(
        np.uint8
    )
    pixels[:, :, 3] = 255
    Image.fromarray(pixels).save(directory / "FloodlightField.png")
    (scene.scratch / "night-field.json").write_text(
        json.dumps(
            {
                "bounds": [minimum_x, minimum_y, width, height],
                "fixture_count": len(lights),
                "method": "Original estimated14mfixtures24mspacing; registered diffuse field, same shading approach as accepted Vegas, independently authored local coordinates.",
            },
            indent=2,
        )
        + "\n"
    )
