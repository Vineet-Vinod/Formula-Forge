"""Export the surveyed Blender scene for raylib, with spatial batches and foliage cards.

uv run --no-sync --with pillow python tools/blender/tracks/export_monza_runtime.py
The authoring .blend is read only. Runtime meshes and route data share its metre frame.
"""

import argparse
import hashlib
import json
import math
import struct
from collections import defaultdict

import bpy
import build_monza as B
import numpy as np
from mathutils import Vector
from PIL import Image

OUT = B.OUT / "runtime"
ROOT = B.OUT.parents[3]
TILE = 120.0


def route():
    # Dense controls retain the surveyed chicanes through Track3D's interpolation.
    indices = range(0, B.N, 4)
    arrays = [("TrackControlPoint", "kMonzaCenterline", [B.XY[i] for i in indices])]
    stations = np.linspace(0, B.L, 773)
    arrays += [
        (
            "TrackElevationPoint",
            "kMonzaElevation",
            [(s, B.station_point(s)[0].z - 0.06) for s in stations],
        ),
        ("TrackWidthPoint", "kMonzaWidth", [(s, B.width(s)) for s in stations]),
        (
            "TrackBankPoint",
            "kMonzaBank",
            [
                (
                    s,
                    math.degrees(
                        math.atan(
                            -max(
                                -0.004,
                                min(0.004, B.CURVATURE[int(s / B.STEP) % B.N] * 0.4),
                            )
                        )
                    ),
                )
                for s in stations
            ],
        ),
    ]
    text = "// Generated from reconstruction/survey.json by export_monza_runtime.py.\n"
    for typ, name, rows in arrays:
        text += f"constexpr {typ} {name}[] = {{\n"
        text += "".join(f"    {{{float(a):.6f}f, {float(b):.6f}f}},\n" for a, b in rows)
        text += "};\n\n"
    (ROOT / "src/track_data/monza_survey.inc").write_text(text)
    elevations = [v for s, v in arrays[1][2]]
    xy = np.array(B.XY)
    return {
        "centerline_controls": len(list(indices)),
        "length_m": B.L,
        "elevation_relief_m": max(elevations) - min(elevations),
        "aspect_ratio": float(np.ptp(xy[:, 0]) / np.ptp(xy[:, 1])),
        "simulation_units_per_metre": 17,
        "render_scale": 1.445,
        "mapping": "Blender (x,y,z) -> glTF (x,z,-y); runtime world = glTF * 1.445",
        "reference_samples": [
            [s, *B.station_point(s)[0]]
            for s in np.linspace(0, B.L, 1536, endpoint=False)
        ],
    }


def foliage_atlas():
    cache = OUT / "foliage_cards.json"
    signature = hashlib.sha256(b"foliage-bake-v1" + B.BLEND.read_bytes()).hexdigest()
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved.get("signature") == signature:
            return saved["cards"]
    sc = bpy.context.scene
    for ob in bpy.data.objects:
        ob.hide_render = True
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 2
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 4
    sc.render.resolution_x = 256
    sc.render.resolution_y = 256
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.view_settings.exposure = 0
    data = bpy.data.cameras.new("Runtime foliage bake")
    cam = bpy.data.objects.new(data.name, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    atlas = Image.new("RGBA", (1536, 1536))
    cards = {}
    for kind in range(12):
        ob = bpy.data.objects[f"LIB_Tree_{kind:02d}"]
        ob.hide_render = False
        vertices = np.array([v.co[:] for v in ob.data.vertices])
        lo = vertices.min(0)
        hi = vertices.max(0)
        center = (lo + hi) / 2
        span = float(max(hi - lo) + 1)
        cards[ob.name] = []
        for view in range(3):
            cam.data.ortho_scale = span
            eye = (
                Vector(center)
                + [Vector((0, -70, 0)), Vector((70, 0, 0)), Vector((0, 0, 70))][view]
            )
            cam.location = eye
            cam.rotation_euler = (
                (Vector(center) - eye).to_track_quat("-Z", "Y").to_euler()
            )
            sc.render.filepath = str(OUT / "foliage_bake.png")
            bpy.ops.render.render(write_still=True)
            im = Image.open(sc.render.filepath).convert("RGBA")
            box = im.getchannel("A").getbbox()
            tile = kind * 3 + view
            tx = (tile % 6) * 256
            ty = (tile // 6) * 256
            atlas.paste(im, (tx, ty))
            x0, y0, x1, y1 = box
            # Camera right and up vectors match the baked projection.
            rot = cam.rotation_euler.to_matrix()
            right = rot @ Vector((1, 0, 0))
            up = rot @ Vector((0, 1, 0))
            corners = []
            for px, py in [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]:
                p = (
                    Vector(center)
                    + right * ((px / 256 - 0.5) * span)
                    + up * ((0.5 - py / 256) * span)
                )
                corners.append(list(p))
            uv = [
                [(tx + px) / 1536, 1 - (ty + py) / 1536]
                for px, py in [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]
            ]
            cards[ob.name].append({"vertices": corners, "uv": uv})
        ob.hide_render = True
    atlas.save(OUT / "foliage.png")
    (OUT / "foliage_bake.png").unlink()
    cache.write_text(
        json.dumps({"signature": signature, "cards": cards}, indent=2) + "\n"
    )
    return cards


class Writer:
    def __init__(self):
        self.data = bytearray()
        self.doc = {
            "asset": {
                "version": "2.0",
                "generator": "Formula Forge Blender survey exporter",
                "copyright": "OpenStreetMap contributors, ODbL 1.0",
            },
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "bufferViews": [],
            "accessors": [],
            "images": [],
            "textures": [],
            "samplers": [
                {"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}
            ],
        }
        self.batches = defaultdict(list)
        self.materials = {}
        self.triangles = 0

    def blob(self, data):
        self.data.extend(b"\0" * ((-len(self.data)) % 4))
        offset = len(self.data)
        self.data.extend(data)
        i = len(self.doc["bufferViews"])
        self.doc["bufferViews"].append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        )
        return i

    def accessor(self, a, typ, component=5126, bounds=False, normalized=False):
        entry = {
            "bufferView": self.blob(a.tobytes()),
            "componentType": component,
            "count": len(a),
            "type": typ,
        }
        if bounds:
            entry.update(min=a.min(axis=0).tolist(), max=a.max(axis=0).tolist())
        if normalized:
            entry["normalized"] = True
        i = len(self.doc["accessors"])
        self.doc["accessors"].append(entry)
        return i

    def texture(self, path):
        i = len(self.doc["images"])
        self.doc["images"].append(
            {"bufferView": self.blob(path.read_bytes()), "mimeType": "image/png"}
        )
        self.doc["textures"].append({"source": i, "sampler": 0})
        return i

    def material(self, name):
        if name in self.materials:
            return self.materials[name]
        source = bpy.data.materials.get(name)
        color = np.array(source.diffuse_color[:3] if source else [0.2, 0.3, 0.1])
        color = np.where(
            color <= 0.0031308, 12.92 * color, 1.055 * color ** (1 / 2.4) - 0.055
        )
        m = {
            "name": name,
            "doubleSided": True,
            "pbrMetallicRoughness": {
                "baseColorFactor": [float(v) for v in color] + [1],
                "metallicFactor": 0.6 if name in ["Armco", "Fence"] else 0,
                "roughnessFactor": 0.85,
            },
        }
        if name == "Runtime_foliage":
            m["pbrMetallicRoughness"].update(
                baseColorFactor=[1, 1, 1, 1],
                baseColorTexture={"index": self.foliage_texture},
            )
            m.update(alphaMode="MASK", alphaCutoff=0.35)
        elif name == "Runtime_wire":
            m["pbrMetallicRoughness"].update(
                baseColorFactor=[0.45, 0.48, 0.46, 1],
                baseColorTexture={"index": self.wire_texture},
            )
            m.update(alphaMode="MASK", alphaCutoff=0.35)
        else:
            m["pbrMetallicRoughness"]["baseColorTexture"] = {
                "index": self.detail_texture
            }
        index = len(self.doc["materials"])
        self.doc["materials"].append(m)
        self.materials[name] = index
        return index

    def add(self, positions, normals, uv, mat, colors=None):
        # Positions are triangle corners in Blender coordinates.
        if not len(positions):
            return
        centers = positions.mean(axis=1)
        tiles = np.floor(centers[:, :2] / TILE).astype(int)
        color = (
            np.ones((*positions.shape[:2], 4), dtype=np.float32)
            if colors is None
            else colors
        )
        for tile in np.unique(tiles, axis=0):
            mask = np.all(tiles == tile, axis=1)
            self.batches[(int(tile[0]), int(tile[1]), mat)].append(
                (positions[mask], normals[mask], uv[mask], color[mask])
            )

    def finish(self):
        low = np.full(3, np.inf)
        high = -low
        for (tx, ty, mat), parts in self.batches.items():
            p, n, u, c = [
                np.concatenate([part[i] for part in parts]).reshape(-1, size)
                for i, size in enumerate([3, 3, 2, 4])
            ]
            p = p[:, [0, 2, 1]]
            p[:, 2] *= -1
            n = n[:, [0, 2, 1]]
            n[:, 2] *= -1
            low = np.minimum(low, p.min(0))
            high = np.maximum(high, p.max(0))
            for start in range(0, len(p), 60000):
                sl = slice(start, start + 60000)
                colors = (
                    np.round(np.clip(c[sl], 0, 1) * 255)
                    if mat == "Asphalt"
                    else np.full((len(p[sl]), 4), 255)
                )
                packed = np.column_stack([p[sl], n[sl], u[sl], colors]).astype("<f4")
                unique, indices = np.unique(packed, axis=0, return_inverse=True)
                indices = indices.astype("<u2")
                attrs = {
                    "POSITION": self.accessor(
                        unique[:, :3].copy(), "VEC3", bounds=True
                    ),
                    "NORMAL": self.accessor(unique[:, 3:6].copy(), "VEC3"),
                    "TEXCOORD_0": self.accessor(unique[:, 6:8].copy(), "VEC2"),
                    "COLOR_0": self.accessor(
                        unique[:, 8:].astype("u1"), "VEC4", 5121, normalized=True
                    ),
                }
                if mat != "Asphalt":
                    # Constant white vertex color is implicit in glTF.
                    attrs.pop("COLOR_0")
                    self.doc["accessors"].pop()
                    view = self.doc["bufferViews"].pop()
                    del self.data[view["byteOffset"] :]
                mesh = {
                    "name": f"{mat} {tx} {ty} {start // 60000}",
                    "primitives": [
                        {
                            "attributes": attrs,
                            "indices": self.accessor(indices, "SCALAR", 5123),
                            "material": self.material(mat),
                            "mode": 4,
                        }
                    ],
                }
                i = len(self.doc["meshes"])
                self.doc["meshes"].append(mesh)
                self.doc["nodes"].append({"mesh": i, "name": mesh["name"]})
                self.doc["scenes"][0]["nodes"].append(i)
                self.triangles += len(indices) // 3
        self.doc["buffers"] = [{"byteLength": len(self.data)}]
        text = json.dumps(self.doc, separators=(",", ":")).encode()
        text += b" " * ((-len(text)) % 4)
        self.data.extend(b"\0" * ((-len(self.data)) % 4))
        content = (
            struct.pack("<III", 0x46546C67, 2, 28 + len(text) + len(self.data))
            + struct.pack("<II", len(text), 0x4E4F534A)
            + text
            + struct.pack("<II", len(self.data), 0x004E4942)
            + self.data
        )
        (OUT / "monza.glb").write_bytes(content)
        return {
            "triangles": self.triangles,
            "meshes": len(self.doc["meshes"]),
            "bytes": len(content),
            "bounds_gltf": [low.tolist(), high.tolist()],
        }


def mesh_arrays(ob, dg):
    if "individual seats" in ob.name or ob.name == "LIB_Tyre_stack":
        mod = ob.modifiers.new("Runtime simplification", "DECIMATE")
        mod.ratio = 0.30 if "individual seats" in ob.name else 0.18
        dg.update()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    verts = np.array([v.co[:] for v in me.vertices], dtype=np.float32)
    ids = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int32)
    normals = np.array(
        [t.normal[:] for t in me.loop_triangles], dtype=np.float32
    ).reshape(-1, 3)
    mats = [m.name for m in me.materials]
    mi = np.array([t.material_index for t in me.loop_triangles])
    p = verts[ids] if len(ids) else np.empty((0, 3, 3))
    n = np.repeat(normals[:, None, :], 3, axis=1)
    if len(ids) and (
        ob.name.startswith(
            (
                "ASPHALT |",
                "Park ground",
                "L grass",
                "R grass",
                "L drainage",
                "R drainage",
                "Pit lane",
            )
        )
    ):
        n = np.array([v.normal[:] for v in me.vertices], dtype=np.float32)[ids]
    ev.to_mesh_clear()
    return p, n, mi, mats


def emit(w, p, n, mi, mats, matrix=None):
    if not len(p):
        return
    if matrix is not None:
        m = np.array(matrix)
        p = p @ m[:3, :3].T + m[:3, 3]
        n = n @ np.linalg.inv(m[:3, :3])
        n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-8)
    # Triplanar UV projection; four metres per repeat, including vertical walls.
    axis = np.abs(n[:, 0]).argmax(1)
    uv = np.empty((*p.shape[:2], 2), dtype=np.float32)
    for a, axes in [(0, [1, 2]), (1, [0, 2]), (2, [0, 1])]:
        uv[axis == a] = p[axis == a][:, :, axes] / 4
    for index, name in enumerate(mats):
        mask = mi == index
        color = np.ones((int(mask.sum()), 3, 4), np.float32)
        q = p[mask]
        variation = 0.95 + 0.05 * np.sin(
            q[:, :, 0] * 0.73 + np.sin(q[:, :, 1] * 0.38)
        ) * np.sin(q[:, :, 2] * 1.3 + q[:, :, 1] * 0.27)
        color[:, :, :3] *= variation[:, :, None]
        if name == "Asphalt":
            # Longitudinal rubber band stays inside the continuous racing road.
            for j, triangle in enumerate(q):
                for k, v in enumerate(triangle):
                    _, i, d = B.TREE.find((float(v[0]), float(v[1]), 0))
                    if (
                        d < B.width(i * B.STEP) / 2
                        and abs(float(v[2]) - B.road_z(i)) < 0.15
                    ):
                        color[j, k, :3] *= 1 - 0.16 * math.exp(
                            -(((d - 1.4) / 1.6) ** 2)
                        )
        w.add(q, n[mask], uv[mask], name, color)


def runtime_grid(w):
    result = []
    length = 83.6 / 17
    for slot in range(11):
        s = B.L - (length / 2 + 1) - slot * (length + 12)
        lane = -2.0 if slot % 2 == 0 else 2.0
        sl = length + 0.68
        sw = 2.25
        rectangles = []
        for offset in [-sw / 2, sw / 2]:
            rectangles.append(
                (s - sl / 2, s + sl / 2, lane + offset - 0.08, lane + offset + 0.08)
            )
        for offset in [-sl / 2, sl / 2]:
            rectangles.append(
                (s + offset - 0.08, s + offset + 0.08, lane - sw / 2, lane + sw / 2)
            )
        for a, b, l, r in rectangles:
            p = np.array(
                [
                    B.station_point(d, o, 0.012)[0]
                    for d, o in [(a, l), (b, l), (b, r), (a, r)]
                ]
            )[[0, 1, 2, 0, 2, 3]].reshape(2, 3, 3)
            w.add(p, np.tile([[[0, 0, 1]]], (2, 3, 1)), p[:, :, :2] / 4, "White_paint")
        result.append(
            {
                "slot": slot,
                "distance_m": s,
                "lane_blender_m": lane,
                "center_blender": list(B.station_point(s, lane)[0]),
            }
        )
    return result


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    B.load()
    alignment = route()
    cards = foliage_atlas()
    # Reload restores visibility, lighting and evaluated geometry after baking cards.
    B.load()
    dg = bpy.context.evaluated_depsgraph_get()
    w = Writer()
    rng = np.random.default_rng(713)
    noise = rng.uniform(0.70, 1, (256, 256))
    noise = np.repeat(noise[:, :, None], 4, 2)
    noise[:, :, 3] = 1
    Image.fromarray((noise * 255).astype("uint8")).save(OUT / "surface_detail.png")
    yy, xx = np.mgrid[:128, :128]
    a = (np.minimum((xx + yy) % 128, 128 - (xx + yy) % 128) < 3) | (
        np.minimum((xx - yy) % 128, 128 - (xx - yy) % 128) < 3
    )
    rgba = np.ones((128, 128, 4), dtype=np.uint8) * 255
    rgba[:, :, 3] = a * 255
    Image.fromarray(rgba).save(OUT / "wire.png")
    w.foliage_texture = w.texture(OUT / "foliage.png")
    w.detail_texture = w.texture(OUT / "surface_detail.png")
    w.wire_texture = w.texture(OUT / "wire.png")
    prototypes = {}
    count = defaultdict(int)
    for ob in list(bpy.data.objects):
        if any(
            c.name in ["Asset_library", "QA_cameras", "Survey_curves"]
            for c in ob.users_collection
        ):
            continue
        if ob.name == "Distant ground horizon" or ob.name.startswith("Grid "):
            continue
        if ob.type not in ["MESH", "FONT", "CURVE"]:
            continue
        if ob.type == "MESH" and "instance_scale" in ob.data.attributes:
            node = next(
                n
                for n in ob.modifiers[0].node_group.nodes
                if n.bl_idname == "GeometryNodeObjectInfo"
            )
            proto = node.inputs["Object"].default_value
            scales = ob.data.attributes["instance_scale"]
            angles = ob.data.attributes["instance_rotation"]
            if proto.name not in prototypes and not proto.name.startswith("LIB_Tree"):
                prototypes[proto.name] = mesh_arrays(proto, dg)
            for i, v in enumerate(ob.data.vertices):
                scale = np.array(scales.data[i].vector)
                angle = angles.data[i].vector.z
                if min(scale) <= 0:
                    continue
                ca, sa = math.cos(angle), math.sin(angle)
                matrix = np.eye(4)
                matrix[:3, :3] = np.array(
                    [[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]]
                ) @ np.diag(scale)
                matrix[:3, 3] = v.co[:]
                count[proto.name] += 1
                if proto.name.startswith("LIB_Tree"):
                    for card in cards[proto.name]:
                        p = np.array(card["vertices"])[[0, 1, 2, 0, 2, 3]].reshape(
                            2, 3, 3
                        )
                        p = p @ matrix[:3, :3].T + matrix[:3, 3]
                        normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
                        normal /= np.linalg.norm(normal, axis=1)[:, None]
                        # Upward ambient helps the baked canopy retain its leaf detail.
                        normal = normal * 0.3 + np.array([0, 0, 0.7])
                        normal /= np.linalg.norm(normal, axis=1)[:, None]
                        uv = np.array(card["uv"])[[0, 1, 2, 0, 2, 3]].reshape(2, 3, 2)
                        uv[:, :, 1] = 1 - uv[:, :, 1]  # glTF texture origin is top left
                        w.add(
                            p,
                            np.repeat(normal[:, None, :], 3, axis=1),
                            uv,
                            "Runtime_foliage",
                        )
                elif proto.name == "LIB_Fence_4m":
                    p, n, mi, mats = prototypes[proto.name]
                    emit(w, p[:28], n[:28], mi[:28], mats, matrix)  # two post rods
                    p = np.array(
                        [[-2, 0, 0.25], [2, 0, 0.25], [2, 0, 3.25], [-2, 0, 3.25]]
                    )[[0, 1, 2, 0, 2, 3]].reshape(2, 3, 3)
                    uv = p[:, :, [0, 2]] / 0.17
                    p = p @ matrix[:3, :3].T + matrix[:3, 3]
                    normal = np.repeat(np.array([[[sa, -ca, 0]]]), 6, axis=1).reshape(
                        2, 3, 3
                    )
                    w.add(p, normal, uv, "Runtime_wire")
                elif proto.name == "LIB_Grass_tuft":
                    if i % 3 == 0:
                        emit(w, *prototypes[proto.name], matrix)
                else:
                    emit(w, *prototypes[proto.name], matrix)
            print("instances", ob.name, flush=True)
        else:
            emit(w, *mesh_arrays(ob, dg), ob.matrix_world)
    grid = runtime_grid(w)
    result = w.finish()
    result.update(
        grid_slots=grid,
        alignment=alignment,
        instances=dict(count),
        source_sha256=hashlib.sha256(B.BLEND.read_bytes()).hexdigest(),
        source="../monza_reconstruction.blend",
        runtime_lods="Three orthogonal cutout views baked from each authored tree; wire cutouts retain 170 mm pitch; 120 m spatial batches",
        authoring_scene_unchanged=True,
    )
    (OUT / "monza.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "alignment"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    export()
