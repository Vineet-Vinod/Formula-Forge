"""Regression checks for winding, paint, apron overlap and stand foundations."""

import json
import sys

import bpy
import build_monza as B
import numpy as np
from repair_monza_rendering import OUT, repair, triangles
from shapely import Polygon, STRtree

sys.path.insert(0, str(B.ROOT / "tools/diagnostics"))
from monza_scene_audit import overlaps


def main():
    B.load()
    originals = json.loads((B.ROOT / "docs/forensics/monza-evidence.json").read_text())
    names = []
    for ob in bpy.data.objects:
        if ob.type == "MESH" and (
            " kerb " in ob.name
            or " green apron " in ob.name
            or ob.name
            in [
                "R continuous 150 mm edge line",
                "L continuous 150 mm edge line",
                "R grass verge",
                "L grass verge",
                "R drainage concrete",
                "L drainage concrete",
            ]
        ):
            assert all(p.normal.z >= 0 for p in ob.data.polygons), ob.name
            names.append(ob.name)
    sources = [
        "ASPHALT | continuous crowned surface",
        "Pit lane | mapped entry and exit",
        "Pit edge -1",
        "Pit edge 1",
        "Start finish line",
    ]
    data = {name: triangles(bpy.data.objects[name]) for name in sources}
    pairs = overlaps([{"name": n, "exported": True} for n in sources], data)
    paint = [p for p in pairs if p["a"] in sources[2:] and p["b"] in sources[:2]]
    # Pit entry/exit overlays are intentionally gone; each retained paint object
    # must still lie above its underlying asphalt.
    for name in sources[2:]:
        assert any(p["a"] == name for p in paint), name
    for p in paint:
        assert p["min_a_minus_b_m"] > 0.005, (p["a"], p["b"], p["min_a_minus_b_m"])
    apron = triangles(bpy.data.objects["Rettifilo green apron 609"])
    polys = [Polygon(t[:, :2]) for t in apron]
    tree = STRtree(polys)
    max_overlap = 0
    for i, p in enumerate(polys):
        for j in tree.query(p, predicate="intersects"):
            if i < j:
                max_overlap = max(max_overlap, p.intersection(polys[j]).area)
    assert max_overlap < 1e-8, max_overlap
    terraces = []
    for ob in bpy.data.objects:
        if "concrete terraces" not in ob.name:
            continue
        old = next(
            (o for o in originals["affected_objects"] if o["name"] == ob.name), None
        )
        v = np.array([v.co[:] for v in ob.data.vertices])
        bottom = v[:, 2].min()
        feet = v[abs(v[:, 2] - bottom) < 1e-5]
        gaps = [float(p[2] - B.terrain(p[0], p[1])) for p in feet]
        assert max(gaps) < -0.09, ob.name
        assert not any(p.normal.z < -0.9 for p in ob.data.polygons), ob.name
        if old is not None:
            assert np.allclose(v[:, :2].min(0), old["bounds"][0][:2])
            assert np.allclose(v[:, :2].max(0), old["bounds"][1][:2])
        terraces.append({"name": ob.name, "max_foundation_clearance_m": max(gaps)})
    # A second pass must neither accumulate offsets nor rebuild the scene.
    unchanged = repair()
    assert not unchanged["changes"], unchanged["changes"]
    result = {
        "upward_sheets": len(names),
        "paint_clearance": [
            {
                "a": p["a"],
                "b": p["b"],
                "min_m": p["min_a_minus_b_m"],
                "max_m": p["max_a_minus_b_m"],
            }
            for p in paint
        ],
        "max_apron_self_overlap_m2": max_overlap,
        "grounded_stands": terraces,
        "repair_idempotent": True,
        "asphalt_vertices_sha256": unchanged["asphalt_vertices_unchanged"],
    }
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ["grounded_stands", "paint_clearance"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
