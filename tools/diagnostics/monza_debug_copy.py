"""Assign suspect IDs only in build/forensics, after writing their manifest.

The GLB contains evaluated suspect objects only; foliage and non-suspects are
omitted. This is for identifying geometry, not an export parity reference.
"""

import colorsys
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/blender/tracks"))
import build_monza as B
import export_monza_runtime as E


def main():
    out = ROOT / "build/forensics/monza"
    suspects = json.loads((out / "suspects_before_debug.json").read_text())
    original = hashlib.sha256(B.BLEND.read_bytes()).hexdigest()
    B.load()
    E.OUT = out
    writer = E.Writer()
    writer.detail_texture = 0
    base_material = writer.material

    def debug_material(name):
        index = base_material(name)
        writer.doc["materials"][index]["pbrMetallicRoughness"].pop(
            "baseColorTexture", None
        )
        return index

    writer.material = debug_material
    names = json.loads((out / "triangle_objects.json").read_text())
    data = np.load(out / "triangles.npz")
    manifest = []
    for i, s in enumerate(suspects):
        name = s["name"]
        ob = bpy.data.objects[name]
        # Byte-valued sRGB colors make the manifest usable for pixel IDs.
        rgb = tuple(
            round(c * 255) / 255
            for c in colorsys.hsv_to_rgb(
                (i * 0.61803398875) % 1,
                0.55 + 0.4 * (i % 3) / 2,
                0.65 + 0.35 * (i % 5) / 4,
            )
        )
        linear = tuple(
            v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb
        )
        mat = bpy.data.materials.new(f"DEBUG_{i:03d} | {name}")
        mat.diffuse_color = (*linear, 1)
        mat.use_nodes = True
        mat.node_tree.nodes.get("Principled BSDF").inputs[
            "Base Color"
        ].default_value = (*linear, 1)
        ob.data = ob.data.copy()
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        if ob.type == "MESH":
            for p in ob.data.polygons:
                p.material_index = 0
        idx = names.index(name)
        p = data[f"p_{idx}"]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-20)
        writer.add(p, np.repeat(n[:, None, :], 3, axis=1), p[:, :, :2] / 4, mat.name)
        manifest.append(
            {**s, "debug_material": mat.name, "rgb8": [round(v * 255) for v in rgb]}
        )
    # Writer's filename is redirected inside a dedicated diagnostic subdirectory.
    E.OUT = out / "debug_export"
    E.OUT.mkdir(exist_ok=True)
    writer.finish()
    (out / "debug_materials.json").write_text(json.dumps(manifest, indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "suspects_debug.blend"), copy=True)
    assert hashlib.sha256(B.BLEND.read_bytes()).hexdigest() == original
    print("Debug copy and object IDs written; production Blender file unchanged.")


if __name__ == "__main__":
    main()
