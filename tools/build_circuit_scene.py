"""Import one circuit's prepared native mesh batches through the guarded Unreal runner."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import unreal
from circuit_materials import shade

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
PALETTE = {
    "White": (0.78, 0.78, 0.74),
    "Red": (0.65, 0.035, 0.025),
    "Black": (0.012, 0.015, 0.018),
    "Steel": (0.38, 0.41, 0.42),
    "Cream": (0.63, 0.58, 0.46),
    "CanopyFabric": (0.78, 0.78, 0.74),
    "Roof": (0.14, 0.15, 0.16),
    "Glass": (0.055, 0.10, 0.13),
    "WarmGlass": (0.30, 0.22, 0.11),
    "Water": (0.035, 0.12, 0.16),
    "Trunk": (0.16, 0.105, 0.055),
    "Leaves": (0.045, 0.105, 0.025),
    "TyreRubber": (0.012, 0.014, 0.015),
    "SeatBlue": (0.055, 0.18, 0.40),
    "SeatRed": (0.50, 0.045, 0.035),
    "SeatYellow": (0.75, 0.58, 0.035),
    "Green": (0.055, 0.25, 0.10),
    "Yellow": (0.85, 0.64, 0.025),
    "Lamp": (36.0, 34.5, 31.5),
    "RunoffGreen": (0.02, 0.19, 0.065),
    "RunoffBlue": (0.025, 0.20, 0.58),
    "RunoffRed": (0.46, 0.018, 0.012),
    "RunoffOrange": (0.90, 0.23, 0.018),
    "RunoffPurple": (0.20, 0.035, 0.19),
    "RunoffViolet": (0.26, 0.07, 0.42),
}
SOURCES = {
    "Road": "/Game/Generated/Interlagos/Materials/asphalt",
    "Runoff": "/Game/Generated/Materials/rebuild_runoff_asphalt",
    "Grass": "/Game/Generated/Interlagos/Materials/infield_grass",
    "Gravel": "/Game/Generated/Materials/rebuild_sandy_gravel",
    "Concrete": "/Game/Generated/Monza/Materials/Concrete",
    "Crowd": "/Game/Generated/Monza/Materials/circuit_original_spectators",
    "Fence": "/Game/Generated/Monza/Materials/Monza_main_straight_wire",
    "TreeCanopy": "/Game/Generated/Interlagos/Materials/runtime_leaf_silhouette",
}


class Importer:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.scratch = ROOT / "build/circuits" / slug
        self.manifest = json.loads((self.scratch / "manifest.json").read_text())
        self.data = ROOT / "Content/Generated" / self.manifest["content_dir"]
        self.assets = "/Game/Generated/" + self.manifest["content_dir"].removesuffix(
            "/Data"
        )
        self.night = slug in ("bahrain", "jeddah", "singapore")
        self.copies: dict[str, unreal.MaterialInterface] = {}
        self.bounds = (0.0, 0.0, 1.0, 1.0)
        self.field = None
        recipe = (
            Path(__file__).read_bytes()
            + (ROOT / "tools/circuit_materials.py").read_bytes()
            + (ROOT / "tools/circuit_art.py").read_bytes()
        )
        for artwork in sorted((self.scratch / "art").glob("*.png")):
            recipe += (
                artwork.name.encode() + hashlib.sha256(artwork.read_bytes()).digest()
            )
        if self.night:
            recipe += (self.scratch / "night-field.json").read_bytes()
        self.material_hash = hashlib.sha256(recipe).hexdigest()
        if self.night:
            self.bounds = tuple(
                json.loads((self.scratch / "night-field.json").read_text())["bounds"]
            )
            self.field = self.texture("FloodlightField")
            self.field.set_editor_property("srgb", False)
            self.field.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_MASKS
            )
            self.field.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
            self.field.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
            LIBRARY.save_loaded_asset(self.field)

    def texture(self, name: str) -> unreal.Texture:
        source = self.scratch / "art" / (name + ".png")
        fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
        existing = unreal.load_asset(self.assets + "/Textures/" + name)
        if (
            existing is not None
            and LIBRARY.get_metadata_tag(existing, "CircuitSourceSHA256") == fingerprint
        ):
            return existing
        task = unreal.AssetImportTask()
        task.filename = str(self.scratch / "art" / (name + ".png"))
        task.destination_path = self.assets + "/Textures"
        task.destination_name = name
        task.automated = True
        task.replace_existing = True
        task.save = True
        TOOLS.import_asset_tasks([task])
        texture = unreal.load_asset(self.assets + "/Textures/" + name)
        LIBRARY.set_metadata_tag(texture, "CircuitSourceSHA256", fingerprint)
        LIBRARY.save_loaded_asset(texture)
        return texture

    def copy(
        self, name: str, source: unreal.MaterialInterface
    ) -> unreal.MaterialInterface:
        if name in self.copies:
            return self.copies[name]
        path = self.assets + "/Materials/" + name
        material = unreal.load_asset(path)
        if (
            material is not None
            and LIBRARY.get_metadata_tag(material, "CircuitMaterialRecipe")
            != self.material_hash
        ):
            if not LIBRARY.delete_asset(path):
                raise RuntimeError(f"Cannot refresh private material {path}")
            material = None
        if material is None:
            material = TOOLS.duplicate_asset(name, self.assets + "/Materials", source)
            if self.night:
                if isinstance(material, unreal.MaterialInstanceConstant):
                    parent_name = source.parent.get_name()
                    parent_hash = hashlib.sha256(
                        source.parent.get_path_name().encode()
                    ).hexdigest()[:8]
                    parent = self.copy(
                        "Parent_" + parent_name + "_" + parent_hash, source.parent
                    )
                    EDIT.set_material_instance_parent(material, parent)
                elif (
                    EDIT.get_material_property_input_node(
                        material, unreal.MaterialProperty.MP_BASE_COLOR
                    )
                    is not None
                ):
                    shade(material, self.bounds, self.field)
            if name == "Concrete" and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                EDIT.set_material_instance_scalar_parameter_value(
                    material, "NormalStrength", 0.035
                )
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(0.82, 0.82, 0.82)
                )
            ground_tints = {
                "cota": (1.4, 1.08, 0.55),
                "portimao": (1.65, 1.25, 0.65),
                "zandvoort": (1.1, 1.05, 0.85),
                "turkey": (1.25, 1.05, 0.65),
            }
            if (
                name == "Grass"
                and self.slug in ground_tints
                and isinstance(material, unreal.MaterialInstanceConstant)
            ):
                tint = EDIT.get_material_instance_vector_parameter_value(source, "Tint")
                red, green, blue = ground_tints[self.slug]
                EDIT.set_material_instance_vector_parameter_value(
                    material,
                    "Tint",
                    unreal.LinearColor(tint.r * red, tint.g * green, tint.b * blue),
                )
            LIBRARY.set_metadata_tag(
                material, "CircuitMaterialRecipe", self.material_hash
            )
            LIBRARY.save_loaded_asset(material)
        self.copies[name] = material
        return material

    def material(self, name: str) -> unreal.MaterialInterface:
        path = self.assets + "/Materials/" + name
        existing = unreal.load_asset(path)
        if (
            existing is not None
            and LIBRARY.get_metadata_tag(existing, "CircuitMaterialRecipe")
            == self.material_hash
        ):
            return existing
        if name in SOURCES:
            source = unreal.load_asset(SOURCES[name])
            if source is None:
                raise RuntimeError(f"Missing accepted source material {SOURCES[name]}")
            return self.copy(name, source)
        if existing is not None and not isinstance(existing, unreal.Material):
            if not LIBRARY.delete_asset(path):
                raise RuntimeError(f"Cannot replace private material {path}")
            existing = None
        material = existing or TOOLS.create_asset(
            name,
            self.assets + "/Materials",
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        EDIT.delete_all_material_expressions(material)
        if name in PALETTE:
            color = EDIT.create_material_expression(
                material, unreal.MaterialExpressionConstant3Vector
            )
            color.constant = unreal.LinearColor(*PALETTE[name])
            EDIT.connect_material_property(
                color, "", unreal.MaterialProperty.MP_BASE_COLOR
            )
            roughness = EDIT.create_material_expression(
                material, unreal.MaterialExpressionConstant
            )
            roughness.r = 0.22 if name in ("Glass", "WarmGlass", "Water") else 0.7
            EDIT.connect_material_property(
                roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
            )
            material.set_editor_property("two_sided", name == "Leaves")
            if name == "Lamp" or (self.night and name == "WarmGlass"):
                EDIT.connect_material_property(
                    color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
                )
            elif self.night:
                shade(material, self.bounds, self.field)
        elif (self.scratch / "art" / (name + ".png")).exists():
            texture = self.texture(name)
            sample = EDIT.create_material_expression(
                material, unreal.MaterialExpressionTextureSample
            )
            sample.texture = texture
            EDIT.connect_material_property(
                sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
            )
            if self.night:
                shade(material, self.bounds, self.field)
        else:
            raise ValueError(f"Unknown material {name} for {self.slug}")
        EDIT.recompile_material(material)
        LIBRARY.set_metadata_tag(material, "CircuitMaterialRecipe", self.material_hash)
        LIBRARY.save_loaded_asset(material)
        return material

    def build(self, batch: int, batches: int) -> None:
        names = {name for tile in self.manifest["tiles"] for name in tile["materials"]}
        materials = {name: self.material(name) for name in sorted(names)}
        for index, record in enumerate(self.manifest["tiles"]):
            if index % batches != batch:
                continue
            path = self.assets + "/Track/" + record["name"]
            mesh = unreal.load_asset(path)
            if (
                mesh is None
                or LIBRARY.get_metadata_tag(mesh, "CircuitSourceSHA256")
                != record["sha256"]
            ):
                mesh = unreal.FFLasVegasMeshLibrary.build_tile(
                    str(self.scratch / record["file"]),
                    path,
                    [materials[name] for name in record["materials"]],
                )
                if mesh is None:
                    raise RuntimeError(
                        f"Cannot build {path}, triangles={record['triangles']}"
                    )
            for slot, name in enumerate(record["materials"]):
                mesh.set_material(slot, materials[name])
            LIBRARY.set_metadata_tag(mesh, "CircuitSourceSHA256", record["sha256"])
            LIBRARY.save_loaded_asset(mesh)
            unreal.log(
                f"CIRCUIT_TILE {self.slug} {record['name']} triangles={record['triangles']}"
            )
        if batch == batches - 1:
            for record in self.manifest["tiles"]:
                mesh = unreal.load_asset(self.assets + "/Track/" + record["name"])
                if (
                    mesh is None
                    or LIBRARY.get_metadata_tag(mesh, "CircuitSourceSHA256")
                    != record["sha256"]
                ):
                    raise RuntimeError(f"Incomplete mesh batch: {record['name']}")
            self.data.joinpath("render_tiles.csv").write_text(
                "\n".join(
                    record["name"]
                    + ","
                    + ",".join(f"{v:.3f}" for v in record["bounds"])
                    for record in self.manifest["tiles"]
                )
                + "\n"
            )
            record = {
                "recipe": "make circuit-assets CIRCUIT=" + self.slug,
                "tiles": len(self.manifest["tiles"]),
                "triangles": sum(tile["triangles"] for tile in self.manifest["tiles"]),
                "road_sha256": hashlib.sha256(
                    (self.data / "drive_surface.bin").read_bytes()
                ).hexdigest(),
                "terrain_sha256": hashlib.sha256(
                    (self.data / "terrain.bin").read_bytes()
                ).hexdigest(),
                "landmarks": self.manifest["landmarks"],
                "vegetation": self.manifest["vegetation"],
                "review_status": "Awaiting packaged whole-route review; asset import is not visual approval.",
            }
            (ROOT / "Attribution/Sources" / self.slug / "scenery.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )


if __name__ == "__main__":
    command = unreal.SystemLibrary.get_command_line()
    slug_match = re.search(r"-FFCircuitAssets=([a-z]+)", command)
    batch_match = re.search(r"-FFTileBatch=(\d+)", command)
    count_match = re.search(r"-FFTileBatches=(\d+)", command)
    if slug_match is None:
        raise ValueError("Missing -FFCircuitAssets=<slug>")
    Importer(slug_match[1]).build(
        int(batch_match[1]) if batch_match else 0,
        int(count_match[1]) if count_match else 4,
    )
