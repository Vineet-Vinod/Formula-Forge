"""Find coincident internal terrace bottoms and clearance over actual ground."""

import json
from pathlib import Path

import bpy  # noqa: F401 - Initializes mathutils in the uv Python process.
import numpy as np
from mathutils.bvhtree import BVHTree
from shapely import Polygon, STRtree

OUT = Path(__file__).resolve().parents[2] / "build/forensics/monza"


def main():
    names = json.loads((OUT / "triangle_objects.json").read_text())
    data = np.load(OUT / "triangles.npz")
    report = []
    ground = data[f"p_{names.index('Park ground')}"].reshape(-1, 3)
    tree3 = BVHTree.FromPolygons(
        ground.tolist(),
        np.arange(len(ground)).reshape(-1, 3).tolist(),
        all_triangles=True,
    )
    for name in names:
        if "concrete terraces" not in name:
            continue
        p = data[f"p_{names.index(name)}"]
        bottom = p[
            (np.ptp(p[:, :, 2], axis=1) < 1e-6)
            & (abs(p[:, :, 2].mean(1) - p[:, :, 2].min()) < 1e-6)
        ]
        if not len(bottom):
            continue
        polygons = [Polygon(t[:, :2]) for t in bottom]
        tree = STRtree(polygons)
        overlap = 0
        count = 0
        for i, poly in enumerate(polygons):
            for j in tree.query(poly, predicate="intersects"):
                if j <= i:
                    continue
                area = poly.intersection(polygons[j]).area
                if area > 1e-8:
                    overlap += area
                    count += 1
        samples = []
        for v in np.unique(bottom.reshape(-1, 3), axis=0):
            hit, _normal, idx, _d = tree3.ray_cast((v[0], v[1], 100), (0, 0, -1), 200)
            if hit is not None:
                samples.append((float(v[2] - hit.z), v.tolist(), idx))
        samples.sort()
        report.append(
            {
                "name": name,
                "bottom_bounds": [
                    bottom.min((0, 1)).tolist(),
                    bottom.max((0, 1)).tolist(),
                ],
                "bottom_triangles": len(bottom),
                "coplanar_bottom_overlap_pairs": count,
                "overlap_area_m2": overlap,
                "bottom_minus_park_mesh_m": [samples[0][0], samples[-1][0]],
                "minimum_clearance_sample": samples[0],
                "maximum_clearance_sample": samples[-1],
            }
        )
    (OUT / "terrace_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Audited", len(report), "terraces against the saved Park ground triangles.")


if __name__ == "__main__":
    main()
