# Silverstone leaf cards and crown layout

The two 1K PNGs are the original leaf diffuse and alpha maps from
[Poly Haven's Tree Small 02](https://polyhaven.com/a/tree_small_02), by Rico
Cilliers. Poly Haven publishes the asset under [CC0](https://polyhaven.com/license).
The rebuild uses the left half of this leaf atlas on new crossed leaf cards.
It does not reuse any earlier Monza or Silverstone scene tree.

Download locations:

- `tree_small_02_leaves_diff_1k.png` from
  `https://dl.polyhaven.org/file/ph-assets/Models/png/1k/tree_small_02/tree_small_02_leaves_diff_1k.png`,
  SHA-256 `d3fc48522c76aa1f91076c6b86f302669822ebe4e2acabd67d42c4d57eaa5ba0`
- `tree_small_02_leaves_alpha_1k.png` from
  `https://dl.polyhaven.org/file/ph-assets/Models/png/1k/tree_small_02/tree_small_02_leaves_alpha_1k.png`,
  SHA-256 `4f143e2dda8a6a572f427ac378b92255d21761e4611de0d26e21816c01aa533b`

Tree placements are generated inside selected raw OpenStreetMap `natural=wood`
ways. Heights, branch shapes, and canopy sizes are visual interpretations.

`tree_small_02_crown_lod.json` is a compact spatial derivative of the same
CC0 tree's full glTF leaf mesh. Its 102 points are centroids of occupied
0.5 m leaf-vertex voxels with at least 3,000 source vertices each. The
source binary is
`https://dl.polyhaven.org/file/ph-assets/Models/gltf/8k/tree_small_02/tree_small_02.bin`,
SHA-256 `8da6c3c389ad8748286d1b7488cd827f75ebdad9d8f59ef7dfb0916df5edc634`.
The derived layout guides new leaf-card positions and does not ship the
95 MB source mesh. Stowe crown top heights are constrained by 2019 EA LAZ;
lower summer foliage and heights of other mapped woods remain estimated.

`uv run --no-sync python tools/blender/tracks/prepare_silverstone_rebuild_leaf.py`
generates the three `tree_small_02_leaf_card_color_*.png` RGBA atlases used by
the glTF exporter. The script converts the CC0 diffuse from sRGB to linear
light, applies the modest per-tree tint listed in `derived_leaf_manifest.json`,
then encodes RGB back to sRGB and copies the separate 16-bit alpha into 8-bit
alpha without premultiplication. The material links this single image directly
to Principled Base Color and Alpha; the derived atlases remain CC0.

## Distant crown views

`prepare_silverstone_rebuild_canopy.py` generates four
`tree_small_02_canopy_000/090/180/270.png` crown views from five linked instances
of the full CC0 source tree. `derived_canopy_manifest.json` records the official
glTF and binary URLs, input hashes, instance transforms, physical crop bounds
and each generated image's SHA-256. The source binary still hashes to
`8da6c3c389ad8748286d1b7488cd827f75ebdad9d8f59ef7dfb0916df5edc634`.
The downloaded full mesh stays in the ignored build probe cache.

All views use one 770 × 441 pixel crop representing 7.27297 × 4.16543 m.
Actual alpha bounds occupy at most 6.66846 m width and span 1.20519–4.76612 m
above the source base. These occupied bounds determine runtime scale, so
transparent padding does not shrink the intended crown. The bake hides trunks
and branches and combines 35% emission albedo with 65% diffuse under uniform
white ambient light. It bakes no directional sun. Its background is transparent;
24 pixels of RGB dilation keep filtering from introducing black edge colors.
Alpha remains unchanged. These generated maps are CC0 derivatives.

The reusable vegetation module places two crossed planes with independent
reverse views, eight triangles per distant cluster. Nearby tree meshes keep
their existing representation. Crown shapes and summer density remain visual
estimates. No commercial game, broadcast or reference-photo pixels enter the
generated textures. Existing mapped center positions, DTM bases and height
estimates remain the placement inputs. The integration patch limits distant
widths at mapped woodland edges rather than enlarging the source footprint.

Run every bpy command under the shared lock, for example:

```sh
flock /tmp/formula_forge_silverstone_blender.lock .venv/bin/python tools/blender/tracks/prepare_silverstone_rebuild_canopy.py
flock /tmp/formula_forge_silverstone_blender.lock .venv/bin/python tools/blender/tracks/verify_silverstone_rebuild_canopy.py
```

The isolated proof checks transparent image borders, generated hashes, finite
unit normals and 16-bit GLB indices. Its before/after images use synthetic
placements and a Blender renderer. They do not establish full-game lighting,
mip filtering or real woodland fidelity.
