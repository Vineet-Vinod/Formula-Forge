"""Collect reproducible, compact evidence from the completed diagnostic runs."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/forensics/monza"


def main():
    scene = json.loads((OUT / "scene_audit.json").read_text())
    exported = json.loads((OUT / "export_audit.json").read_text())
    terraces = json.loads((OUT / "terrace_audit.json").read_text())
    metrics = {}
    for pose in [
        "start",
        "pit",
        "grandstand",
        "kerb",
        "kerb_entry",
        "stand_side",
        "stand_av",
    ]:
        metrics[pose] = {}
        for depth, prefix in [(16, ""), (24, "depth24_")]:
            a = np.array(
                Image.open(OUT / f"{prefix}{pose}_near0.05_reverse0.png")
            ).astype(int)
            b = np.array(
                Image.open(OUT / f"{prefix}{pose}_near0.05_reverse1.png")
            ).astype(int)
            diff = np.max(abs(a[:, :, :3] - b[:, :, :3]), axis=2)
            metrics[pose][str(depth)] = {
                "pixels_changed_gt8": int((diff > 8).sum()),
                "fraction_changed_gt8": float((diff > 8).mean()),
            }
    observed = {}
    for prefix in ["", "depth24_"]:
        observed[prefix or "default"] = [
            line
            for line in (OUT / f"{prefix}start_near0.05_reverse0.log")
            .read_text()
            .splitlines()
            if line.startswith("FORENSICS")
        ]
    protected = scene["hashes_before"]
    assert protected == {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in protected
    }
    names = set(exported["comparison"]) | {
        "Start finish line",
        "tribune concrete terraces",
        "Tribuna Alta Velocità concrete terraces",
        "Tribuna Prima Variante Esterna concrete terraces",
    }
    report = {
        "date": "2026-09-04",
        "protected_asset_hashes_unchanged": protected,
        "coordinate_frame": scene["units"],
        "renderer_observations": observed,
        "draw_order_metrics": metrics,
        "scope": {
            "scene_objects": 1342,
            "ordinary_geometry_objects_inspected": len(scene["objects"]),
            "instance_containers": len(scene["instances"]),
            "suspect_debug_materials": len(
                json.loads((OUT / "debug_materials.json").read_text())
            ),
        },
        "affected_objects": [o for o in scene["objects"] if o["name"] in names],
        "depth_overlaps": scene["surface_overlaps"],
        "structural_contacts": scene["structural_close_parallel_faces"],
        "duplicate_objects": scene["duplicate_objects"],
        "duplicate_faces": scene["duplicate_face_groups"],
        "terrace_bases": terraces,
        "export_audit": exported,
        "limitations": scene["limitations"],
    }
    target = ROOT / "docs/forensics/monza-evidence.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "draw_order_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print("Protected asset hashes unchanged. Wrote", target)


if __name__ == "__main__":
    main()
