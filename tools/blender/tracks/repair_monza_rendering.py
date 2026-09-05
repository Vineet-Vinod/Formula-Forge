"""Repair diagnosed visual geometry without changing asphalt or the driving route.

uv run --no-sync python tools/blender/tracks/repair_monza_rendering.py
Only the named paint/apron meshes, upward ground sheets and stand foundations
are edited. The original scene is backed up under build/forensics/monza-fix.
"""

import hashlib
import json
import shutil

import bpy  # isort: skip
import bmesh  # isort: skip
import build_monza as B
import numpy as np
from mathutils.bvhtree import BVHTree
from shapely import Polygon, STRtree, constrained_delaunay_triangles, unary_union

OUT = B.ROOT / "build/forensics/monza-fix"
PAINT_CLEARANCE = 0.008


def triangles(ob):
    ob.data.calc_loop_triangles()
    v = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    return v[np.array([t.vertices[:] for t in ob.data.loop_triangles], dtype=int)]


def replace_mesh(ob, vertices, faces):
    mats = list(ob.data.materials)
    mesh = bpy.data.meshes.new(ob.name + " repaired")
    mesh.from_pydata(vertices, [], faces)
    for mat in mats:
        mesh.materials.append(mat)
    mesh.update()
    ob.data = mesh


def upward_sheet(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    flipped = 0
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
            flipped += 1
    if flipped:
        bm.to_mesh(ob.data)
        ob.data.update()
    bm.free()
    return flipped


def ground_terraces(ob):
    if ob.get("grounded_foundation_v1"):
        return 0
    # Row boxes share a flat base. Extend only their feet below the lowest
    # terrain; remove hidden coincident bottoms instead of moving the stand.
    bottom = min(v.co.z for v in ob.data.vertices)
    feet = [v for v in ob.data.vertices if abs(v.co.z - bottom) < 1e-5]
    floor = min(bottom, min(B.terrain(v.co.x, v.co.y) for v in feet) - 0.10)
    remove = [
        p.index
        for p in ob.data.polygons
        if all(abs(ob.data.vertices[i].co.z - bottom) < 1e-5 for i in p.vertices)
    ]
    for v in feet:
        v.co.z = floor
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in remove], context="FACES_ONLY")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    ob["grounded_foundation_v1"] = True
    return len(remove)


def planar_z(t, xy):
    n = np.cross(t[1] - t[0], t[2] - t[0])
    return t[0, 2] - ((np.asarray(xy) - t[0, :2]) @ n[:2]) / n[2]


def polygon_triangles(poly):
    if poly.is_empty:
        return
    for t in constrained_delaunay_triangles(poly).geoms:
        if t.area > 1e-9:
            yield list(t.exterior.coords)[:3]


def conform_paint(ob, surfaces, top):
    if ob.get("conformed_paint_v1"):
        return 0
    footprint = unary_union([Polygon(t[:, :2]) for t in triangles(ob)])
    remaining = footprint
    vertices = []
    faces = []
    for base, polys, tree in surfaces:
        covered = []
        for i in tree.query(remaining, predicate="intersects"):
            part = remaining.intersection(polys[i])
            if part.area < 1e-9:
                continue
            covered.append(part)
            for xy in polygon_triangles(part):
                corners = []
                for x, y in xy:
                    hit, _, _, _ = top.ray_cast((x, y, 20), (0, 0, -1), 40)
                    z = max(float(planar_z(base[i], (x, y))), hit.z if hit else -100)
                    corners.append((x, y, z + PAINT_CLEARANCE))
                a = len(vertices)
                vertices.extend(corners)
                faces.append((a, a + 1, a + 2))
        remaining = remaining.difference(unary_union(covered))
    assert remaining.area < 1e-4, (ob.name, remaining.area)
    replace_mesh(ob, vertices, faces)
    upward_sheet(ob)
    ob["conformed_paint_v1"] = True
    return len(faces)


def partition_apron(ob):
    if ob.get("partitioned_apron_v2"):
        return 0
    vertices = []
    faces = []
    occupied = Polygon()
    for t in triangles(ob):
        poly = Polygon(t[:, :2])
        allowed = poly.difference(occupied.buffer(0.0001, join_style="mitre"))
        for xy in polygon_triangles(allowed):
            a = len(vertices)
            vertices.extend((x, y, float(planar_z(t, (x, y)))) for x, y in xy)
            faces.append((a, a + 1, a + 2))
        occupied = occupied.union(poly)
    replace_mesh(ob, vertices, faces)
    upward_sheet(ob)
    ob["partitioned_apron_v2"] = True
    return len(faces)


def repair():
    road = bpy.data.objects["ASPHALT | continuous crowned surface"]
    before = hashlib.sha256(
        np.asarray([v.co[:] for v in road.data.vertices], dtype="<f4").tobytes()
    ).hexdigest()
    surfaces = []
    allbase = []
    for name in [
        "ASPHALT | continuous crowned surface",
        "Pit lane | mapped entry and exit",
    ]:
        p = triangles(bpy.data.objects[name])
        polys = [Polygon(t[:, :2]) for t in p]
        surfaces.append((p, polys, STRtree(polys)))
        allbase.extend(p)
    allbase = np.asarray(allbase).reshape(-1, 3)
    top = BVHTree.FromPolygons(
        allbase.tolist(),
        np.arange(len(allbase)).reshape(-1, 3).tolist(),
        all_triangles=True,
    )
    changes = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        count = 0
        operation = ""
        if "concrete terraces" in ob.name:
            count = ground_terraces(ob)
            operation = "remove bottom faces and ground row foundations"
        elif ob.name in ["Pit edge -1", "Pit edge 1", "Start finish line"]:
            count = conform_paint(ob, surfaces, top)
            operation = "paint follows upper asphalt triangles with 8 mm clearance"
        elif ob.name == "Rettifilo green apron 609":
            count = partition_apron(ob)
            operation = "partition self-overlapping apron"
        elif (
            " kerb " in ob.name
            or " green apron " in ob.name
            or ob.name
            in [
                "L grass verge",
                "R grass verge",
                "L drainage concrete",
                "R drainage concrete",
                "L continuous 150 mm edge line",
                "R continuous 150 mm edge line",
            ]
        ):
            count = upward_sheet(ob)
            operation = "orient top sheet upward"
        if count:
            changes.append({"object": ob.name, "operation": operation, "faces": count})
    # The horizontal timing rod's end caps coincide with the board's end faces.
    # Recess those caps 5 mm, along the rod, without moving its support posts.
    gantry = bpy.data.objects["Timing gantry"]
    if not gantry.get("recessed_endcaps_v1"):
        p, _t, n = B.station_point(12)
        for v in gantry.data.vertices:
            lateral = (v.co.x - p.x) * n.x + (v.co.y - p.y) * n.y
            if v.co.z > p.z + 6.5 and abs(lateral) > 10.99:
                sign = 1 if lateral > 0 else -1
                v.co.x -= sign * n.x * 0.005
                v.co.y -= sign * n.y * 0.005
        gantry.data.update()
        gantry["recessed_endcaps_v1"] = True
    after = hashlib.sha256(
        np.asarray([v.co[:] for v in road.data.vertices], dtype="<f4").tobytes()
    ).hexdigest()
    assert before == after
    return {
        "changes": changes,
        "asphalt_vertices_unchanged": before,
        "paint_clearance_m": PAINT_CLEARANCE,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    backup = OUT / "before.blend"
    if not backup.exists():
        shutil.copy2(B.BLEND, backup)
    B.load()
    result = repair()
    (OUT / "repairs.json").write_text(json.dumps(result, indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(B.BLEND))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
