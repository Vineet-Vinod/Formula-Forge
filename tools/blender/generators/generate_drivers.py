"""Generate six original human-like arcade racing drivers."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from asset_helpers import (ASSET_PROP, asset_objects, bar, build_rigid_rig, cone,
                           create_rig_action, cube, cylinder, empty,
                           export_asset, material, reset_scene, sphere, torus)


DRIVERS = {
    "imani_reef": {
        "display_name": "Imani Reef",
        "silhouette": "realistic human racing driver with twin buns",
        "skin": (0.24, 0.085, 0.042, 1),
        "shirt": (0.018, 0.045, 0.085, 1),
        "accent": (0.015, 0.64, 0.56, 1),
        "hair": (0.012, 0.006, 0.004, 1),
        "feature": "buns", "realistic": True,
    },
    "dax_calder": {
        "display_name": "Dax Calder", "silhouette": "mohawk mechanic",
        "skin": (0.48, 0.23, 0.12, 1), "shirt": (0.08, 0.22, 0.52, 1),
        "accent": (0.94, 0.82, 0.08, 1), "hair": (0.04, 0.025, 0.015, 1),
        "feature": "mohawk",
    },
    "marina_quill": {
        "display_name": "Marina Quill", "silhouette": "visor-wearing coastal ace",
        "skin": (0.76, 0.46, 0.28, 1), "shirt": (0.72, 0.08, 0.20, 1),
        "accent": (0.10, 0.66, 0.84, 1), "hair": (0.12, 0.045, 0.018, 1),
        "feature": "visor",
    },
    "niko_brass": {
        "display_name": "Niko Brass", "silhouette": "goggled workshop prodigy",
        "skin": (0.90, 0.66, 0.43, 1), "shirt": (0.14, 0.55, 0.22, 1),
        "accent": (0.96, 0.30, 0.05, 1), "hair": (0.20, 0.09, 0.03, 1),
        "feature": "goggles",
    },
    "sol_vega": {
        "display_name": "Sol Vega", "silhouette": "retro rally pilot",
        "skin": (0.63, 0.34, 0.18, 1), "shirt": (0.78, 0.72, 0.10, 1),
        "accent": (0.04, 0.18, 0.23, 1), "hair": (0.025, 0.018, 0.012, 1),
        "feature": "helmet",
    },
    "bea_torque": {
        "display_name": "Bea Torque", "silhouette": "bob-haired street tactician",
        "skin": (0.84, 0.58, 0.38, 1), "shirt": (0.39, 0.12, 0.62, 1),
        "accent": (0.96, 0.54, 0.09, 1), "hair": (0.015, 0.012, 0.016, 1),
        "feature": "bob",
    },
}

REQUIRED = ["driver_root", "root", "head", "arm_L", "arm_R",
            "driver_rig", "driver_root_bone", "head_bone", "arm_L_bone",
            "arm_R_bone"]


def make_face(head, mats):
    sphere("face", (0, 0, 0), (0.215, 0.18, 0.225), mats["skin"], head)
    for x in (-0.075, 0.075):
        sphere(f"eye_{x:+}", (x, -0.172, 0.028), (0.045, 0.022, 0.052), mats["white"], head,
               segments=18, rings=12)
        sphere(f"pupil_{x:+}", (x, -0.194, 0.025), (0.019, 0.010, 0.025), mats["dark"], head,
               segments=14, rings=10)
    sphere("nose", (0, -0.185, -0.025), (0.035, 0.030, 0.048), mats["skin"], head,
           segments=16, rings=10)
    cube("smile", (0, -0.190, -0.085), (0.085, 0.012, 0.018), mats["mouth"], head, 0.008)
    bar("brow_L", (-0.125, -0.195, 0.108), (-0.035, -0.198, 0.098),
        0.009, mats["dark"], head)
    bar("brow_R", (0.035, -0.198, 0.098), (0.125, -0.195, 0.108),
        0.009, mats["dark"], head)


def make_hair(feature, head, mats):
    hair = mats["hair"]
    if feature == "buns":
        sphere("hair_cap", (0, 0.015, 0.10), (0.225, 0.18, 0.17), hair, head)
        for x in (-0.20, 0.20):
            sphere(f"hair_bun_{x:+}", (x, 0.0, 0.19), (0.105, 0.095, 0.12), hair, head)
            torus(f"bun_band_{x:+}", (x, 0, 0.14), 0.065, 0.012, mats["accent"], head)
    elif feature == "mohawk":
        for i, y in enumerate((-0.11, -0.04, 0.03, 0.10)):
            sphere(f"mohawk_{i}", (0, y, 0.21 + 0.02 * (2 - abs(i - 2))),
                   (0.045, 0.065, 0.15), mats["accent"], head)
        cube("side_hair", (0, 0.04, 0.08), (0.21, 0.27, 0.16), hair, head, 0.07)
    elif feature == "visor":
        sphere("swept_hair", (0.07, 0.04, 0.11), (0.22, 0.17, 0.18), hair, head)
        cylinder("visor_band", (0, -0.02, 0.12), 0.222, 0.045, mats["accent"], head,
                 rotation=(math.pi / 2, 0, 0), vertices=32, bevel=0.01)
        cube("visor_bill", (0, -0.22, 0.11), (0.30, 0.15, 0.045), mats["accent"], head, 0.025)
    elif feature == "goggles":
        sphere("tousled_hair", (0, 0.04, 0.13), (0.225, 0.17, 0.16), hair, head)
        for x in (-0.085, 0.085):
            torus(f"goggle_{x:+}", (x, -0.20, 0.055), 0.060, 0.012, mats["metal"], head,
                  rotation=(math.pi / 2, 0, 0))
            sphere(f"goggle_lens_{x:+}", (x, -0.205, 0.055), (0.048, 0.012, 0.048),
                   mats["glass"], head)
        bar("goggle_bridge", (-0.025, -0.205, 0.055), (0.025, -0.205, 0.055),
            0.008, mats["metal"], head)
    elif feature == "helmet":
        sphere("pilot_helmet", (0, 0.035, 0.065), (0.245, 0.195, 0.255), mats["accent"], head)
        cube("helmet_stripe", (0, 0.0, 0.256), (0.065, 0.31, 0.025), mats["shirt"], head, 0.01)
        cube("helmet_brow", (0, -0.192, 0.125), (0.34, 0.035, 0.045), mats["shirt"], head, 0.018)
        for x in (-0.225, 0.225):
            cylinder(f"earcup_{x:+}", (x, 0, -0.005), 0.07, 0.035, mats["shirt"], head,
                     rotation=(0, math.pi / 2, 0), bevel=0.015)
    else:
        sphere("bob_crown", (0, 0.035, 0.105), (0.235, 0.19, 0.19), hair, head)
        for x in (-0.205, 0.205):
            cube(f"bob_side_{x:+}", (x, 0.01, -0.04), (0.075, 0.25, 0.28), hair, head, 0.035)
        cube("headband", (0, -0.08, 0.16), (0.40, 0.055, 0.055), mats["accent"], head, 0.025)


def make_realistic_imani(torso, head, arm_l, arm_r, leg_l, leg_r, mats):
    """Build an adult-proportioned seated human within the shared driver rig."""
    # Layered ellipsoids give the torso a ribcage/waist transition without the
    # round toy silhouette of the original single sphere.
    sphere("torso_shell", (0, 0.01, 0.08), (0.245, 0.145, 0.285),
           mats["shirt"], torso, 20, 12)
    sphere("waist", (0, 0.015, -0.125), (0.195, 0.125, 0.155),
           mats["dark"], torso, 18, 10)
    cube("chest_panel", (0, -0.139, 0.115), (0.25, 0.018, 0.30),
         mats["accent"], torso, 0.018)
    for side in (-1, 1):
        bar(f"suit_piping_{side:+}", (side * 0.115, -0.148, 0.25),
            (side * 0.075, -0.151, -0.04), 0.010,
            mats["detail"], torso)
    cylinder("neck", (0, 0, 0.365), 0.060, 0.105,
             mats["skin"], torso, vertices=16, bevel=0.010)
    torus("suit_collar", (0, 0, 0.325), 0.074, 0.018,
          mats["accent"], torso, major_segments=18, minor_segments=6)

    # A smaller cranium, separate jaw and subtle features produce a readable
    # human face while staying efficient enough for the game camera.
    sphere("cranium", (0, 0.0, 0.105), (0.128, 0.112, 0.158),
           mats["skin"], head, 22, 14)
    sphere("jaw", (0, -0.016, 0.015), (0.105, 0.100, 0.105),
           mats["skin"], head, 18, 10)
    for side in (-1, 1):
        sphere(f"ear_{side:+}", (side * 0.126, 0.0, 0.080),
               (0.020, 0.014, 0.034), mats["skin"], head, 12, 8)
        sphere(f"eye_white_{side:+}", (side * 0.045, -0.112, 0.108),
               (0.024, 0.010, 0.012), mats["white"], head, 14, 8)
        sphere(f"iris_{side:+}", (side * 0.045, -0.121, 0.108),
               (0.009, 0.005, 0.009), mats["dark"], head, 12, 8)
        bar(f"brow_{side:+}", (side * 0.072, -0.119, 0.142),
            (side * 0.020, -0.123, 0.147), 0.006,
            mats["hair"], head)
    sphere("nose_bridge", (0, -0.116, 0.085), (0.016, 0.021, 0.040),
           mats["skin"], head, 14, 8)
    sphere("nose_tip", (0, -0.137, 0.063), (0.022, 0.018, 0.016),
           mats["skin"], head, 14, 8)
    bar("upper_lip", (-0.024, -0.124, 0.023),
        (0.024, -0.124, 0.023), 0.006, mats["mouth"], head)
    bar("lower_lip", (-0.021, -0.122, 0.012),
        (0.021, -0.122, 0.012), 0.005, mats["mouth"], head)

    # Close-fitting natural hair and compact twin buns preserve Imani's visual
    # identity without the oversized spherical shapes of the old design.
    sphere("hair_cap", (0, 0.018, 0.155), (0.134, 0.116, 0.108),
           mats["hair"], head, 20, 12)
    for side in (-1, 1):
        sphere(f"hair_bun_{side:+}", (side * 0.105, 0.025, 0.226),
               (0.060, 0.055, 0.060), mats["hair"], head, 16, 10)
        detail = mats["accent"] if side > 0 else mats["detail"]
        torus(f"bun_band_{side:+}", (side * 0.105, -0.005, 0.215),
              0.041, 0.008, detail, head,
              rotation=(math.pi / 2, 0, 0),
              major_segments=16, minor_segments=6)

    # Limbs taper from shoulder/hip to the extremities. The hands meet near
    # the steering-wheel position and the legs retain the common seated pose.
    for side, arm in ((-1, arm_l), (1, arm_r)):
        sphere(f"shoulder_{side:+}", (0, 0, 0.070),
               (0.055, 0.060, 0.068), mats["shirt"], arm, 16, 10)
        elbow = (side * 0.045, -0.195, -0.020)
        hand = (-side * 0.145, -0.410, -0.080)
        bar(f"upper_arm_{side:+}", (0, 0, 0.055), elbow,
            0.047, mats["shirt"], arm)
        bar(f"forearm_{side:+}", elbow, hand, 0.044,
            mats["skin"], arm)
        sphere(f"hand_{side:+}", hand, (0.046, 0.038, 0.052),
               mats["skin"], arm, 16, 10)
        torus(f"cuff_{side:+}",
              tuple(elbow[index] * 0.22 + hand[index] * 0.78
                    for index in range(3)),
              0.047, 0.009, mats["accent"], arm,
              rotation=(math.radians(68), 0, 0),
              major_segments=16, minor_segments=6)

    for side, leg in ((-1, leg_l), (1, leg_r)):
        knee = (0, -0.305, -0.105)
        ankle = (0, -0.500, -0.315)
        bar(f"thigh_{side:+}", (0, 0, 0.075), knee,
            0.082, mats["dark"], leg)
        bar(f"shin_{side:+}", knee, ankle, 0.066,
            mats["shirt"], leg)
        sphere(f"knee_panel_{side:+}", knee, (0.086, 0.072, 0.078),
               mats["accent"], leg, 16, 10)
        cube(f"boot_{side:+}", (0, -0.575, -0.390),
             (0.145, 0.245, 0.135), mats["dark"], leg, 0.045)
        cube(f"boot_stripe_{side:+}", (0, -0.660, -0.355),
             (0.150, 0.025, 0.030), mats["accent"], leg, 0.010)


def add_realistic_driver_preview_context(mats):
    """Add a non-exported seat and wheel so the authored pose reads clearly."""
    seat_back = cube("PREVIEW_seat_back", (0, 0.115, -0.015),
                     (0.42, 0.10, 0.62), mats["dark"], bevel=0.065)
    seat_back.rotation_euler.x = math.radians(-8)
    seat_base = cube("PREVIEW_seat_base", (0, 0.035, -0.325),
                     (0.40, 0.44, 0.10), mats["dark"], bevel=0.045)
    wheel = torus("PREVIEW_steering_wheel", (0, -0.355, 0.105),
                  0.135, 0.016, mats["dark"],
                  rotation=(math.radians(68), 0, 0),
                  major_segments=20, minor_segments=6)
    column = bar("PREVIEW_steering_column", (0, -0.34, 0.09),
                 (0, -0.04, -0.10), 0.014, mats["metal"])
    for obj in (seat_back, seat_base, wheel, column):
        obj[ASSET_PROP] = False


def build_driver(slug: str):
    reset_scene()
    spec = DRIVERS[slug]
    mats = {
        "skin": material(f"{slug}_skin", spec["skin"], roughness=0.62),
        "shirt": material(f"{slug}_shirt", spec["shirt"], roughness=0.44),
        "accent": material(f"{slug}_accent", spec["accent"], metallic=0.06, roughness=0.38),
        "detail": material(f"{slug}_detail", (0.82, 0.88, 0.84, 1),
                           metallic=0.04, roughness=0.46),
        "hair": material(f"{slug}_hair", spec["hair"], roughness=0.70),
        "dark": material(f"{slug}_dark", (0.012, 0.016, 0.02, 1), roughness=0.62),
        "white": material(f"{slug}_eyes", (0.96, 0.96, 0.91, 1), roughness=0.40),
        "mouth": material(f"{slug}_mouth", (0.35, 0.018, 0.025, 1), roughness=0.58),
        "metal": material(f"{slug}_metal", (0.40, 0.45, 0.48, 1), metallic=0.72, roughness=0.22),
        "glass": material(f"{slug}_glass", (0.08, 0.42, 0.54, 1), metallic=0.15, roughness=0.16),
    }
    driver_root = empty("driver_root")
    driver_root["asset_id"] = f"formula_buggy.driver.{slug}"
    driver_root["attach_to"] = "seat_anchor"
    root = empty("root", owner=driver_root)
    torso = empty("torso", (0, 0, 0.12), root)
    head = empty("head", (0, -0.02, 0.47), root)
    arm_x = 0.28 if spec.get("realistic") else 0.25
    arm_l = empty("arm_L", (-arm_x, -0.02, 0.25), root)
    arm_r = empty("arm_R", (arm_x, -0.02, 0.25), root)
    leg_l = empty("leg_L", (-0.145, 0, -0.08), root)
    leg_r = empty("leg_R", (0.145, 0, -0.08), root)

    if spec.get("realistic"):
        make_realistic_imani(torso, head, arm_l, arm_r,
                             leg_l, leg_r, mats)
    else:
        sphere("torso_shell", (0, 0, 0), (0.29, 0.19, 0.30), mats["shirt"], torso)
        cube("harness_buckle", (0, -0.205, -0.01), (0.17, 0.035, 0.15), mats["accent"], torso, 0.025)
        for x in (-0.14, 0.14):
            bar(f"harness_{x:+}", (x, -0.185, 0.22), (x * 0.35, -0.21, 0.04),
                0.024, mats["accent"], torso)
        cube("harness_belt", (0, -0.198, -0.11), (0.38, 0.03, 0.055), mats["accent"], torso, 0.018)
        cylinder("collar", (0, -0.01, 0.29), 0.11, 0.055, mats["accent"], torso, bevel=0.012)
        make_face(head, mats)
        make_hair(spec["feature"], head, mats)

        for side, arm in (("L", arm_l), ("R", arm_r)):
            sign = -1 if side == "L" else 1
            bar(f"upper_arm_{side}", (0, 0, 0), (sign * 0.075, -0.20, -0.15),
                0.075, mats["shirt"], arm)
            bar(f"forearm_{side}", (sign * 0.075, -0.20, -0.15),
                (-sign * 0.02, -0.43, -0.20), 0.065, mats["skin"], arm)
            sphere(f"hand_{side}", (-sign * 0.02, -0.44, -0.20),
                   (0.075, 0.065, 0.075), mats["skin"], arm)
        for side, leg in (("L", leg_l), ("R", leg_r)):
            bar(f"thigh_{side}", (0, 0, 0), (0, -0.30, -0.13), 0.10, mats["dark"], leg)
            bar(f"shin_{side}", (0, -0.30, -0.13), (0, -0.39, -0.38), 0.085, mats["shirt"], leg)
            cube(f"shoe_{side}", (0, -0.46, -0.40), (0.19, 0.28, 0.13), mats["accent"], leg, 0.05)

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
    if spec.get("realistic"):
        add_realistic_driver_preview_context(mats)
    return spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=["all", *DRIVERS], default="all")
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "assets_src" / "drivers")
    args = parser.parse_args()
    targets = DRIVERS if args.asset == "all" else [args.asset]
    for slug in targets:
        spec = build_driver(slug)
        metadata = {
            "type": "driver",
            "display_name": spec["display_name"],
            "silhouette": spec["silhouette"],
            "design_style": ("realistic human" if spec.get("realistic")
                             else "stylized human"),
            "target_seated_pose_height_m": 1.1,
            "target_dimensions_m": {"width_x": 0.65, "depth_y": 0.66,
                                    "seated_height_z": 1.1},
            "attachment": {"driver_origin": "pelvis", "vehicle_bone": "seat_anchor"},
            "animation_clips": {"idle": [1, 32], "accelerate": [40, 54],
                                "brake": [60, 74], "turn_left": [80, 100],
                                "turn_right": [80, 100]},
        }
        camera = ((2.15, -3.15, 1.55) if spec.get("realistic")
                  else (2.6, -3.6, 1.8))
        target = ((0, -0.12, 0.08) if spec.get("realistic")
                  else (0, -0.08, 0.08))
        export_asset(args.output_root / slug, slug, metadata, REQUIRED,
                     camera, target)


if __name__ == "__main__":
    main()
