# Monza circuit reconstruction

Open **monza_reconstruction.blend** in Blender 5.0 or later. Coordinates are
metres, with X east, Y north and Z up. The origin is the mapped control line at
9.2811729 E, 45.6189632 N. The horizontal lap measures 5,793.000 m and the modeled
spatial centerline measures 5,793.010 m.

This is a geographically anchored environment reconstruction. It is not a laser
scan. Plan geometry and mapped footprints have stronger evidence than local
elevations, camber, building heights, individual trees and temporary circuit
furniture. See [reference provenance](references/SOURCES.md) and [QA notes](QA.md).
The working reference configuration combines the 2025 FIA plan with the 2026
official circuit length and corner count.

## Scene contents

`Survey_curves` contains separate editable centerline, left edge, right edge,
pit lane, service roads and historic oval curves. These are sampled POLY curves
at 0.75 m on the main lap. Every point remains editable; there are no hidden
Bezier handles changing the validated route between observations.

`Track` contains a continuous asphalt mesh with eight lateral divisions, a
35 mm crown, restrained estimated crossfall, edge paint, drainage, kerbs, green
aprons, repair patches and the pit lane. A road vertex attribute controls the
rubber deposition pattern. Materials use world-space metre coordinates.

The other collections separate `Safety_barriers`, `Fencing`, `Marshal_posts`,
`Signage`, `Grandstands`, `Pit_buildings`, `Bridges`, `Service_roads`, `Forest`,
`Distant_environment`, `Runoff` and `Historic_oval`.

Trees, fences, Armco, grass tufts, tyre stacks and light poles use shared mesh
assets through Geometry Nodes instancing. `Asset_library` stores the source
meshes, hidden from direct display. The point meshes retain per-instance scale
and rotation attributes. Tree placement follows mapped forest polygons, their
inner clearings and road/building exclusions. The separately named back-straight
tree belt is inferred from aerial imagery.

The named driver cameras are 1.2 m above the road. Each section has an elevated
camera as well. The `LAP | 1.2 m | animated survey inspection` camera covers a
complete closed lap over frames 1–1932. Timeline markers identify the ten
environment sections. This is an inspection animation, not a simulated racing
line or a lap-time prediction.

## Review artifacts

- `monza_overview.png`: complete circuit and historic oval.
- `monza_driver.png`: larger pit-straight render.
- `qa/sections/`: ten driver views and ten elevated views.
- `qa/driver_contact_sheet.jpg`, `qa/elevated_contact_sheet.jpg`: section comparisons.
- `qa/monza_lap.mp4`: low-resolution continuous inspection, all 1,932 frames.
- `qa/lap_sheets/`: consecutive-frame contact sheets for the lap review.
- `qa/final_validation.json`: measurements from the saved Blender scene.
- `qa/runoff_partition.json`: areas retained after clipping runoff overlaps.
- `survey.json`: geographic source data, projection and confidence metadata.
- `geometry_qa.json`: section lengths, headings, radii, widths and elevations.

## Rebuild

Run from the repository root. Normal builds use the checked-in OSM snapshot and
do not fetch changing map data. Synchronize the environment once before running
independent render jobs.

The pinned authoring dependencies are Blender's `bpy` and Shapely. Pillow is
needed only for contact sheets, and FFmpeg only for encoding the inspection video.

```sh
uv sync
uv run --no-sync python tools/blender/tracks/survey_monza.py
uv run --no-sync python tools/blender/tracks/build_monza.py --phase foundation
uv run --no-sync python tools/blender/tracks/build_monza.py --phase environment --section 0
```

Inspect the two section renders, then repeat the environment command for sections
1 through 9 in order. The generator rejects an out-of-order or duplicate section.
Rebuilding the foundation replaces the authored scene, so preserve manual edits
in a separate Blender file before rebuilding.

```sh
uv run --no-sync python tools/blender/tracks/build_monza.py --phase finalize
uv run --no-sync python tools/blender/tracks/verify_monza_reconstruction.py
uv run --no-sync python tools/blender/tracks/build_monza.py --phase review
uv run --no-sync python tools/blender/tracks/build_monza.py --phase lap
uv run --no-sync --with pillow python tools/blender/tracks/monza_review_media.py
uv run --no-sync --with pillow python tools/blender/tracks/monza_review_media.py --lap
ffmpeg -y -framerate 24 -i assets/tracks/monza/reconstruction/qa/lap/%04d.png -c:v libx264 -crf 19 -pix_fmt yuv420p assets/tracks/monza/reconstruction/qa/monza_lap.mp4
```

The raw lap PNGs are regeneration intermediates and are ignored by Git. Frame
ranges can be rendered independently with `--frame-start` and `--frame-end`.

## Game integration

The reconstruction is a standalone authoring asset. The existing `monza.blend`,
`monza.glb`, runtime track catalog, physics, handling and gear behavior remain
unchanged. The existing game layout uses a different coordinate contract.
Replacing its visible road with this scene requires a separate alignment decision.

Geographic data: copyright OpenStreetMap contributors, ODbL 1.0. Keep this
attribution with the scene. No external image textures or sponsor artwork are
bundled. The source manifest is also embedded as a Blender text block.
