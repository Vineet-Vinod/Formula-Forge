# Formula Forge Asset Pipeline

The source-of-truth asset flow is:

`manifest + Blender Python -> .blend -> validated .glb -> raylib`

## Setup

The Python minor and `bpy` version are deliberately pinned because Blender's
PyPI wheels target one Python ABI at a time.

```sh
uv sync --frozen
```

## Commands

```sh
uv run --no-sync python tools/build_assets.py list
uv run --no-sync python tools/build_assets.py build smoke_kart
uv run --no-sync python tools/build_assets.py validate smoke_kart
uv run --no-sync python tools/build_assets.py preview smoke_kart
uv run --no-sync python tools/build_assets.py build all
```

Each generator is registered in `formula_assets/generators.py`. Each JSON
manifest owns its output locations, required node/material/animation names, and
acceptable dimensions in meters. A build fails before export when that contract
is violated. It then parses the exported GLB and verifies that required data and
the binary geometry buffer survived export.

Blender source uses meters, +Z up, and +Y forward. glTF export performs the
standard +Y-up conversion. Generated metadata records measured bounds, counts,
coordinate conventions, and hashes for integration/debugging.

`validate` opens the saved source, rechecks the scene and GLB contracts, verifies
the source/runtime hashes in metadata, and confirms that the preview is a PNG.

Preview lights, camera, and ground live in `FB_PREVIEW`. Runtime geometry lives
in `FB_RUNTIME`, and only the latter is exported. The preview renderer uses
Eevee and works without an interactive Blender installation through the `bpy`
wheel.

## C++ integration

Create the raylib window/OpenGL context before calling `GlbAsset::load()`. The
loader owns the raylib `Model` and animation array, supports named 60 Hz clip
sampling, and draws with an explicit meters-to-world scale. Its runtime bounds
use glTF/raylib axes: X width, Y height, Z length. Manifest bounds are measured
in Blender authoring axes: X width, Y length, Z height.
