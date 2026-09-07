"""Read-only source/export forensics. Run with uv run --no-sync python.

No generator/export entry points are called. Coordinates are Blender world metres.
Exact tests use a 10 micrometre positional tolerance. Surface tests intersect
projected triangles, then compare plane heights at intersection vertices.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy  # isort: skip
import bmesh  # isort: skip
import numpy as np
from shapely import Polygon, STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/blender/tracks"))
import build_monza as B


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(o):
    return (
        not any(
            c.name in ["Asset_library", "QA_cameras", "Survey_curves"]
            for c in o.users_collection
        )
        and o.name != "Distant ground horizon"
        and not o.name.startswith("Grid ")
        and o.type in ["MESH", "FONT", "CURVE"]
    )


def bounds(p):
    return [p.min(axis=0).tolist(), p.max(axis=0).tolist()] if len(p) else None


def keys(p):
    q = np.round(p / 1e-5).astype(np.int64)
    q = (
        np.sort(
            q.view([("x", "i8"), ("y", "i8"), ("z", "i8")]).reshape(q.shape[:2]), axis=1
        )
        .view("i8")
        .reshape(-1, 9)
    )
    return q


def mesh_info(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    v = np.array([v.co[:] for v in me.vertices], dtype=float).reshape(-1, 3)
    m = np.array(o.matrix_world)
    v = v @ m[:3, :3].T + m[:3, 3]
    ids = np.array([t.vertices[:] for t in me.loop_triangles], dtype=int).reshape(-1, 3)
    p = v[ids]
    mi = np.array([t.material_index for t in me.loop_triangles], dtype=int)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    n /= np.maximum(2 * area[:, None], 1e-20)
    mats = [s.material.name if s.material else None for s in o.material_slots]
    bm = bmesh.new()
    bm.from_mesh(me)
    boundary = sum(e.is_boundary for e in bm.edges)
    nonmanifold = sum(not e.is_manifold and not e.is_boundary for e in bm.edges)
    inconsistent = sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
    bm.free()
    parent = np.arange(len(v))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in me.edges:
        a, b = e.vertices
        parent[root(a)] = root(b)
    groups = defaultdict(list)
    for i in range(len(v)):
        groups[root(i)].append(i)
    components = sorted(
        ({"vertices": len(ii), "bounds": bounds(v[ii])} for ii in groups.values()),
        key=lambda x: -x["vertices"],
    )
    uv = {}
    for layer in me.uv_layers:
        a = np.array([x.uv[:] for x in layer.data])
        uv[layer.name] = {
            "bounds": bounds(a),
            "nonfinite": int((~np.isfinite(a)).sum()),
        }
    k = keys(p)
    _, counts = np.unique(k, axis=0, return_counts=True)
    rec = {
        "name": o.name,
        "type": o.type,
        "collections": [c.name for c in o.users_collection],
        "parent": o.parent.name if o.parent else None,
        "exported": selected(o),
        "hide_render": o.hide_render,
        "hide_viewport": o.hide_viewport,
        "hide_get": o.hide_get(),
        "collection_hidden": [
            c.name for c in o.users_collection if c.hide_render or c.hide_viewport
        ],
        "location": list(o.location),
        "rotation": list(o.rotation_euler),
        "scale": list(o.scale),
        "determinant": float(np.linalg.det(m[:3, :3])),
        "matrix_world": m.tolist(),
        "bounds": bounds(v),
        "dimensions": (np.ptp(v, axis=0).tolist() if len(v) else [0, 0, 0]),
        "vertices": len(v),
        "polygons": len(me.polygons),
        "triangles": len(p),
        "duplicate_triangles": int(sum(counts - 1)),
        "degenerate_triangles": int((area < 1e-10).sum()),
        "boundary_edges": boundary,
        "other_nonmanifold_edges": nonmanifold,
        "inconsistent_winding_edges": inconsistent,
        "normal_z_counts": {
            "up": int((n[:, 2] > 0.9).sum()),
            "down": int((n[:, 2] < -0.9).sum()),
        },
        "max_triangle_area_m2": float(area.max()) if len(area) else 0,
        "max_edge_m": float(np.linalg.norm(p - np.roll(p, 1, axis=1), axis=2).max())
        if len(p)
        else 0,
        "materials": mats,
        "material_triangles": dict(
            Counter(mats[i] if 0 <= i < len(mats) else f"INVALID:{i}" for i in mi)
        ),
        "uv": uv,
        "components_count": len(components),
        "largest_components": components[:8],
        "modifiers": [
            {
                "name": x.name,
                "type": x.type,
                "viewport": x.show_viewport,
                "render": x.show_render,
            }
            for x in o.modifiers
        ],
        "properties": {k: str(o[k]) for k in o.keys()},  # noqa: SIM118 - bpy Object is not iterable.
        "nonfinite_coordinates": int((~np.isfinite(v)).sum()),
    }
    ev.to_mesh_clear()
    return rec, p, mi


def overlaps(objects, triangles):
    # Only surfaces relevant to reported symptoms, with full triangle footprints.
    names = [
        r["name"]
        for r in objects
        if r["exported"]
        and r["name"] in triangles
        and (
            any(
                t in r["name"].lower()
                for t in [
                    "kerb",
                    "apron",
                    "pit edge",
                    "pit lane",
                    "edge line",
                    "drainage",
                    "grass verge",
                    "runoff",
                    "escape road",
                    "start finish",
                ]
            )
            or r["name"] in ["Park ground", "ASPHALT | continuous crowned surface"]
        )
    ]
    flat = []
    owner = []
    local = []
    for name in names:
        p = triangles[name]
        for i, t in enumerate(p):
            n = np.cross(t[1] - t[0], t[2] - t[0])
            if abs(n[2]) > 1e-9:
                flat.append(t)
                owner.append(name)
                local.append(i)
    p = np.array(flat)
    polys = [Polygon(t[:, :2]) for t in p]
    tree = STRtree(polys)
    result = {}

    def z(t, xy):
        n = np.cross(t[1] - t[0], t[2] - t[0])
        return t[0, 2] - ((xy - t[0, :2]) @ n[:2]) / n[2]

    targets = [
        i
        for i, n in enumerate(owner)
        if any(
            s in n.lower()
            for s in ["kerb", "apron", "pit edge", "edge line", "start finish"]
        )
    ]
    for i in targets:
        for j in tree.query(polys[i], predicate="intersects"):
            if owner[i] == owner[j]:
                if j <= i:
                    continue
                if len(set(map(tuple, p[i])) & set(map(tuple, p[j]))) >= 2:
                    continue
            # Avoid symmetric pairs where both objects are query targets.
            if (
                any(
                    s in owner[j].lower()
                    for s in ["kerb", "apron", "pit edge", "edge line", "start finish"]
                )
                and j < i
            ):
                continue
            poly = polys[i].intersection(polys[j])
            if poly.area < 1e-8 or poly.geom_type != "Polygon":
                continue
            xy = np.array(poly.exterior.coords)[:, :2]
            dz = z(p[i], xy) - z(p[j], xy)
            lo, hi = float(dz.min()), float(dz.max())
            pair = (owner[i], owner[j])
            r = result.setdefault(
                pair,
                {
                    "a": pair[0],
                    "b": pair[1],
                    "overlap_pairs": 0,
                    "projected_area_sum_m2": 0.0,
                    "min_a_minus_b_m": 1e9,
                    "max_a_minus_b_m": -1e9,
                    "crossing_pairs": 0,
                    "within_1mm_pairs": 0,
                    "within_10mm_pairs": 0,
                    "examples": [],
                },
            )
            r["overlap_pairs"] += 1
            r["projected_area_sum_m2"] += poly.area
            r["min_a_minus_b_m"] = min(r["min_a_minus_b_m"], lo)
            r["max_a_minus_b_m"] = max(r["max_a_minus_b_m"], hi)
            r["crossing_pairs"] += int(lo < -1e-5 and hi > 1e-5)
            r["within_1mm_pairs"] += int(lo <= 0.001 and hi >= -0.001)
            r["within_10mm_pairs"] += int(lo <= 0.01 and hi >= -0.01)
            if len(r["examples"]) < 3 or (
                lo < -1e-5
                and hi > 1e-5
                and not any(x["crossing"] for x in r["examples"])
            ):
                xy0 = np.array(poly.representative_point().coords)
                r["examples"].append(
                    {
                        "triangle_a": local[i],
                        "triangle_b": local[j],
                        "point_a": [
                            float(xy0[0, 0]),
                            float(xy0[0, 1]),
                            float(z(p[i], xy0)[0]),
                        ],
                        "gap_range_m": [lo, hi],
                        "crossing": bool(lo < -1e-5 and hi > 1e-5),
                    }
                )
    return list(result.values())


def structural_contacts(triangles):
    # Exhaustive projected overlap of close parallel triangles on roofs/gantry,
    # including triangles from the same object, independent of normals' sign.
    names = [
        n
        for n in triangles
        if ("canopy" in n and n.startswith("Tribuna"))
        or n in ["MONZA start bridge", "Start gantry lettering", "Timing gantry"]
    ]
    result = []
    for ai, a in enumerate(names):
        pa = triangles[a]
        if not len(pa):
            continue
        for b in names[ai:]:
            pb = triangles[b]
            if not len(pb):
                continue
            if np.any(pa.max((0, 1)) + 0.02 < pb.min((0, 1))) or np.any(
                pb.max((0, 1)) + 0.02 < pa.min((0, 1))
            ):
                continue
            hits = []
            for i, t in enumerate(pa):
                n = np.cross(t[1] - t[0], t[2] - t[0])
                length = np.linalg.norm(n)
                if length < 1e-10:
                    continue
                n /= length
                axis = int(abs(n).argmax())
                axes = [x for x in range(3) if x != axis]
                nb = np.cross(pb[:, 1] - pb[:, 0], pb[:, 2] - pb[:, 0])
                nb /= np.maximum(np.linalg.norm(nb, axis=1)[:, None], 1e-20)
                distances = (pb - t[0]) @ n
                candidates = np.flatnonzero(
                    (np.abs(nb @ n) > 0.9999) & (np.abs(distances).max(axis=1) < 0.02)
                )
                for j in candidates:
                    if a == b and j <= i:
                        continue
                    poly = Polygon(t[:, axes]).intersection(Polygon(pb[j][:, axes]))
                    if poly.area > 1e-7:
                        hits.append(
                            {
                                "triangle_a": i,
                                "triangle_b": int(j),
                                "max_plane_distance_m": float(abs(distances[j]).max()),
                                "overlap_area_projected_m2": poly.area,
                                "center": t.mean(0).tolist(),
                            }
                        )
            if hits:
                result.append(
                    {"a": a, "b": b, "count": len(hits), "examples": hits[:12]}
                )
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / "build/forensics/monza")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    protected = [
        B.BLEND,
        B.OUT / "monza.glb",
        B.OUT / "monza.json",
        ROOT / "src/track_data/monza_survey.inc",
    ]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    B.load()
    dg = bpy.context.evaluated_depsgraph_get()
    records = []
    triangles = {}
    matids = {}
    instances = []
    for o in bpy.data.objects:
        if o.type not in ["MESH", "FONT", "CURVE"]:
            continue
        if o.type == "MESH" and "instance_scale" in o.data.attributes:
            scale = np.array(
                [v.vector[:] for v in o.data.attributes["instance_scale"].data]
            )
            instances.append(
                {
                    "name": o.name,
                    "count": len(scale),
                    "nonpositive_scale": int((scale.min(axis=1) <= 0).sum()),
                    "matrix_world": np.array(o.matrix_world).tolist(),
                    "collections": [c.name for c in o.users_collection],
                }
            )
            continue
        r, p, mi = mesh_info(o, dg)
        records.append(r)
        if selected(o):
            triangles[o.name] = p
            matids[o.name] = mi
    print("Inventory complete", len(records), "objects", flush=True)
    signatures = defaultdict(list)
    for n, p in triangles.items():
        if len(p):
            k = keys(p)
            k = k[np.lexsort(k.T[::-1])]
            signatures[hashlib.sha256(k.tobytes()).hexdigest()].append(n)
    duplicates = [v for v in signatures.values() if len(v) > 1]
    allkeys = []
    owners = []
    for n, p in triangles.items():
        # Million-seat comparisons are included; instances are reported separately.
        allkeys.append(keys(p))
        owners.extend([n] * len(p))
    k = np.concatenate(allkeys)
    _, inv, counts = np.unique(k, axis=0, return_inverse=True, return_counts=True)
    duplicate_groups = defaultdict(list)
    for i in np.flatnonzero(counts[inv] > 1):
        duplicate_groups[int(inv[i])].append(owners[i])
    face_pairs = Counter(tuple(sorted(v)) for v in duplicate_groups.values())
    print("Duplicate scan complete", len(duplicate_groups), flush=True)
    depth = overlaps(records, triangles)
    print("Surface intersections complete", len(depth), flush=True)
    structures = structural_contacts(triangles)
    materials = []
    for m in bpy.data.materials:
        materials.append(
            {
                "name": m.name,
                "diffuse": list(m.diffuse_color),
                "surface_render_method": m.surface_render_method,
                "backface_culling": m.use_backface_culling,
                "nodes": [n.bl_idname for n in m.node_tree.nodes]
                if m.node_tree
                else [],
                "principled_alpha": [
                    float(n.inputs["Alpha"].default_value)
                    for n in m.node_tree.nodes
                    if n.bl_idname == "ShaderNodeBsdfPrincipled"
                ]
                if m.node_tree
                else [],
            }
        )
    candidates = [
        r
        for r in records
        if r["exported"]
        and r["bounds"]
        and r["bounds"][0][0] < 65
        and r["bounds"][1][0] > -100
        and r["bounds"][0][1] < 800
        and r["bounds"][1][1] > -300
        and r["max_triangle_area_m2"] > 5
    ]
    suspect_names = {r["name"] for r in candidates}
    for r in records:
        if r["exported"] and (
            any(
                word in r["name"].lower()
                for word in [
                    "kerb",
                    "apron",
                    "edge line",
                    "pit edge",
                    "canopy",
                    "gantry",
                ]
            )
            or r["name"].startswith("ASPHALT")
        ):
            suspect_names.add(r["name"])
    suspects = [
        {
            key: r[key]
            for key in [
                "name",
                "bounds",
                "dimensions",
                "components_count",
                "largest_components",
                "max_triangle_area_m2",
            ]
        }
        for r in records
        if r["name"] in suspect_names
    ]
    (args.output / "suspects_before_debug.json").write_text(
        json.dumps(suspects, indent=2) + "\n"
    )
    report = {
        "units": "Blender world metres (x,y,z), runtime (x,z,-y)*1.445",
        "hashes_before": before,
        "objects": records,
        "instances": instances,
        "duplicate_objects": duplicates,
        "duplicate_face_groups": [
            {"objects": list(k), "groups": v} for k, v in face_pairs.items()
        ],
        "surface_overlaps": depth,
        "structural_close_parallel_faces": structures,
        "grandstand_large_face_candidates": [r["name"] for r in candidates],
        "materials": materials,
        "collections": [
            {
                "name": c.name,
                "hide_render": c.hide_render,
                "hide_viewport": c.hide_viewport,
            }
            for c in bpy.data.collections
        ],
        "limitations": [
            "Geometry-node instances audited as placement attributes and separate prototypes, not expanded for global face comparisons.",
            "Source topology uses evaluated viewport modifiers. Export seat/tyre decimation is separate.",
            "Non-manifold counts distinguish intended sheet boundaries from other edges. Disconnected components do not alone prove floating geometry.",
            "Surface comparisons exclude vertical triangles and use positive XY overlap area. Structural close-parallel scan covers Tribuna canopies and start gantry with a 20 mm threshold.",
            "Internal coplanar faces are detected; arbitrary enclosed/intersecting solids need targeted inspection.",
            "Screenshot camera poses are unavailable. Suspect mapping to screenshot pixels needs game object-ID capture.",
        ],
    }
    report["hashes_after"] = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    assert before == report["hashes_after"]
    (args.output / "scene_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    # Data for a separate diagnostic exporter, never written to production assets.
    np.savez_compressed(
        args.output / "triangles.npz",
        **{f"p_{i}": p for i, p in enumerate(triangles.values())},
        **{f"m_{i}": matids[n] for i, n in enumerate(triangles)},
    )
    (args.output / "triangle_objects.json").write_text(
        json.dumps(list(triangles), indent=2) + "\n"
    )
    print("Written", args.output / "scene_audit.json", flush=True)


if __name__ == "__main__":
    main()
