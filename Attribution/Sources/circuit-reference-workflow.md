# Circuit references and landscape data

The 18 additional venues use the user's videos in `Saved/Refs`. Each venue's
`reference-index.json` identifies the clip, frame timestamps, layout era and
limitations. `environment-recipe.json` records observations around the complete
route. These are reconstruction notes, not approval of the rendered circuit.
The videos are not distributed, and no video pixels or commercial meshes are
included in the game.

`scenery-terrain.json` records a retained, bounded Copernicus elevation window
and its source URL and checksum. GLO-30 is a surface model at approximately 30 m;
Baku uses public GLO-90 because its GLO-30 tile was unavailable. Resampling these
windows at 12 m does not improve their source resolution. Terrain is for the
surroundings; road elevations remain independently sourced. Suzuka retains its
existing GSI terrain. Building and vegetation heights in a surface model must
not become racing-deck elevations through tunnels or under bridges.

Copernicus DEM attribution: Copernicus Digital Elevation Model, accessed
2026-11-08 from [AWS Open Data](https://registry.opendata.aws/copernicus-dem/).
The [dataset documentation](https://copernicus-dem-90m.s3.amazonaws.com/readme.html)
links the Copernicus DEM licence and required notices. Retained windows are
processed subsets of the original DSM. Local heights use a median offset to the
native road profile; the transformation is recorded per venue.

OpenStreetMap extracts retain their per-venue query, retrieval and checksum
records. © OpenStreetMap contributors, ODbL 1.0. Named architectural models use
mapped footprints where available; heights, roof details and placements inferred
from pictures remain estimates and are identified in the recipes.

Official circuit/FIA documents and published elevation diagrams supply geometry
facts and dimensional checks. Any digitised elevation controls are original
numeric reconstructions with recorded station registration and uncertainty.
Reference diagrams and photographs remain research inputs and are not shipped
as artwork.

The accepted Silverstone, Monza, Interlagos and Las Vegas assets remain separate.
New scenes copy their licensed material recipes into private venue folders.
A successful mesh import or native geometry check does not establish visual
fidelity: packaged whole-route driving, reference comparison and independent
review remain required.
