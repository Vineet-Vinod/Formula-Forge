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
