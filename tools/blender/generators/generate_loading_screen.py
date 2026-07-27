"""Rerender the original five-car Formula Forge loading artwork."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy


LEGACY_VEHICLES = (
    "formula_fiery",
    "formula_marc",
    "formula_macl",
    "formula_rb",
    "formula_dash",
)


def render_legacy_scene(output_dir: Path) -> None:
    """Render the preserved scene whose five cars predate the team reskins."""
    blend_path = output_dir / "formula_forge_loading.blend"
    png_path = output_dir / "formula_forge_loading.png"
    if not blend_path.is_file():
        raise FileNotFoundError(f"missing preserved loading scene: {blend_path}")

    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    scene = bpy.context.scene
    scene.render.filepath = str(png_path)
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.frame_set(1)
    bpy.ops.render.render(write_still=True)

    manifest = {
        "schema_version": 1,
        "asset": "formula_forge_loading",
        "type": "ui_artwork",
        "resolution": [1280, 720],
        "composition": "five original Formula liveries in a red-lit semicircle",
        "lighting": "dark studio with red arena and rim lights",
        "vehicles": list(LEGACY_VEHICLES),
        "source": blend_path.name,
        "render": png_path.name,
    }
    (output_dir / "formula_forge_loading.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    output_dir = (args.output_dir.resolve() if args.output_dir else
                  project_root / "assets" / "ui" / "formula_forge_loading")
    render_legacy_scene(output_dir)


if __name__ == "__main__":
    main()
