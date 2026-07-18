# Track asset authoring

The generator reads the authoritative centerline/elevation/width arrays from
`src/track_layout.hpp` and `src/track_catalog.cpp`, then authors a Blender world
in meters for each playable layout. Generated artifacts live under
`assets_src/tracks/<slug>/`.

```sh
uv sync
uv run python tools/blender/tracks/generate_tracks.py --track all
uv run python tools/blender/tracks/verify_tracks.py --track all
```

Each output directory contains the editable `.blend`, runtime `.glb`, rendered
preview PNG, and JSON integration metadata. The GLB uses combined palm, house,
and rock meshes to keep the runtime draw-call count bounded.

## Runtime alignment contract

Track geometry is authored so the exported glTF/raylib basis aligns directly
with the C++ `toWorld` basis. Blender `(X, Y, Z)` exports as glTF
`(X, Z, -Y)`; the generator therefore authors Blender Y as the negative of the
C++ plan Y. Load at origin with zero yaw. Use the per-asset
`runtime_alignment.recommended_glb_uniform_scale` from metadata (`1.445` for
meter-based catalog circuits and `0.085` for Sunset Cove's native course
units). The GLB centerline datum then maps to C++ world coordinates exactly;
the visible asphalt is 0.06 meters above that datum on catalog tracks and 0.20
native units above it on Sunset Cove to prevent z-fighting. Sunset elevation,
ramps, and its 152.0-172.8-unit visible road width reproduce the procedural
runtime formulas rather than pretending its source coordinates are meters.
Spa similarly reproduces its procedural 14-16 meter phase-based width.
Opaque world layers are strictly separated rather than coplanar: ocean, sand,
vegetation, embankment, runoff, and asphalt rise in that order. The exact
numeric levels are recorded in `runtime_alignment.opaque_layer_elevations_asset_units`.
The three kilometer-scale base layers use explicit shared-center triangle fans;
they must not be converted back to n-gons because driver triangulation can
produce visible precision seams at runtime.

Metadata records the start pose in both Blender and glTF/raylib axes, Blender
and glTF bounds, stable node/material role names, source-array hashes, spline
settings, and the C++ `TrackLayoutId`. The asset origin remains the catalog
plan origin rather than the start line. Sunset Cove's start gantry uses its
runtime phase of `0.795`; every other circuit currently starts at phase zero.
