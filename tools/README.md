# Blender asset pipeline

Formula Forge keeps its editable Blender files and runtime exports in the same
asset tree:

`Blender Python -> .blend -> .glb/.png -> validation -> game`

The Python version and `bpy` wheel are pinned in `pyproject.toml` and
`uv.lock`. Set up the environment from the repository root:

```sh
uv sync --frozen
```

## Generate assets

```sh
uv run --no-sync python tools/blender/generators/generate_vehicles.py --asset all
uv run --no-sync python tools/blender/generators/generate_drivers.py --asset all
uv run --no-sync python tools/blender/generators/generate_loading_screen.py
uv run --no-sync python tools/blender/generators/generate_formula_garage.py
uv run --no-sync python tools/blender/tracks/generate_tracks.py --track all
```

`make assets` runs the same sequence. Generators write into `assets/vehicles`,
`assets/drivers`, `assets/ui`, and `assets/tracks`.

## Validate assets

```sh
uv run --no-sync python tools/blender/generators/verify_assets.py
uv run --no-sync python tools/blender/tracks/verify_tracks.py --track all
```

`make assets-validate` runs both validators. They check scene structure,
dimensions, required materials and animations, preview/export consistency,
mesh budgets, track length and width, landmark order, clearance, and runtime
metadata.

Blender authoring uses meters with X as width, Y as length, and Z as height.
glTF export converts to its Y-up convention; raylib runtime bounds therefore
use X as width, Y as height, and Z as length.

Create the raylib window/OpenGL context before calling `GlbAsset::load()`. The
loader owns its raylib model and animation array, samples named 60 Hz clips,
and enforces runtime dimension contracts independently of the Python checks.

Circuit-specific generation and alignment details are documented in
[tracks/README.md](blender/tracks/README.md).
