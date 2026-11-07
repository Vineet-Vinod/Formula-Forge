#!/usr/bin/env python3
"""Import Suzuka tiles. Run after tools/suzuka_scene.py, through tools/unreal.sh python."""

from __future__ import annotations

import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "build" / "suzuka"
ASSETS = "/Game/Generated/Japan"
LIBRARY = unreal.EditorAssetLibrary
MATERIALS = {
    "Road": "/Game/Generated/Interlagos/Materials/asphalt",
    "Line": "/Game/Generated/Interlagos/Materials/curb_white",
    "KerbRed": "/Game/Generated/Interlagos/Materials/curb_primary",
    "KerbWhite": "/Game/Generated/Interlagos/Materials/curb_white",
    "Grass": "/Game/Generated/Interlagos/Materials/infield_grass",
    "Gravel": "/Game/Generated/Monza/Materials/Gravel",
    "Concrete": "/Game/Generated/Interlagos/Materials/grandstand_concrete",
    "Seats": "/Game/Generated/Interlagos/Materials/mapped_seating",
    "Roof": "/Game/Generated/Interlagos/Materials/mapped_roof_metal",
    "Crowd": "/Game/Generated/Interlagos/Materials/Interlagos_spectators",
    "Leaf": "/Game/Generated/Interlagos/Materials/runtime_leaf_silhouette",
    "Trunk": "/Game/Generated/Monza/Materials/Soil",
    "White": "/Game/Generated/Monza/Materials/White_paint",
    "Red": "/Game/Generated/Monza/Materials/Red_paint",
    "Armco": "/Game/Generated/Monza/Materials/Armco",
    "Steel": "/Game/Generated/Interlagos/Materials/gantry_metal",
    "Glass": "/Game/Generated/Monza/Materials/Glass",
}


def main() -> None:
    manifest = json.loads((SCRATCH / "manifest.json").read_text())
    loaded = {}
    for key, path in MATERIALS.items():
        material = unreal.load_asset(path)
        if material is None:
            raise RuntimeError(f"Missing material {path}")
        loaded[key] = material
    LIBRARY.make_directory(ASSETS + "/Track")
    lines = []
    for record in manifest["tiles"]:
        destination = ASSETS + "/Track/" + record["name"]
        materials = [loaded[name] for name in record["materials"]]
        mesh = unreal.FFLasVegasMeshLibrary.build_tile(str(SCRATCH / record["file"]), destination, materials)
        if mesh is None:
            raise RuntimeError(f"Could not build {record['name']}")
        LIBRARY.save_loaded_asset(mesh)
        lines.append(record["name"] + "," + ",".join(f"{bound:.3f}" for bound in record["bounds"]))
        unreal.log(f"suzuka tile {record['name']} {record['materials']}")
    data = ROOT / "Content/Generated/Japan/Data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "render_tiles.csv").write_text("\n".join(lines) + "\n")
    unreal.log(f"suzuka: wrote {len(lines)} tiles")


if __name__ == "__main__":
    main()
