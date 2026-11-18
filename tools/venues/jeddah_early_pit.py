"""Source608–611 STC wall, privacy screens and bridge before the Qatar chicane."""

import hashlib
from pathlib import Path

from circuit_mesh import MeshScene, add, mul, norm, sub
from pit_routes_dataclasses import PitRoute
from pydantic import TypeAdapter

from venues.jeddah_early_pit_dataclasses import EarlyPit
from venues.jeddah_pit_protection import sections_hash

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah/pit-early-corridor.json"


def load_recipe(route: PitRoute) -> EarlyPit:
    recipe = TypeAdapter(EarlyPit).validate_json(SOURCE.read_bytes())
    road = SOURCE.parents[3] / "build/circuits/jeddah/road.csv"
    if hashlib.sha256(road.read_bytes()).hexdigest() != recipe.source_road_sha256 or sections_hash(route) != recipe.source_sections_sha256:
        raise ValueError("Rebind the early pit corridor to the current road and pit sections")
    return recipe


def emit_details(scene: MeshScene, recipe: EarlyPit) -> None:
    for face in recipe.floors:
        scene.triangle("Tile_Route", "Runoff", face.a, face.b, face.c,
                       uv=tuple((p[0] / 4, p[1] / 4) for p in (face.a, face.b, face.c)))
    phase = 0.
    for record in recipe.walls:
        wall = record.barrier
        along = norm((wall.bx - wall.ax, wall.by - wall.ay, 0.))
        # The chain follows the garage/outer side; source-right faces the lane.
        inward = along[1], -along[0], 0.
        a, b = (wall.ax, wall.ay, wall.bottom + .05), (wall.bx, wall.by, wall.bottom + .05)
        face_a, face_b = add(a, mul(inward, .165)), add(b, mul(inward, .165))
        length = ((wall.bx - wall.ax) ** 2 + (wall.by - wall.ay) ** 2) ** .5
        scene.banner(add(face_a, (0, 0, .08)), add(face_b, (0, 0, .08)), .8,
                     record.material, "Tile_Route", phase / 6.4, length / 6.4)
        if record.privacy:
            outer_a, outer_b = add(a, mul(inward, -.35)), add(b, mul(inward, -.35))
            scene.banner(add(outer_a, (0, 0, 1.0)), add(outer_b, (0, 0, 1.0)),
                         3.2, "White", "Building_JeddahPitPrivacy")
            scene.beam("Building_JeddahPitPrivacyFrame", "Steel", outer_a,
                       add(outer_a, (0, 0, 4.2)), .055)
            for height in (1., 4.2):
                scene.beam("Building_JeddahPitPrivacyFrame", "Steel", add(outer_a, (0, 0, height)),
                           add(outer_b, (0, 0, height)), .055)
        phase += length
    bridge = recipe.bridge
    along = norm(sub(bridge.right, bridge.left))
    normal = -along[1], along[0], 0.
    top_z = max(bridge.left[2], bridge.right[2]) + bridge.underside_m
    left, right = (bridge.left[0], bridge.left[1], top_z), (bridge.right[0], bridge.right[1], top_z)
    for foot, top in ((bridge.left, left), (bridge.right, right)):
        scene.beam("Building_JeddahSTCBridgeColumns", "White", add(foot, (0, 0, .95)),
                   add(top, (0, 0, bridge.panel_height_m)), .22)
    for depth in (-.5, .5):
        a, b = add(left, mul(normal, depth)), add(right, mul(normal, depth))
        scene.beam("Building_JeddahSTCBridgeFrame", "Steel", a, b, .18)
        scene.beam("Building_JeddahSTCBridgeFrame", "Steel", add(a, (0, 0, bridge.panel_height_m)),
                   add(b, (0, 0, bridge.panel_height_m)), .18)
    scene.banner(add(left, mul(normal, -.55)), add(right, mul(normal, -.55)),
                 bridge.panel_height_m, "PanelJeddahPitBridgeStc", "Building_JeddahSTCBridgePanel", repeat=3)
    for i in range(12):
        a = add(left, mul(sub(right, left), i / 12))
        b = add(left, mul(sub(right, left), (i + 1) / 12))
        scene.beam("Building_JeddahSTCBridgeBracing", "Steel", add(a, mul(normal, .45)),
                   add(add(b, mul(normal, .45)), (0, 0, bridge.panel_height_m)), .07)
    scene.beam("Building_JeddahSTCBridgeSoffit", "White", left, right, 1.0, .14)
