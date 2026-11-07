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
EDIT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def solid(name: str, color: tuple[float, float, float], roughness: float, two_sided: bool = False) -> unreal.Material:
    material = unreal.load_asset(ASSETS + "/Materials/" + name)
    if material is None:
        material = TOOLS.create_asset(name, ASSETS + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(material)
    rgb = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    rgb.constant = unreal.LinearColor(*color)
    EDIT.connect_material_property(rgb, "", unreal.MaterialProperty.MP_BASE_COLOR)
    shine = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    shine.r = roughness
    EDIT.connect_material_property(shine, "", unreal.MaterialProperty.MP_ROUGHNESS)
    material.set_editor_property("two_sided", two_sided)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)
    return material


def duplicate(name: str, source_path: str) -> unreal.MaterialInterface:
    source = unreal.load_asset(source_path)
    if source is None:
        raise RuntimeError(f"Missing material {source_path}")
    destination = ASSETS + "/Materials/" + name
    if LIBRARY.does_asset_exist(destination) and not LIBRARY.delete_asset(destination):
        raise RuntimeError(f"Cannot replace {destination}")
    copied = TOOLS.duplicate_asset(name, ASSETS + "/Materials", source)
    LIBRARY.save_loaded_asset(copied)
    return copied


def main() -> None:
    manifest = json.loads((SCRATCH / "manifest.json").read_text())
    # Road and grass shaders are the game's accepted surfaces, copied into Suzuka's folder.
    # The stands, pits, wheel and kerbs are Suzuka colours, not another circuit's scenery.
    loaded = {
        "Road": duplicate("SuzukaAsphalt", "/Game/Generated/Materials/rebuild_road_asphalt"),
        "Grass": duplicate("SuzukaGrass", "/Game/Generated/Interlagos/Materials/infield_grass"),
        "Line": solid("SuzukaLine", (0.82, 0.82, 0.78), 0.55),
        "KerbRed": solid("SuzukaKerbRed", (0.62, 0.04, 0.03), 0.6),
        "KerbWhite": solid("SuzukaKerbWhite", (0.78, 0.78, 0.74), 0.55),
        "Gravel": solid("SuzukaGravel", (0.45, 0.38, 0.28), 0.92),
        "Armco": solid("SuzukaArmco", (0.62, 0.63, 0.60), 0.42),
        "Concrete": solid("SuzukaConcrete", (0.58, 0.56, 0.52), 0.82),
        "SeatA": solid("SuzukaSeatRed", (0.42, 0.07, 0.06), 0.75),
        "SeatB": solid("SuzukaSeatBlue", (0.10, 0.16, 0.30), 0.75),
        "Roof": solid("SuzukaRoof", (0.07, 0.075, 0.08), 0.7),
        "Pit": solid("SuzukaPit", (0.70, 0.68, 0.63), 0.78),
        "Garage": solid("SuzukaGarage", (0.015, 0.016, 0.018), 0.9),
        "Steel": solid("SuzukaSteel", (0.25, 0.27, 0.28), 0.45),
        "Trunk": solid("SuzukaTrunk", (0.16, 0.11, 0.06), 0.9),
        "White": solid("SuzukaWheel", (0.78, 0.78, 0.75), 0.4),
        "Red": solid("SuzukaGondola", (0.55, 0.03, 0.025), 0.55),
        "Glass": solid("SuzukaGlass", (0.05, 0.08, 0.10), 0.15, two_sided=True),
    }
    # The same original spectator atlas Las Vegas uses on its grandstands.
    loaded["Crowd"] = duplicate("SuzukaCrowd", "/Game/Generated/Monza/Materials/circuit_original_spectators")
    loaded["Leaf"] = duplicate("SuzukaFoliage", "/Game/Generated/Interlagos/Materials/runtime_leaf_silhouette")
    loaded["Seats"] = loaded["SeatA"]
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
