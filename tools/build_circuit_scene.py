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
    "FlyerSteel": (0.14, 0.15, 0.16),
    "Cream": (0.63, 0.58, 0.46),
    "JeddahApronPink": (.63, .035, .26),
    "JeddahApronCyan": (.025, .44, .52),
    "JeddahApronOrange": (.81, .16, .025),
    "JeddahApronYellow": (.83, .63, .035),
    "JeddahPitSignalGreen": (.04, 8.0, .20),
    "JeddahPitSignalOff": (.015, .006, .006),
    "JeddahEditionStone": (.53, .50, .44),
    "JeddahEditionCharcoal": (.025, .024, .022),
    "JeddahEditionRoomGlass": (.014, .017, .018),
    "JeddahEditionGuardGlass": (.08, .09, .09),
    "MonacoRuscinoRose": (0.56, 0.36, 0.32),
    "MonacoBruyeresRed": (0.30, 0.035, 0.045),
    "MonacoBruyeresStone": (0.78, 0.72, 0.60),
    "MonacoBruyeresWood": (0.20, 0.08, 0.03),
    "MonacoMontjoieCream": (0.78, 0.70, 0.52),
    "MonacoMontjoieWood": (0.22, 0.09, 0.03),
    "MonacoMontjoieBlueRoof": (0.025, 0.14, 0.20),
    "MonacoChapelOchre": (0.72, 0.64, 0.43),
    "MonacoChapelStone": (0.83, 0.78, 0.63),
    "MonacoChapelDoor": (0.16, 0.088, 0.035),
    "MonacoChapelDarkGlass": (0.018, 0.024, 0.020),
    "MonacoChapelIron": (0.035, 0.035, 0.028),
    "MonacoChapelWoodTrim": (0.26, 0.15, 0.08),
    "MonacoChapelRecess": (0.42, 0.35, 0.23),
    "MonacoBambooCane": (0.09, 0.14, 0.035),
    "MonacoBambooLeafDeep": (0.025, 0.08, 0.012),
    "MonacoBambooLeafMid": (0.05, 0.13, 0.02),
    "MonacoRomeStucco": (0.783537792, 0.693871761, 0.527115126),
    "MonacoRomePinkMarble": (0.584078418, 0.356400144, 0.300543794),
    "MonacoRomeMoulding": (0.871367119, 0.799102738, 0.644479682),
    "MonacoRomeIron": (0.035601315, 0.045186204, 0.039546235),
    "MonacoRomeSlate": (0.130136477, 0.184474995, 0.194617830),
    "MonacoRomeShutter": (0.141263291, 0.059511238, 0.023153366),
    "MonacoRomeRoofSoil": (0.070360096, 0.046665086, 0.028426040),
    "MonacoRomeRoofPlant": (0.088655586, 0.029556834, 0.036889450),
    "MonacoTerraceStoneLight": (0.578, 0.558, 0.479),
    "MonacoTerraceStoneMid": (0.445, 0.434, 0.361),
    "MonacoTerraceStoneDark": (0.319, 0.309, 0.250),
    "MonacoTerraceMortar": (0.258, 0.250, 0.202),
    "BakuSkyGlass": (0.10, 0.17, 0.23),
    "BakuSkyGlassLight": (0.18, 0.25, 0.29),
    "BakuPhilharmonicOchre": (0.72, 0.52, 0.22),
    "BakuHotelCopper": (0.20, 0.36, 0.29),
    "BakuOxideRoof": (0.32, 0.065, 0.045),
    "BakuFoundationBlueRoof": (0.035, 0.11, 0.24),
    "BakuFoundationRecess": (0.17, 0.14, 0.10),
    "CanopyFabric": (0.78, 0.78, 0.74),
    "Roof": (0.14, 0.15, 0.16),
    "JeddahConstruction": (0.19, 0.17, 0.145),
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
    "RunoffNavy": (0.005182, 0.010960, 0.045186),
    "RunoffBlack": (0.003035, 0.003035, 0.003035),
    "RunoffRed": (0.46, 0.018, 0.012),
    "RunoffOrange": (0.90, 0.23, 0.018),
    "RunoffPurple": (0.20, 0.035, 0.19),
    "RunoffViolet": (0.26, 0.07, 0.42),
}
ROUGHNESS = {
    "MonacoRomeStucco": 0.9,
    "MonacoRomePinkMarble": 0.85,
    "MonacoRomeMoulding": 0.86,
    "MonacoRomeIron": 0.72,
    "MonacoRomeSlate": 0.78,
    "MonacoRomeShutter": 0.8,
    "MonacoRomeRoofSoil": 0.98,
    "MonacoRomeRoofPlant": 0.92,
    "MonacoTerraceStoneLight": 0.96,
    "MonacoTerraceStoneMid": 0.97,
    "MonacoTerraceStoneDark": 0.97,
    "MonacoTerraceMortar": 0.98,
    "BakuFoundationBlueRoof": 0.38,
    "BakuFoundationRecess": 0.96,
    "MonacoBruyeresRed": 0.82,
    "MonacoBruyeresStone": 0.78,
    "MonacoBruyeresWood": 0.62,
    "MonacoMontjoieCream": 0.82,
    "MonacoMontjoieWood": 0.60,
    "MonacoMontjoieBlueRoof": 0.34,
    "MonacoChapelOchre": 0.90,
    "MonacoChapelStone": 0.86,
    "MonacoChapelDoor": 0.68,
    "MonacoChapelDarkGlass": 0.30,
    "MonacoChapelIron": 0.78,
    "MonacoChapelWoodTrim": 0.70,
    "MonacoChapelRecess": 0.90,
    "MonacoBambooCane": 0.78,
    "MonacoBambooLeafDeep": 0.80,
    "MonacoBambooLeafMid": 0.78,
}
SOURCES = {
    "Road": "/Game/Generated/Interlagos/Materials/asphalt",
    "Runoff": "/Game/Generated/Materials/rebuild_runoff_asphalt",
    "JeddahWorkingAsphalt": "/Game/Generated/Materials/rebuild_runoff_asphalt",
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
        self.road_floor = 0.05 if slug == "bahrain" else 0.15
        self.emissive_scale = .20 if slug == "jeddah" else 1.0
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
        if self.slug == "monaco":
            recipe += (ROOT / "tools/venues/monaco_rock_material.py").read_bytes()
        if self.slug == "jeddah":
            recipe += (ROOT / "tools/venues/jeddah_sky_material.py").read_bytes()
        self.material_hash = hashlib.sha256(recipe).hexdigest()
        if self.slug == "jeddah":
            from venues.jeddah_sky_material import build_reflection, build_sky

            build_sky(self.assets + "/Materials/JeddahNightSky", self.material_hash)
            build_reflection(self.scratch / "art/JeddahNightReflection.hdr",
                             self.assets + "/Environment/JeddahNightReflection")
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
                    shade(material, self.bounds, self.field, self.road_floor, self.emissive_scale, self.slug == "jeddah")
            if self.slug in ("baku", "monaco") and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                for parameter in EDIT.get_scalar_parameter_names(material):
                    if str(parameter) in ("UseBakedAO", "UseVertexColor"):
                        EDIT.set_material_instance_scalar_parameter_value(material, parameter, 0.0)
            if name == "Concrete" and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                EDIT.set_material_instance_scalar_parameter_value(
                    material, "NormalStrength", 0.035
                )
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(0.82, 0.82, 0.82)
                )
            if self.slug == "monaco" and name in ("Limestone", "Terracotta", "MonacoShutter") and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                tint = {"Limestone": (0.94, 0.82, 0.66),
                        "Terracotta": (0.62, 0.26, 0.12),
                        "MonacoShutter": (0.045, 0.10, 0.065)}[name]
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(*tint)
                )
                EDIT.set_material_instance_scalar_parameter_value(material, "Roughness", 1.0)
                EDIT.set_material_instance_scalar_parameter_value(material, "NormalStrength", 0.12 if name == "Limestone" else 0.08)
            if self.slug == "baku" and name == "BakuStone" and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(0.70, 0.62, 0.49)
                )
                EDIT.set_material_instance_scalar_parameter_value(material, "Roughness", 0.9)
                EDIT.set_material_instance_scalar_parameter_value(material, "NormalStrength", 0.12)
            if self.slug == "monaco" and name in ("MonacoIvyGround", "MonacoRockGround") and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                tint = ((0.48, 0.70, 0.40) if name == "MonacoIvyGround"
                        else (0.68, 0.66, 0.61))
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(*tint)
                )
                EDIT.set_material_instance_scalar_parameter_value(material, "Roughness", 0.95)
                EDIT.set_material_instance_scalar_parameter_value(material, "NormalStrength", 0.18)
            if self.slug == "monaco" and name == "MonacoGardenLawn" and isinstance(
                material, unreal.MaterialInstanceConstant
            ):
                tint = EDIT.get_material_instance_vector_parameter_value(source, "Tint")
                EDIT.set_material_instance_vector_parameter_value(
                    material, "Tint", unreal.LinearColor(tint.r * .70, tint.g * .83, tint.b * .60)
                )
                EDIT.set_material_instance_scalar_parameter_value(material, "Roughness", .95)
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
        if self.slug == "jeddah" and name == "JeddahHospitalityGlass":
            from venues.jeddah_hospitality_material import build

            return build(self.assets)
        if self.slug == "baku" and name == "BakuSahilCanopy":
            from venues.baku_sahil_material import build

            return build(ROOT, self.assets)
        path = self.assets + "/Materials/" + name
        existing = unreal.load_asset(path)
        if (
            existing is not None
            and LIBRARY.get_metadata_tag(existing, "CircuitMaterialRecipe")
            == self.material_hash
        ):
            return existing
        if self.slug == "monaco" and name == "MonacoRockGround":
            from venues.monaco_rock_material import build, import_textures

            parent_path = self.assets + "/Materials/MonacoRockBase"
            parent = unreal.load_asset(parent_path) or TOOLS.create_asset(
                "MonacoRockBase", self.assets + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
            if not isinstance(parent, unreal.Material):
                raise TypeError("The private rock parent must remain a Material")
            EDIT.delete_all_material_expressions(parent)
            build(parent, import_textures(ROOT, self.assets), mixed=False)
            EDIT.recompile_material(parent)
            LIBRARY.set_metadata_tag(parent, "CircuitMaterialRecipe", self.material_hash)
            LIBRARY.save_loaded_asset(parent)
            material = existing or TOOLS.create_asset(
                name, self.assets + "/Materials", unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew())
            if not isinstance(material, unreal.MaterialInstanceConstant):
                raise TypeError("Existing mesh imports require the public rock MaterialInstanceConstant")
            EDIT.set_material_instance_parent(material, parent)
            LIBRARY.set_metadata_tag(material, "CircuitMaterialRecipe", self.material_hash)
            LIBRARY.save_loaded_asset(material)
            return material
        if self.slug == "monaco" and name == "MonacoNaturalGround":
            from venues.monaco_rock_material import build, import_textures

            material = existing or TOOLS.create_asset(
                name, self.assets + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
            if not isinstance(material, unreal.Material):
                raise TypeError("Natural ravine cover requires its own source material")
            EDIT.delete_all_material_expressions(material)
            build(material, import_textures(ROOT, self.assets), mixed=True)
            EDIT.recompile_material(material)
            LIBRARY.set_metadata_tag(material, "CircuitMaterialRecipe", self.material_hash)
            LIBRARY.save_loaded_asset(material)
            return material
        if self.slug == "monaco" and name in ("MonacoIvyGround", "MonacoGardenLawn"):
            source_name = "Grass"
            source = unreal.load_asset(SOURCES[source_name])
            if source is None:
                raise RuntimeError(f"Missing accepted {source_name} source for {name}")
            return self.copy(name, source)
        if (self.slug == "monaco" and name in ("Limestone", "Terracotta", "MonacoShutter")) or (
            self.slug == "baku" and name == "BakuStone"
        ):
            source = unreal.load_asset(SOURCES["Concrete"])
            if source is None:
                raise RuntimeError(f"Missing accepted Concrete source for {self.slug} masonry")
            return self.copy(name, source)
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
            if self.slug == "jeddah" and name == "Water":
                color.constant = unreal.LinearColor(.003, .009, .014)
            EDIT.connect_material_property(
                color, "", unreal.MaterialProperty.MP_BASE_COLOR
            )
            if self.slug == "singapore" and name == "FlyerSteel":
                metal = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                metal.r = 0.65
                EDIT.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
            if self.slug == "baku" and name == "BakuHotelCopper":
                metal = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                metal.r = .20
                EDIT.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
            roughness = EDIT.create_material_expression(
                material, unreal.MaterialExpressionConstant
            )
            roughness.r = 0.22 if name in ("Glass", "WarmGlass", "Water", "BakuSkyGlass", "BakuSkyGlassLight") else 0.7
            roughness.r = ROUGHNESS.get(name, roughness.r)
            if self.slug == "baku" and name == "BakuHotelCopper":
                roughness.r = .55
            if self.slug == "baku" and name == "BakuOxideRoof":
                roughness.r = .95
            if self.slug == "monaco" and name == "MonacoRuscinoRose":
                roughness.r = 0.85
            if self.slug == "jeddah" and name == "JeddahConstruction":
                roughness.r = 0.94
            if name.startswith("JeddahApron"):
                roughness.r = .85
            if name.startswith("JeddahEdition"):
                roughness.r = {"JeddahEditionStone": .85, "JeddahEditionCharcoal": .88,
                               "JeddahEditionRoomGlass": .42, "JeddahEditionGuardGlass": .18}[name]
            EDIT.connect_material_property(
                roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
            )
            if self.slug == "monaco" and name in (
                "MonacoTerraceStoneLight", "MonacoTerraceStoneMid",
                "MonacoTerraceStoneDark", "MonacoTerraceMortar",
            ):
                specular = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                specular.r = .15
                EDIT.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
            material.set_editor_property("two_sided", name == "Leaves")
            if name in ("JeddahEditionRoomGlass", "JeddahEditionGuardGlass"):
                specular = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                specular.r = .12
                EDIT.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
            if name == "JeddahEditionGuardGlass":
                material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
                material.set_editor_property("two_sided", True)
                material.set_editor_property("translucency_lighting_mode",
                                             unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
                opacity = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                opacity.r = .12
                EDIT.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
            if name in ("Lamp", "JeddahPitSignalGreen") or (self.night and name == "WarmGlass"):
                EDIT.connect_material_property(
                    color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
                )
            elif self.night:
                shade(material, self.bounds, self.field, self.road_floor, self.emissive_scale, self.slug == "jeddah")
        elif (self.scratch / "art" / (name + ".png")).exists():
            texture = self.texture(name)
            sample = EDIT.create_material_expression(
                material, unreal.MaterialExpressionTextureSample
            )
            sample.texture = texture
            EDIT.connect_material_property(
                sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
            )
            if name in ("GroundPirelli", "GroundMSC", "GroundAlgarve"):
                roughness = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
                roughness.r = 0.7
                EDIT.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
            if self.night:
                shade(material, self.bounds, self.field, self.road_floor, self.emissive_scale, self.slug == "jeddah")
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
            partition = self.manifest.get("city_partition")
            if partition is not None:
                current = {tile["name"] for tile in self.manifest["tiles"]}
                for name in partition["superseded_assets"]:
                    if name in current:
                        raise RuntimeError(f"Partition parent is still active: {name}")
                    path = self.assets + "/Track/" + name
                    if not LIBRARY.does_asset_exist(path):
                        continue
                    references = LIBRARY.find_package_referencers_for_asset(path, True)
                    if references:
                        raise RuntimeError(f"Partition parent still has asset references: {path}: {references}")
                    if not LIBRARY.delete_asset(path):
                        raise RuntimeError(f"Cannot remove replaced partition parent: {path}")
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
