"""Original trackside lettering and registered illumination for newly authored venues."""

from __future__ import annotations

import json

import numpy as np
from circuit_mesh import world
from circuit_scene import CircuitScene
from lasvegas_art import sign
from PIL import Image
from venues.jeddah_art import artwork as jeddah_artwork
from venues.night_lighting import build_lighting

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
    if scene.slug == "jeddah":
        sign(directory / "PanelStc.png", "stc", (79, 0, 140), (246, 246, 239), 1024, 128)
        jeddah_artwork(directory)
    if scene.slug == "australia":
        sign(directory / "GroundPirelli.png", "PIRELLI", (10, 10, 10), (239, 210, 18), 1024, 256)
    elif scene.slug == "zandvoort":
        sign(directory / "GroundMSC.png", "MSC CRUISES", (16, 27, 60), (241, 239, 226), 1024, 128)
    elif scene.slug == "portimao":
        sign(directory / "GroundAlgarve.png", "PORTIMÃO", (10, 10, 10), (241, 239, 226), 1024, 256)
    if scene.slug not in NIGHT:
        return
    fixtures = build_lighting(scene)
    samples = [scene.nearest(f.position[0], f.position[1])[0] for f in fixtures]
    lights = []
    for fixture, sample in zip(fixtures, samples, strict=True):
        lane = (fixture.position[0] - sample.x) * sample.ty - (fixture.position[1] - sample.y) * sample.tx
        target = fixture.target if fixture.target is not None else sample.point(
            min(1.5, sample.half_width * .2) * (1 if lane > 0 else -1))
        lights.append(world(target))
    if scene.slug == "jeddah":
        data = scene.data
        data.mkdir(parents=True, exist_ok=True)
        rows = ["x,y,z,target_x,target_y,target_z,power"]
        for fixture, target in zip(fixtures, lights, strict=True):
            rows.append(",".join(f"{value:.5f}" for value in (*world(fixture.position), *target, fixture.power)))
        (data / "night_lights.csv").write_text("\n".join(rows) + "\n")
    minimum_x = min(p[0] for p in lights) - 10000
    minimum_y = min(p[1] for p in lights) - 10000
    width = max(p[0] for p in lights) - minimum_x + 10000
    height = max(p[1] for p in lights) - minimum_y + 10000
    size = 2048
    radiance = np.zeros((size, size), dtype=np.float32)
    elevation = np.zeros((size, size), dtype=np.float32)
    for fixture, sample, (x, y, _z) in zip(fixtures, samples, lights, strict=True):
        along_radius = max(5.0, fixture.pool_radius_m * .55) * 100
        across_radius = max(4.0, fixture.pool_radius_m * .35) * 100
        reach = max(along_radius, across_radius) * 5
        c0 = max(0, int((x - reach - minimum_x) / width * size))
        c1 = min(size, int((x + reach - minimum_x) / width * size) + 1)
        r0 = max(0, int((y - reach - minimum_y) / height * size))
        r1 = min(size, int((y + reach - minimum_y) / height * size) + 1)
        dx = minimum_x + (np.arange(c0, c1) + 0.5) * width / size - x
        dy = minimum_y + (np.arange(r0, r1) + 0.5) * height / size - y
        along = -dx[None, :] * sample.ty - dy[:, None] * sample.tx
        across = dx[None, :] * sample.tx - dy[:, None] * sample.ty
        weight = fixture.power / (1 + (along / along_radius) ** 2 + (across / across_radius) ** 2) ** 1.5
        radiance[r0:r1, c0:c1] += weight
        elevation[r0:r1, c0:c1] += weight * sample.z * 100
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, 0] = np.rint(np.minimum(.65, radiance * 0.18) ** 2 * 255).astype(
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
                "method": "Reference-registered masts, head banks and cable fixtures aim elliptical pools onto the local road. Road-height registration, calibrated cone width and bounded accumulated radiance preserve night falloff; original diffuse field and private materials.",
            },
            indent=2,
        )
        + "\n"
    )
