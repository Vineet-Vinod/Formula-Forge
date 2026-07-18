"""Generate four original arcade racing vehicle families."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy

from asset_helpers import (add_wheel, bar, build_rigid_rig,
                           create_rig_action, cube, cylinder, empty,
                           export_asset, material, reset_scene, sphere, torus,
                           asset_objects)


VEHICLES = {
    "tidebreaker": {
        "display_name": "Tidebreaker XR",
        "family": "open beach buggy",
        "dimensions_target_m": [1.92, 4.02, 1.62],
        "paint": (0.04, 0.58, 0.70, 1),
        "accent": (1.00, 0.32, 0.08, 1),
    },
    "sunskipper": {
        "display_name": "Sunskipper GT",
        "family": "compact roadster",
        "dimensions_target_m": [1.78, 3.72, 1.28],
        "paint": (0.96, 0.67, 0.05, 1),
        "accent": (0.12, 0.32, 0.68, 1),
    },
    "reefrunner": {
        "display_name": "Reefrunner R4",
        "family": "rally hatch",
        "dimensions_target_m": [1.84, 3.94, 1.52],
        "paint": (0.80, 0.08, 0.12, 1),
        "accent": (0.94, 0.94, 0.88, 1),
    },
    "boardwalk": {
        "display_name": "Boardwalk Bruiser",
        "family": "surf utility coupe",
        "dimensions_target_m": [1.96, 4.18, 1.56],
        "paint": (0.18, 0.62, 0.26, 1),
        "accent": (0.94, 0.46, 0.10, 1),
    },
}

REQUIRED = ["car_root", "body", "wheel_FL", "wheel_FR", "wheel_RL",
            "wheel_RR", "steering", "brake_lights", "driver_mount",
            "vehicle_rig", "seat_anchor"]


def common_materials(spec):
    slug = spec["display_name"].split()[0].lower()
    return {
        "paint": material(f"{slug}_paint", spec["paint"], metallic=0.22, roughness=0.28),
        "accent": material(f"{slug}_accent", spec["accent"], metallic=0.08, roughness=0.32),
        "dark": material(f"{slug}_dark", (0.018, 0.024, 0.028, 1), metallic=0.2, roughness=0.38),
        "rubber": material(f"{slug}_rubber", (0.009, 0.011, 0.012, 1), roughness=0.78),
        "metal": material(f"{slug}_metal", (0.34, 0.39, 0.42, 1), metallic=0.82, roughness=0.21),
        "glass": material(f"{slug}_glass", (0.035, 0.15, 0.22, 0.78), metallic=0.05, roughness=0.12),
        "light": material(f"{slug}_lamp", (0.8, 0.9, 1, 1), roughness=0.14,
                          emission=(0.7, 0.88, 1), emission_strength=4.0),
        "brake": material(f"{slug}_brake", (0.52, 0.006, 0.004, 1), roughness=0.2,
                          emission=(1, 0.005, 0.002), emission_strength=5.0),
        "tan": material(f"{slug}_tan", (0.48, 0.23, 0.08, 1), roughness=0.54),
    }


def build_vehicle(slug: str):
    reset_scene()
    spec = VEHICLES[slug]
    mats = common_materials(spec)
    root = empty("car_root")
    root["asset_id"] = f"formula_buggy.vehicle.{slug}"
    root["units"] = "meters"
    body = empty("body", owner=root)
    steering = empty("steering", (0, -0.30, 1.00), root)
    brakes = empty("brake_lights", owner=root)
    # This Blender-space anchor becomes approximately (0, 1.0, -0.1) after
    # glTF's Z-up/-Y-front to Y-up/+Z-front axis conversion.
    driver_mount = empty("driver_mount", (0, 0.10, 1.00), root)

    if slug == "tidebreaker":
        wheel_radius, wheel_width = 0.42, 0.28
        cube("floorpan", (0, 0.10, 0.50), (1.48, 2.58, 0.28), mats["paint"], body, 0.16)
        cube("nose", (0, -1.43, 0.66), (1.46, 0.76, 0.48), mats["paint"], body, 0.17)
        cube("front_grille", (0, -1.825, 0.63), (0.64, 0.035, 0.17), mats["dark"], body, 0.025)
        cube("rear_deck", (0, 1.33, 0.68), (1.42, 0.72, 0.55), mats["accent"], body, 0.13)
        cube("front_bash", (0, -1.91, 0.46), (1.42, 0.16, 0.16), mats["metal"], body, 0.05)
        cube("rear_bash", (0, 1.96, 0.49), (1.34, 0.14, 0.14), mats["metal"], body, 0.045)
        for x in (-0.68, 0.68):
            bar(f"roll_side_{x:+}", (x, 0.72, 0.58), (x, 0.34, 1.55), 0.055, mats["metal"], body)
            bar(f"roll_back_{x:+}", (x, 0.34, 1.55), (x, 1.00, 1.02), 0.055, mats["metal"], body)
        bar("roll_cross", (-0.68, 0.34, 1.55), (0.68, 0.34, 1.55), 0.055, mats["metal"], body)
        cube("seat_L", (-0.36, 0.35, 0.82), (0.52, 0.64, 0.65), mats["dark"], body, 0.12)
        cube("seat_R", (0.36, 0.35, 0.82), (0.52, 0.64, 0.65), mats["dark"], body, 0.12)
        for x in (-0.48, 0.48):
            sphere(f"headlamp_{x:+}", (x, -1.78, 0.79), (0.18, 0.12, 0.18), mats["light"], body)
        positions = {"wheel_FL": (-0.82, -1.20, 0.46), "wheel_FR": (0.82, -1.20, 0.46),
                     "wheel_RL": (-0.82, 1.17, 0.46), "wheel_RR": (0.82, 1.17, 0.46)}
    elif slug == "sunskipper":
        wheel_radius, wheel_width = 0.36, 0.22
        cube("lower_body", (0, 0.03, 0.48), (1.62, 3.18, 0.48), mats["paint"], body, 0.19)
        cube("sculpted_hood", (0, -1.30, 0.70), (1.44, 1.02, 0.34), mats["paint"], body, 0.15)
        cube("front_grille", (0, -1.575, 0.46), (0.70, 0.035, 0.14), mats["dark"], body, 0.025)
        cube("hood_accent", (0, -1.31, 0.875), (0.25, 0.82, 0.025), mats["accent"], body, 0.01)
        cube("rear_haunch", (0, 1.05, 0.70), (1.56, 0.92, 0.38), mats["paint"], body, 0.16)
        cube("cockpit", (0, 0.18, 0.90), (1.16, 1.18, 0.42), mats["dark"], body, 0.15)
        cube("windscreen", (0, -0.35, 1.10), (1.05, 0.08, 0.38), mats["glass"], body, 0.035).rotation_euler.x = math.radians(-18)
        cube("rear_spoiler", (0, 1.65, 1.01), (1.40, 0.25, 0.10), mats["accent"], body, 0.04)
        cube("rear_diffuser", (0, 1.85, 0.35), (1.34, 0.14, 0.12), mats["dark"], body, 0.035)
        for x in (-0.54, 0.54):
            bar(f"spoiler_post_{x:+}", (x, 1.52, 0.76), (x, 1.62, 0.98), 0.035, mats["dark"], body)
            sphere(f"headlamp_{x:+}", (x, -1.72, 0.65), (0.22, 0.08, 0.11), mats["light"], body)
        positions = {"wheel_FL": (-0.77, -1.14, 0.38), "wheel_FR": (0.77, -1.14, 0.38),
                     "wheel_RL": (-0.77, 1.15, 0.38), "wheel_RR": (0.77, 1.15, 0.38)}
    elif slug == "reefrunner":
        wheel_radius, wheel_width = 0.38, 0.24
        cube("lower_body", (0, 0.05, 0.56), (1.66, 3.28, 0.56), mats["paint"], body, 0.16)
        cube("hood", (0, -1.30, 0.84), (1.50, 0.90, 0.34), mats["paint"], body, 0.12)
        cube("front_grille", (0, -1.605, 0.61), (0.76, 0.035, 0.19), mats["dark"], body, 0.025)
        cube("cabin", (0, 0.28, 1.06), (1.44, 1.72, 0.88), mats["paint"], body, 0.17)
        cube("windscreen", (0, -0.61, 1.22), (1.24, 0.08, 0.54), mats["glass"], body, 0.03).rotation_euler.x = math.radians(-12)
        cube("roof_rack", (0, 0.31, 1.53), (1.34, 1.30, 0.07), mats["dark"], body, 0.02)
        for x in (-0.48, 0, 0.48):
            sphere(f"rally_lamp_{x:+}", (x, -1.68, 0.83), (0.15, 0.09, 0.15), mats["light"], body)
        cube("front_skid", (0, -1.86, 0.43), (1.26, 0.20, 0.12), mats["metal"], body, 0.04)
        cube("rear_skid", (0, 1.91, 0.43), (1.28, 0.14, 0.12), mats["metal"], body, 0.035)
        cube("stripe", (0, -0.12, 1.52), (0.34, 1.72, 0.035), mats["accent"], body, 0.01)
        positions = {"wheel_FL": (-0.80, -1.18, 0.41), "wheel_FR": (0.80, -1.18, 0.41),
                     "wheel_RL": (-0.80, 1.20, 0.41), "wheel_RR": (0.80, 1.20, 0.41)}
    else:
        wheel_radius, wheel_width = 0.40, 0.27
        cube("lower_body", (0, 0.08, 0.56), (1.72, 3.76, 0.60), mats["paint"], body, 0.17)
        cube("power_hood", (0, -1.38, 0.88), (1.54, 0.90, 0.42), mats["paint"], body, 0.12)
        cube("front_grille", (0, -1.835, 0.61), (0.74, 0.035, 0.17), mats["dark"], body, 0.025)
        cube("rear_bumper", (0, 2.10, 0.47), (1.48, 0.18, 0.15), mats["dark"], body, 0.045)
        cube("cab", (0, 0.20, 1.10), (1.54, 1.50, 0.88), mats["paint"], body, 0.15)
        cube("windscreen", (0, -0.58, 1.27), (1.31, 0.09, 0.53), mats["glass"], body, 0.03).rotation_euler.x = math.radians(-9)
        for x in (-0.875, 0.875):
            cube(f"wood_panel_{x:+}", (x, 0.38, 0.71), (0.035, 1.68, 0.30), mats["tan"], body, 0.012)
        # A short original foam surf board makes the silhouette instantly readable.
        board = cube("roof_board", (0, 0.24, 1.61), (0.55, 2.10, 0.10), mats["accent"], body, 0.05)
        board.rotation_euler.z = math.radians(4)
        for y in (-0.36, 0.66):
            bar(f"rack_{y:+}", (-0.76, y, 1.50), (0.76, y, 1.50), 0.035, mats["dark"], body)
        for x in (-0.52, 0.52):
            sphere(f"headlamp_{x:+}", (x, -1.84, 0.83), (0.19, 0.10, 0.15), mats["light"], body)
        positions = {"wheel_FL": (-0.84, -1.22, 0.43), "wheel_FR": (0.84, -1.22, 0.43),
                     "wheel_RL": (-0.84, 1.26, 0.43), "wheel_RR": (0.84, 1.26, 0.43)}

    wheels = {}
    for name, pos in positions.items():
        pivot, tire = add_wheel(name, pos, wheel_radius, wheel_width, root,
                                mats["rubber"], mats["metal"])
        wheels[name] = pivot
    # Steering wheel belongs to the steering pivot and turns with the front axle.
    torus("steering_wheel", (0, 0, 0), 0.18, 0.025, mats["dark"], steering,
          rotation=(math.radians(68), 0, 0))
    for x in (-0.48, 0.48):
        cube(f"brake_{x:+}", (x, 1.76 if slug != "tidebreaker" else 1.70, 0.72),
             (0.27, 0.07, 0.14), mats["brake"], brakes, 0.025)

    bone_specs = {
        "rig_root": {"head": (0, 0, 0), "tail": (0, 0, 0.25)},
        "body_anim": {"head": (0, 0, 0.55), "tail": (0, 0, 0.9), "parent": "rig_root"},
        "wheel_FL_anim": {"head": positions["wheel_FL"], "parent": "rig_root"},
        "wheel_FR_anim": {"head": positions["wheel_FR"], "parent": "rig_root"},
        "wheel_RL_anim": {"head": positions["wheel_RL"], "parent": "rig_root"},
        "wheel_RR_anim": {"head": positions["wheel_RR"], "parent": "rig_root"},
        "steering_anim": {"head": tuple(steering.location), "parent": "body_anim"},
        "brake_lights_anim": {"head": (0, 1.70, 0.72), "parent": "body_anim"},
        "seat_anchor": {"head": (0, 0.10, 1.00), "tail": (0, -0.10, 1.00),
                        "parent": "body_anim"},
    }

    def group_for_object(obj):
        current = obj
        while current:
            if current.name.startswith("wheel_FL"):
                return "wheel_FL_anim"
            if current.name.startswith("wheel_FR"):
                return "wheel_FR_anim"
            if current.name.startswith("wheel_RL"):
                return "wheel_RL_anim"
            if current.name.startswith("wheel_RR"):
                return "wheel_RR_anim"
            if current.name == "steering":
                return "steering_anim"
            if current.name == "brake_lights":
                return "brake_lights_anim"
            current = current.parent
        return "body_anim"

    rig = build_rigid_rig("vehicle_rig", bone_specs, asset_objects(), root,
                          group_for_object)
    wheel_channels = [
        {"bone": f"{name}_anim", "index": 0,
         "keys": [(1, 0), (24, -math.tau * 2.5)]}
        for name in ("wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR")
    ]
    create_rig_action(rig, "accelerate", (1, 24), wheel_channels)
    create_rig_action(rig, "brake", (60, 72), [
        {"bone": "body_anim", "index": 0,
         "keys": [(60, 0), (66, math.radians(-3.5)), (72, 0)]},
        {"bone": "brake_lights_anim", "path": "scale", "index": 0,
         "keys": [(60, 1), (64, 1.18), (69, 1.18), (72, 1)]},
    ])
    for clip, sign in (("turn_left", 1), ("turn_right", -1)):
        create_rig_action(rig, clip, (30, 50), [
            {"bone": "wheel_FL_anim", "index": 2,
             "keys": [(30, 0), (40, sign * math.radians(24)), (50, 0)]},
            {"bone": "wheel_FR_anim", "index": 2,
             "keys": [(30, 0), (40, sign * math.radians(24)), (50, 0)]},
            {"bone": "steering_anim", "index": 1,
             "keys": [(30, 0), (40, sign * math.radians(52)), (50, 0)]},
        ])
    create_rig_action(rig, "idle", (80, 108), [
        {"bone": "body_anim", "path": "location", "index": 2,
         "keys": [(80, 0), (94, 0.012), (108, 0)]},
    ])

    return spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=["all", *VEHICLES], default="all")
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "assets_src" / "vehicles")
    args = parser.parse_args()
    targets = VEHICLES if args.asset == "all" else [args.asset]
    for slug in targets:
        spec = build_vehicle(slug)
        metadata = {
            "type": "vehicle",
            "display_name": spec["display_name"],
            "family": spec["family"],
            "target_dimensions_m": {"width_x": spec["dimensions_target_m"][0],
                                    "length_y": spec["dimensions_target_m"][1],
                                    "height_z": spec["dimensions_target_m"][2]},
            "animation_clips": {"accelerate": [1, 24], "turn_left": [30, 50],
                                "turn_right": [30, 50], "brake": [60, 72],
                                "idle": [80, 108]},
            "mounts": {"driver_object": "driver_mount", "driver_bone": "seat_anchor",
                       "gltf_local_y_up_z_forward_m": [0.0, 1.0, -0.1]},
        }
        export_asset(args.output_root / slug, slug, metadata, REQUIRED,
                     (5.4, -6.8, 3.4), (0, 0, 0.70))


if __name__ == "__main__":
    main()
