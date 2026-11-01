# Retained asset source notices

These asset notices are retained from the previous project. Historical authoring
paths and GLB release descriptions refer to that version in Git history; the
current game distributes the derived native Unreal assets in Content/Generated.
Current source manifests are under Sources/. Notices for removed libraries and
fonts that are no longer packaged have been omitted.

## OpenStreetMap circuit geometry

- Source and attribution: <https://www.openstreetmap.org/copyright>
- Copyright: © OpenStreetMap contributors.
- License: Open Data Commons Open Database License 1.0 (ODbL).
- Use: meter-projected centerline control points for the additional real-world
  circuits under `src/track_data/`.
- Local modification: selected raceway ways are stitched in mapped one-way
  order, centered, uniformly resampled to remove node-density artifacts, and normalized at
  runtime to the authoritative FIA lap length.

FIA and circuit publications are used only to validate factual length,
direction, elevation, and layout characteristics; their artwork is not
redistributed.

## Monza reconstruction geographic data

The data snapshot and derived survey under `tools/blender/tracks/sources/monza/`
contain OpenStreetMap data, copyright OpenStreetMap contributors, licensed under
the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OpenStreetMap attribution](https://www.openstreetmap.org/copyright) and the
[reconstruction source manifest](Sources/monza/SOURCES.md)
for the snapshot, provenance and produced-work attribution. The Blender
reconstruction retains the attribution in the source manifest and in a text block.

## Non-Monza circuit reconstruction data and assets

Bahrain, Buddh, COTA, Hockenheim, Interlagos, Istanbul, Sepang, Shanghai,
Silverstone, Spa and Suzuka use © OpenStreetMap contributors data under
[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), licensed aerials by
Planet Labs, Adbar, Swapnil1101, CK Tan, SPW and GSI, and public elevation data.
Full per-image credits, licenses, modifications, source hashes and elevation
attributions are in the [source manifest](Sources/README.md)
and each circuit's `provenance.json`.

The photo-derived authored layouts and reconstructed visual assets are CC BY-SA
4.0, retaining those credits; original source images and ODbL databases retain
their own licenses. Game code is not relicensed. No aerial texture is embedded
in the runtime assets; their aggregate texture is original procedural artwork.

Modified elevation-data attribution: produced using Copernicus WorldDEM-30
© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under
COPERNICUS by the European Union and ESA; all rights reserved.

Spa orthophoto credit: Service public de Wallonie (SPW) – Orthophotos 2024
(2026-01-15). Suzuka uses processed Geospatial Information Authority of Japan
photo/elevation tiles; the authored modifications are not a GSI product.

Regional lidar credits: © Environment Agency copyright and/or database right
2022. All rights reserved (OGL v3.0); Datenquelle: LGL, www.lgl-bw.de,
dl-de/by-2-0, LGL-BW (2026); Prefeitura Municipal de São Paulo (PMSP), GeoSampa
M3DC 2017 (CC BY-SA 4.0 under the owner's 2025 GeoSampa notice).
Source crops, modifications and licence links are in the source manifest above.

Monza's original project-authored tree library is reused without modifying its
source asset. The derived runtime foliage atlas and reproduction instructions
are in `tools/blender/tracks/sources/shared/monza_foliage/README.md`.
Building models use factual observations from operator, architect and contractor
publications listed in each circuit's `architecture.json`; their photographs
and drawings are not included in the distributed assets.

## Silverstone runtime artwork and source data

The Silverstone runtime release contains `silverstone.glb`, `silverstone.json`,
and `assets/environments/silverstone/daylight.png`. The [release manifest](Sources/silverstone/release_manifest.json)
lists every embedded GLB image and its source category. The track's mapped
plan uses © OpenStreetMap contributors data under ODbL 1.0. The retained
Environment Agency 2019 LiDAR point cloud and 2022 bare-earth DTM are under
the Open Government Licence, with attribution © Environment Agency copyright
and/or database right 2022. All rights reserved. Their survey dates, area,
hashes, and limits are in `tools/blender/tracks/sources/silverstone/sources.yaml`.

The road, grass, and concrete textures in the GLB derive from these [Poly Haven
CC0 assets](https://polyhaven.com/license): [Asphalt Track](https://polyhaven.com/a/asphalt_track)
by Dimitrios Savva, [Concrete Wall 009](https://polyhaven.com/a/concrete_wall_009)
by Charlotte Baglioni, and [Leafy Grass](https://polyhaven.com/a/leafy_grass)
by Charlotte Baglioni. Their original files are documented in
`tools/blender/tracks/sources/spa/materials/manifest.json`; the Silverstone
derivatives and hashes are in
`tools/blender/tracks/sources/silverstone/materials/manifest.json`. Silverstone's
daylight panorama is a color-adjusted derivative of the [Kloofendal 38d Partly
Cloudy Pure Sky](https://polyhaven.com/a/kloofendal_38d_partly_cloudy_puresky)
CC0 image by Greg Zaal and Jarod Guest. Its source and derivative hashes are in
the Spa and Silverstone sky manifests. The GLB's diamond fence image and grain
image are generated by this project; its foliage atlas comes from the project's
shared Monza tree library.

The SkySat aerial in `tools/blender/tracks/sources/silverstone/references/`
is a dated research reference by Planet Labs, Inc. under CC BY-SA 4.0. It is
not a runtime texture. FIA maps, F1 broadcasts, commercial game imagery,
operator photographs, and Google imagery are reference-only and are not
included in the runtime release. The repo's research files and editable Blender
scene are separate from the three runtime files above.

The new Silverstone visual rebuild uses the 1K leaf diffuse and alpha maps,
plus a compact leaf-position derivative of the full mesh, from
[Tree Small 02](https://polyhaven.com/a/tree_small_02) by Rico
Cilliers, [CC0](https://polyhaven.com/license). Original URLs and hashes are in
`tools/blender/tracks/sources/silverstone/vegetation/README.md`. The new tree
placements use OSM woodland polygons; they do not reuse the Monza tree mesh.
The rebuild's ground materials also use [Grass Ground](https://polyhaven.com/a/grass_ground)
and [Sandy Gravel](https://polyhaven.com/a/sandy_gravel) by Charlotte Baglioni,
both [CC0](https://polyhaven.com/license). The retained 1K PNG URLs, hashes,
and 2.5 m and 2.1 m physical tile widths are recorded in
`tools/blender/tracks/sources/silverstone/rebuild_materials/manifest.json`.
The selected short green lawn material is [Grass 005](https://ambientcg.com/view?id=Grass005)
by ambientCG under [CC0 1.0](https://docs.ambientcg.com/license/). The 1K PNG
color, OpenGL normal, and roughness maps are retained with source archive and
file hashes in the rebuild materials manifest. Its two-metre scene tile is an
artist scale estimate based on the visible blade size.

The rebuild's 32 m grass texture combines the accepted Grass005 dry derivative
with original procedural clumps and dry patches. Input and output hashes,
CC0 source attribution, and estimated physical scales are recorded in
`tools/blender/tracks/sources/silverstone/surface_grass/manifest.json`.
Reference photographs and onboard frames contributed no texture pixels.

Four distant crown views are generated from Rico Cilliers' CC0 Tree Small 02
mesh. Source URLs, hashes and bake settings are recorded in
`tools/blender/tracks/sources/silverstone/vegetation/derived_canopy_manifest.json`.
The full source mesh remains in the ignored build cache, outside runtime packaging.

National Pits and Brooklands use Charlotte Baglioni's
[Concrete Wall 009](https://polyhaven.com/a/concrete_wall_009),
[CC0](https://polyhaven.com/license), and a tinted derivative. Their other
blockwork, shutters and cladding maps are original project artwork.
`tools/blender/tracks/sources/silverstone/architecture_materials/manifest.json`
records retained concrete inputs, output hashes and estimated surface scales.
The National glazing reflection is an original render of the licensed combined
scene and sky, with radiance encoding and source hashes in its probe JSON.
No commercial game, broadcast or reference-photograph pixels enter these maps.

The Silverstone event panel word atlas uses rasterized DejaVu Sans Bold glyphs.
The font is not packaged with the game. DejaVu derives from Bitstream Vera,
copyright (c) 2003 Bitstream, Inc.; the DejaVu changes are public domain.
The Bitstream Vera license permits reproduction and distribution with its
copyright and trademark notices. The atlas is original project typesetting,
not a copied sponsor logo or a broadcast image. The font source, installed
license record, atlas hash and source-view evidence are in
`tools/blender/tracks/sources/silverstone/event_graphics/manifest.json`.
The two event-screen stills are original no-HUD renders of this game. Their
camera positions and source hashes are in `docs/silverstone_event_screen_sources.json`.
