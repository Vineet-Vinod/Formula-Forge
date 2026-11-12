"""The mapped ECP carriageways and exit ramp above the Flyer corner sequence."""

from __future__ import annotations

import gzip
import math
from pathlib import Path

from circuit_dataclasses import OsmData, Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union

SOURCES = Path(__file__).resolve().parents[2] / "Attribution/Sources/singapore"


def build_viaduct(scene: CircuitScene) -> None:
    payload = gzip.decompress((SOURCES / "flyer-viaduct.osm.json.gz").read_bytes())
    elements = TypeAdapter(OsmData).validate_json(payload).elements
    protected = unary_union([scene.corridor_mask, *scene.extra_corridors]).buffer(1.0)
    buildings = unary_union([Polygon(building.ring) for building in scene.buildings])
    water = unary_union(scene.water_shapes)
    road_z = scene.at(4290).z
    deck_top, soffit = road_z + 13., road_z + 12.1
    for element in elements:
        path = LineString([scene.geo(point.lat, point.lon) for point in element.geometry])
        lanes = int(element.tags["lanes"])
        width = lanes * 3.5 + 1.6
        footprint = path.buffer(width / 2, cap_style="flat", join_style="round")
        ground = footprint.difference(water).difference(buildings)
        pieces = [ground] if isinstance(ground, Polygon) else list(ground.geoms)
        for piece in pieces:
            if isinstance(piece, Polygon) and not piece.is_empty:
                scene.ground_patches.append((piece, road_z + .1, "Runoff"))

        def section(distance: float, reach: float, height: float, line: LineString = path) -> Point:
            center = line.interpolate(distance)
            before = line.interpolate(max(0., distance - 1))
            after = line.interpolate(min(line.length, distance + 1))
            span = max(1e-9, before.distance(after))
            return (center.x + (after.y - before.y) / span * reach,
                    center.y - (after.x - before.x) / span * reach, height)

        count = math.ceil(path.length / 3)
        for index in range(count):
            a, b = path.length * index / count, path.length * (index + 1) / count
            left_a, right_a = section(a, -width / 2, deck_top), section(a, width / 2, deck_top)
            left_b, right_b = section(b, -width / 2, deck_top), section(b, width / 2, deck_top)
            scene.quad("Building_ECPDeck", "Road", left_a, right_a, right_b, left_b, up=True)
            scene.quad("Building_ECPUnderside", "Concrete", add(left_a, (0, 0, -.9)),
                       add(left_b, (0, 0, -.9)), add(right_b, (0, 0, -.9)), add(right_a, (0, 0, -.9)), up=False)
            for side in (-1, 1):
                pa, pb = section(a, side * width / 2, soffit), section(b, side * width / 2, soffit)
                ta, tb = add(pa, (0, 0, .9)), add(pb, (0, 0, .9))
                if side < 0:
                    scene.quad("Building_ECPFascia", "Concrete", pa, ta, tb, pb)
                else:
                    scene.quad("Building_ECPFascia", "Concrete", pa, pb, tb, ta)
                scene.beam("Building_ECPParapets", "Concrete", section(a, side * (width / 2 - .22), deck_top + .55),
                           section(b, side * (width / 2 - .22), deck_top + .55), .42, 1.1)
                scene.beam("Building_ECPParapetCaps", "Steel", section(a, side * (width / 2 - .22), deck_top + 1.15),
                           section(b, side * (width / 2 - .22), deck_top + 1.15), .12)
            girders = max(3, round(width / 1.8))
            for girder in range(girders):
                reach = width * ((girder + .5) / girders - .5)
                scene.beam("Building_ECPLongitudinalGirders", "Concrete", section(a, reach, soffit - .30),
                           section(b, reach, soffit - .30), .28, .6)
        for distance in (0., path.length):
            a, b = section(distance, -width / 2, soffit), section(distance, width / 2, soffit)
            ta, tb = add(a, (0, 0, .9)), add(b, (0, 0, .9))
            if distance == 0:
                scene.quad("Building_ECPDeckEnds", "Concrete", a, b, tb, ta)
            else:
                scene.quad("Building_ECPDeckEnds", "Concrete", a, ta, tb, b)
        placed, omitted = 0, 0
        for distance in range(18, int(path.length) - 8, 32):
            center = section(distance, 0., 0.)
            arm_a, arm_b = section(distance, -width * .35, soffit - .25), section(distance, width * .35, soffit - .25)
            support = LineString([arm_a[:2], center[:2], arm_b[:2]]).buffer(1.0)
            if support.intersects(protected) or support.intersects(buildings.buffer(1)):
                omitted += 1
                continue
            if water.covers(ShapePoint(center[:2])):
                base = -5.2
            else:
                base = scene.ground(*center[:2])
            fork = center[0], center[1], soffit - 4.2
            scene.beam("Building_ECPPierShafts", "Concrete", (center[0], center[1], base), fork, 1.8, 2.0)
            scene.beam("Building_ECPPierForks", "Concrete", fork, arm_a, 1.15, 1.35)
            scene.beam("Building_ECPPierForks", "Concrete", fork, arm_b, 1.15, 1.35)
            scene.beam("Building_ECPPierHeads", "Concrete", arm_a, arm_b, 1.3, .6)
            placed += 1
        scene.landmarks.append({"name": "ECP Flyer viaduct " + str(element.id),
                                "osm_id": element.id, "lanes": lanes,
                                "deck_width_estimate_m": width,
                                "deck_top_m": deck_top, "soffit_m": soffit,
                                "lowest_girder_m": soffit - .6,
                                "pier_bays": placed, "pier_bays_omitted_at_protected_corridors": omitted,
                                "source_note": "Actual retained layer-1 ECP/Benjamin Sheares carriageway or Rochor Road exit alignment. Continuous supplied 1254–1255.8 s shows the closed concrete underside, repeated girders and forked supports. Lane width 3.5 m, combined shoulders 1.6 m, local deck 13 m above adjacent racing street, 0.9 m slab and 32 m support pitch are visual reconstruction estimates, not surveyed dimensions. Deck height uncertainty is ±3 m. Supports avoid every protected racing corridor and existing building. The known elevated-road DSM is replaced only beneath these actual deck footprints on land; ambiguous mall/layer-2 terrain is untouched."})
