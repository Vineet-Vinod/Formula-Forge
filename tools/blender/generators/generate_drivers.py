"""Generate the single anonymous Standard Driver used by every car."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from asset_helpers import (ASSET_PROP, asset_objects, bar, build_rigid_rig,
                           cone, create_rig_action, cube, cylinder, empty,
                           export_asset, material, reset_scene, sphere, torus)
import bpy
from mathutils import Vector


DRIVERS = {
    "standard_driver": {
        "display_name": "Standard Driver",
        "silhouette": "realistic-proportioned helmeted formula racing driver",
        "suit": (0.018, 0.035, 0.075, 1),
        "accent": (0.96, 0.22, 0.025, 1),
    },
}

REQUIRED = ["driver_root", "root", "head", "arm_L", "arm_R",
            "driver_rig", "driver_root_bone", "head_bone", "arm_L_bone",
            "arm_R_bone"]


def curved_helmet_panel(name, center, radius_x, radius_y, height,
                        sweep_degrees, thickness, edge_taper, mat, owner,
                        segments=18):
    """Build a thin wraparound panel conforming to the helmet ellipsoid."""
    vertices = []
    sweep = math.radians(sweep_degrees)
    for layer in range(2):
        inset = layer * thickness
        for index in range(segments + 1):
            angle = -sweep + 2.0 * sweep * index / segments
            edge = abs(angle / sweep) ** 1.6
            half_height = height * 0.5 - edge_taper * edge
            layer_radius_x = radius_x - inset
            layer_radius_y = radius_y - inset
            x = center[0] + layer_radius_x * math.sin(angle)
            y = center[1] - layer_radius_y * math.cos(angle)
            vertices.extend(((x, y, center[2] - half_height),
                             (x, y, center[2] + half_height)))

    stride = (segments + 1) * 2
    faces = []
    for index in range(segments):
        outer = index * 2
        outer_next = outer + 2
        inner = stride + outer
        inner_next = inner + 2
        faces.extend((
            (outer, outer_next, outer_next + 1, outer + 1),
            (inner + 1, inner_next + 1, inner_next, inner),
            (outer + 1, outer_next + 1, inner_next + 1, inner + 1),
            (outer, inner, inner_next, outer_next),
        ))
    faces.extend(((0, 1, stride + 1, stride),
                  (segments * 2, stride + segments * 2,
                   stride + segments * 2 + 1, segments * 2 + 1)))

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj[ASSET_PROP] = True
    obj.data.materials.append(mat)
    obj.parent = owner
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def tapered_bar(name, start, end, start_radius, end_radius, mat, owner):
    """Create a low-cost tapered limb segment between two authored points."""
    start_v, end_v = Vector(start), Vector(end)
    direction = end_v - start_v
    obj = cone(name, (start_v + end_v) * 0.5,
               start_radius, end_radius, direction.length,
               mat, owner, vertices=16)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return obj


def make_standard_driver(torso, head, arm_l, arm_r, leg_l, leg_r, mats):
    """Build a logo-free modern Formula driver in a compact seated pose."""
    # Close-cut multi-layer overalls: shaped ribcage and waist, high collar,
    # shoulder epaulettes, front zip and restrained contrast seams. Modern F1
    # racewear reads as fabric rather than body armour.
    sphere("torso_shell", (0, 0.012, 0.090), (0.250, 0.142, 0.270),
           mats["suit"], torso, 22, 14)
    sphere("waist", (0, 0.020, -0.128), (0.192, 0.118, 0.145),
           mats["suit"], torso, 18, 10)
    cylinder("suit_collar", (0, -0.002, 0.350), 0.075, 0.075,
             mats["suit_detail"], torso, vertices=20, bevel=0.012)
    cube("suit_zipper", (0, -0.143, 0.105), (0.012, 0.010, 0.270),
         mats["zipper"], torso, 0.004)
    cube("waist_seam", (0, -0.120, -0.095), (0.335, 0.012, 0.018),
         mats["accent"], torso, 0.004)
    for side in (-1, 1):
        bar(f"chest_seam_{side:+}", (side * 0.170, -0.126, 0.270),
            (side * 0.105, -0.147, -0.055), 0.007,
            mats["accent"], torso)
        cube(f"shoulder_epaulette_{side:+}",
             (side * 0.198, -0.060, 0.270),
             (0.090, 0.082, 0.018), mats["suit_detail"], torso, 0.007)
        bar(f"shoulder_piping_{side:+}",
            (side * 0.232, -0.100, 0.255),
            (side * 0.155, -0.138, 0.210), 0.008,
            mats["accent"], torso)

    # The black HANS/FHR yoke sits over the shoulders with short forward legs;
    # it is visually separate from the suit and tucked under the helmet.
    torus("hans_collar", (0, 0.018, 0.330), 0.094, 0.024,
          mats["hans"], torso, major_segments=20, minor_segments=6)
    for side in (-1, 1):
        bar(f"hans_leg_{side:+}", (side * 0.077, 0.000, 0.325),
            (side * 0.105, -0.123, 0.258), 0.022,
            mats["hans"], torso)

    # Full-face Formula helmet based on the reference's construction: a glossy
    # domed crown, a separate light lower shell, a broad wraparound visor and
    # an angular chin bar. Graphics remain generic and sponsor-free.
    sphere("helmet_shell", (0, 0.005, 0.115), (0.150, 0.132, 0.178),
           mats["helmet_red"], head, 22, 14)
    # One continuous lower shell replaces the former overlapping chin pieces,
    # which read as a protruding mouth. Its forward ellipse meets the visor and
    # tapers smoothly back toward the neck.
    sphere("helmet_lower_shell", (0, -0.015, 0.015),
           (0.138, 0.130, 0.122), mats["helmet_white"], head, 22, 12)

    # The visor and its upper reinforcement are continuous curved meshes that
    # track the crown radius from cheek to cheek.
    curved_helmet_panel("helmet_visor", (0, 0.004, 0.112),
                        0.140, 0.137, 0.078, 67, 0.006, 0.012,
                        mats["visor"], head, segments=20)
    curved_helmet_panel("visor_reinforcement", (0, 0.004, 0.157),
                        0.143, 0.140, 0.012, 68, 0.005, 0.001,
                        mats["helmet_white"], head, segments=20)
    for side in (-1, 1):
        cylinder(f"helmet_hinge_{side:+}", (side * 0.145, -0.050, 0.112),
                 0.023, 0.014, mats["visor_trim"], head,
                 rotation=(0, math.pi / 2, 0), vertices=16, bevel=0.003)
        bar(f"helmet_cheek_line_{side:+}",
            (side * 0.118, -0.112, 0.050),
            (side * 0.086, -0.144, -0.040), 0.006,
            mats["helmet_blue"], head)
    bar("helmet_rear_spoiler", (-0.090, 0.130, 0.125),
        (0.090, 0.130, 0.125), 0.010, mats["helmet_red"], head)

    # Tapered sleeves, subtle elbow folds and gauntlet gloves. Hands converge
    # on the common steering-wheel hard point shared by all five cars.
    for side, arm in ((-1, arm_l), (1, arm_r)):
        shoulder = (0, 0, 0.065)
        elbow = (side * 0.035, -0.190, -0.025)
        wrist = (-side * 0.128, -0.360, -0.082)
        hand = (-side * 0.145, -0.405, -0.090)
        sphere(f"shoulder_{side:+}", shoulder,
               (0.058, 0.061, 0.070), mats["suit"], arm, 16, 10)
        tapered_bar(f"upper_arm_{side:+}", shoulder, elbow,
                    0.052, 0.046, mats["suit"], arm)
        sphere(f"elbow_fold_{side:+}", elbow,
               (0.049, 0.046, 0.050), mats["suit_shadow"], arm, 14, 8)
        tapered_bar(f"forearm_{side:+}", elbow, wrist,
                    0.046, 0.039, mats["suit"], arm)
        tapered_bar(f"glove_cuff_{side:+}", wrist, hand,
                    0.049, 0.043, mats["gloves"], arm)
        sphere(f"glove_{side:+}", hand, (0.049, 0.039, 0.051),
               mats["gloves"], arm, 16, 10)
        cube(f"glove_top_panel_{side:+}",
             (hand[0], hand[1] - 0.020, hand[2] + 0.022),
             (0.058, 0.014, 0.045), mats["accent"], arm, 0.006)

    # The legs keep a realistic pedal-box bend. Boots are slim, flat-soled
    # fireproof driving shoes rather than the square blocks from the first pass.
    for side, leg in ((-1, leg_l), (1, leg_r)):
        hip = (0, 0, 0.075)
        knee = (0, -0.300, -0.105)
        ankle = (0, -0.500, -0.310)
        toe = (0, -0.635, -0.370)
        tapered_bar(f"thigh_{side:+}", hip, knee,
                    0.086, 0.072, mats["suit"], leg)
        sphere(f"knee_panel_{side:+}", knee,
               (0.078, 0.070, 0.076), mats["suit_shadow"], leg, 16, 10)
        tapered_bar(f"shin_{side:+}", knee, ankle,
                    0.068, 0.052, mats["suit"], leg)
        tapered_bar(f"boot_ankle_{side:+}", ankle, toe,
                    0.053, 0.046, mats["boots"], leg)
        sphere(f"boot_{side:+}", (0, -0.620, -0.390),
               (0.064, 0.112, 0.050), mats["boots"], leg, 18, 10)
        cube(f"boot_sole_{side:+}", (0, -0.620, -0.438),
             (0.128, 0.220, 0.020), mats["sole"], leg, 0.006)
        bar(f"leg_piping_{side:+}",
            (side * 0.060, -0.080, 0.035),
            (side * 0.052, -0.438, -0.270), 0.007,
            mats["accent"], leg)


def add_standard_driver_preview_context(mats):
    """Add a non-exported seat and wheel so the authored pose reads clearly."""
    seat_back = cube("PREVIEW_seat_back", (0, 0.115, -0.015),
                     (0.42, 0.10, 0.62), mats["preview_dark"], bevel=0.065)
    seat_back.rotation_euler.x = math.radians(-8)
    seat_base = cube("PREVIEW_seat_base", (0, 0.035, -0.325),
                     (0.40, 0.44, 0.10), mats["preview_dark"], bevel=0.045)
    wheel = torus("PREVIEW_steering_wheel", (0, -0.355, 0.105),
                  0.135, 0.016, mats["preview_dark"],
                  rotation=(math.radians(68), 0, 0),
                  major_segments=20, minor_segments=6)
    column = bar("PREVIEW_steering_column", (0, -0.34, 0.09),
                 (0, -0.04, -0.10), 0.014, mats["zipper"])
    for obj in (seat_back, seat_base, wheel, column):
        obj[ASSET_PROP] = False


def build_driver(slug: str):
    reset_scene()
    spec = DRIVERS[slug]
    mats = {
        "suit": material(f"{slug}_suit", spec["suit"], roughness=0.72),
        "suit_detail": material(f"{slug}_suit_detail", (0.76, 0.80, 0.82, 1),
                                roughness=0.70),
        "suit_shadow": material(f"{slug}_suit_shadow", (0.028, 0.055, 0.105, 1),
                                roughness=0.76),
        "accent": material(f"{slug}_accent", spec["accent"], roughness=0.55),
        "zipper": material(f"{slug}_zipper", (0.18, 0.20, 0.22, 1),
                           metallic=0.38, roughness=0.34),
        "hans": material(f"{slug}_hans", (0.010, 0.012, 0.016, 1),
                         roughness=0.32),
        "helmet_red": material(f"{slug}_helmet_red", (0.72, 0.012, 0.020, 1),
                               metallic=0.06, roughness=0.16),
        "helmet_white": material(f"{slug}_helmet_white", (0.88, 0.90, 0.91, 1),
                                 metallic=0.05, roughness=0.20),
        "helmet_blue": material(f"{slug}_helmet_blue", (0.015, 0.24, 0.50, 1),
                                metallic=0.08, roughness=0.22),
        "visor": material(f"{slug}_visor", (0.006, 0.012, 0.020, 1),
                          metallic=0.45, roughness=0.08),
        "visor_trim": material(f"{slug}_visor_trim", (0.025, 0.028, 0.032, 1),
                               metallic=0.48, roughness=0.20),
        "gloves": material(f"{slug}_gloves", (0.010, 0.013, 0.018, 1),
                           roughness=0.62),
        "boots": material(f"{slug}_boots", (0.014, 0.018, 0.024, 1),
                          roughness=0.66),
        "sole": material(f"{slug}_sole", (0.004, 0.005, 0.006, 1),
                         roughness=0.82),
        "preview_dark": material(f"{slug}_preview_dark", (0.010, 0.013, 0.017, 1),
                                 roughness=0.52),
    }
    driver_root = empty("driver_root")
    driver_root["asset_id"] = f"formula_forge.driver.{slug}"
    driver_root["attach_to"] = "seat_anchor"
    root = empty("root", owner=driver_root)
    torso = empty("torso", (0, 0, 0.12), root)
    head = empty("head", (0, -0.02, 0.47), root)
    arm_x = 0.28
    arm_l = empty("arm_L", (-arm_x, -0.02, 0.25), root)
    arm_r = empty("arm_R", (arm_x, -0.02, 0.25), root)
    leg_l = empty("leg_L", (-0.145, 0, -0.08), root)
    leg_r = empty("leg_R", (0.145, 0, -0.08), root)

    make_standard_driver(torso, head, arm_l, arm_r, leg_l, leg_r, mats)

    bones = {
        "driver_root_bone": {"head": (0, 0, 0), "tail": (0, 0, 0.18)},
        "torso_bone": {"head": (0, 0, 0.05), "tail": (0, 0, 0.38), "parent": "driver_root_bone"},
        "head_bone": {"head": (0, -0.02, 0.38), "tail": (0, -0.02, 0.61), "parent": "torso_bone"},
        "arm_L_bone": {"head": (-arm_x, -0.02, 0.25), "tail": (-arm_x - 0.07, -0.22, 0.10), "parent": "torso_bone"},
        "arm_R_bone": {"head": (arm_x, -0.02, 0.25), "tail": (arm_x + 0.07, -0.22, 0.10), "parent": "torso_bone"},
        "leg_L_bone": {"head": (-0.145, 0, -0.08), "tail": (-0.145, -0.30, -0.22), "parent": "driver_root_bone"},
        "leg_R_bone": {"head": (0.145, 0, -0.08), "tail": (0.145, -0.30, -0.22), "parent": "driver_root_bone"},
    }

    def group_for_object(obj):
        current = obj
        while current:
            mapping = {"head": "head_bone", "arm_L": "arm_L_bone", "arm_R": "arm_R_bone",
                       "leg_L": "leg_L_bone", "leg_R": "leg_R_bone", "torso": "torso_bone"}
            if current.name in mapping:
                return mapping[current.name]
            current = current.parent
        return "driver_root_bone"

    rig = build_rigid_rig("driver_rig", bones, asset_objects(), driver_root,
                          group_for_object)
    create_rig_action(rig, "idle", (1, 32), [
        {"bone": "torso_bone", "path": "location", "index": 2,
         "keys": [(1, 0), (16, 0.008), (32, 0)]},
        {"bone": "head_bone", "index": 2,
         "keys": [(1, math.radians(-1)), (16, math.radians(1)), (32, math.radians(-1))]},
    ])
    create_rig_action(rig, "accelerate", (40, 54), [
        {"bone": "torso_bone", "index": 0,
         "keys": [(40, 0), (47, math.radians(5)), (54, 0)]},
        {"bone": "head_bone", "index": 0,
         "keys": [(40, 0), (47, math.radians(-3)), (54, 0)]},
    ])
    create_rig_action(rig, "brake", (60, 74), [
        {"bone": "torso_bone", "index": 0,
         "keys": [(60, 0), (67, math.radians(-7)), (74, 0)]},
        {"bone": "head_bone", "index": 0,
         "keys": [(60, 0), (67, math.radians(4)), (74, 0)]},
    ])
    for clip, sign in (("turn_left", 1), ("turn_right", -1)):
        create_rig_action(rig, clip, (80, 100), [
            {"bone": "torso_bone", "index": 1,
             "keys": [(80, 0), (90, sign * math.radians(4)), (100, 0)]},
            {"bone": "head_bone", "index": 2,
             "keys": [(80, 0), (90, sign * math.radians(10)), (100, 0)]},
            {"bone": "arm_L_bone", "index": 2,
             "keys": [(80, 0), (90, sign * math.radians(12)), (100, 0)]},
            {"bone": "arm_R_bone", "index": 2,
             "keys": [(80, 0), (90, sign * math.radians(12)), (100, 0)]},
        ])
    # A common compact seated envelope keeps every silhouette compatible with
    # the same vehicle seat anchor while preserving proportions.
    driver_root.scale = (0.82, 0.82, 0.82)
    add_standard_driver_preview_context(mats)
    return spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=["all", *DRIVERS], default="all")
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "assets" / "drivers")
    args = parser.parse_args()
    targets = DRIVERS if args.asset == "all" else [args.asset]
    for slug in targets:
        spec = build_driver(slug)
        metadata = {
            "type": "driver",
            "display_name": spec["display_name"],
            "silhouette": spec["silhouette"],
            "design_style": "realistic modern formula driver",
            "target_seated_pose_height_m": 1.1,
            "target_dimensions_m": {"width_x": 0.60, "depth_y": 0.72,
                                    "seated_height_z": 1.05},
            "attachment": {"driver_origin": "pelvis", "vehicle_bone": "seat_anchor"},
            "animation_clips": {"idle": [1, 32], "accelerate": [40, 54],
                                "brake": [60, 74], "turn_left": [80, 100],
                                "turn_right": [80, 100]},
        }
        camera = (1.95, -2.90, 1.42)
        target = (0, -0.15, 0.05)
        export_asset(args.output_root / slug, slug, metadata, REQUIRED,
                     camera, target)


if __name__ == "__main__":
    main()
