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
preview PNG, and JSON integration metadata. Worlds use readable medium-gray
tarmac, continuous track-limit lines, bank-following curbs, profiled grass,
gravel and asphalt runoff, concrete/Tecpro safety barriers, and catch fencing.
Grounded combined meshes provide grandstands and spectators, pit facilities,
marshal posts and vegetation while keeping the runtime draw-call count bounded.

`verify_tracks.py` treats those presentation details as runtime contracts. It
checks opaque material parity between BLEND and GLB, asphalt luminance,
continuous barrier/fence/track-limit topology, local shoulder grounding for
every scenery placement, and the exact catalog alignment used by physics.

## Runtime alignment contract

Track geometry is authored so the exported glTF/raylib basis aligns directly
with the C++ `toWorld` basis. Blender `(X, Y, Z)` exports as glTF
`(X, Z, -Y)`; the generator therefore authors Blender Y as the negative of the
C++ plan Y. Because mapping a Cartesian XY plan into raylib's Y-up XZ ground
plane reverses driver-visible turn handedness, the runtime and asset generator
apply the same per-source Y reflection before this basis conversion. This keeps
real-world left and right turns correct without changing lap order. Load at
origin with zero yaw. Use the per-asset
`runtime_alignment.recommended_glb_uniform_scale` from metadata (`1.445` for
all meter-based circuits). The GLB centerline datum then maps to C++ world
coordinates exactly; the visible asphalt is 0.06 meters above that datum. Spa
reproduces its procedural 14-16 meter phase-based width.
Opaque world base layers are strictly separated rather than coplanar. The local
embankment follows each centerline's elevation, carries crossfall through the
first four metres of runoff, then eases back to the local centerline height by
36 metres. This same height function grounds runoff, barriers, scenery, and the
runtime vehicle contact plane.
The kilometer-scale base layers do not overlap: infield is an inner triangle
fan, with successively darker grass/ground rings beyond it. Rings use explicit
shared-edge triangles. Do not convert
these layers back to overlapping n-gons; their depth precision is insufficient
at the full metric-circuit scale.

Metadata records the start pose in both Blender and glTF/raylib axes, Blender
and glTF bounds, stable node/material role names, source-array hashes, spline
settings, and the C++ `TrackLayoutId`. The asset origin remains the catalog
plan origin rather than the start line. Every circuit currently starts at
phase zero.
