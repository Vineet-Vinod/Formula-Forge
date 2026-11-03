# Building and reviewing a Formula Forge track

Use this guide when adding a circuit or rebuilding one. Read [AGENTS.md](../AGENTS.md)
first. The deliverable is a track that looks right and drives smoothly in the
packaged Unreal game, with evidence for its dimensions and terrain. An overhead
render, successful import or passing unit test does not establish that quality.

The code paths and capture example were checked on 2026-11-03. Recheck the
loaders and commands when the implementation changes.

This guide records the lessons from Silverstone, Monza and Interlagos. It also
maps those lessons to the current Unreal-only repository. It is not a claim that
an automatic track generator already exists here.

## 1. Establish the assignment and baseline

Confirm the circuit variant, direction, reference year and requested scope. A
historic layout, current Grand Prix layout and commercial game's interpretation
may differ. Record those differences before combining their sources. Adding a
track is authorized when the user requests it; the current three-track scope in
AGENTS.md should not silently prevent that requested addition.

The acceptance history matters:

- Silverstone established the first acceptable level of detail and consistent
  driving POV. Monza was accepted after its main straight, POV, full-lap terrain
  and perceived width were corrected.
- Interlagos became the user's reference for graphics, terrain and playing
  smoothness. Its successful features should guide new work; do not copy its
  architecture, vegetation or elevation into another venue.
- The approved camera and vehicle are shared. Preserve handling, speed, shifting,
  physics and camera unless a change is explicitly requested. A map task is not
  permission to change those systems to conceal a geometry problem.
- Compare against fresh captures of the current accepted tracks on the same
  machine. [validation.json](validation.json) records historical checks, not a
  current performance guarantee. Its 30 fps capped flow test cannot demonstrate
  uncapped frame-rate parity.

Start with a clean-status inspection. Use a feature branch in this folder;
project instructions prohibit worktrees unless requested. Preserve existing user
changes and the separate engine installation. Keep downloads, clips, builds and
review output under ignored `build/`. Do not write personal filesystem paths into
committed instructions. Do not merge or push without an explicit request.

On Linux, keep total used memory below 11 GB and run one heavy operation at a
time. Use the guarded Make targets and their `tools/unreal.sh` implementation.
This applies to downloading/decompressing large surveys and authoring tools too:
a direct external command does not inherit the Unreal guard. Give those jobs
bounded memory, crop inputs and process tiles serially. Never bypass a failed
guard just to finish a render.

### Required evidence before calling a track complete

| Area | Evidence |
| --- | --- |
| Layout and dimensions | Registered plan, metric widths, landmark positions, lap length and direction checks |
| Elevation | Road profile, cross-sections, source classes/datums, bridge/deck treatment and seam checks |
| Protection | Both-side barrier coverage, matching collision, pit exit and runoff inspection |
| Graphics | Matched reference/runtime frames, including the actual cockpit camera |
| Driving | Full live laps, representative kerb/verge contact, uphill visibility and lap timing |
| Performance | Repeatable driving runs compared with an accepted track at equal settings |
| Integration | Selection, loading, unlimited/finite laps, pause, restart, results and return to menu |
| Reproducibility | Source/licence manifest, transformation records, authoring recipe and committed runtime assets |

## 2. Understand what is available now

The editable shipping assets are native `.uasset` and `.umap` files in
`Content/Generated`. Source records are under [Attribution](../Attribution/README.md).
Many of those records describe historical Blender/GLB authoring. The old `.blend`
files, downloaded reference videos, raw survey archives and generator scripts
were removed during cleanup. A manifest entry is not proof that its payload is
still on disk. Inventory what is present and reacquire missing permitted inputs.

Do not invoke historical targets such as `make monza-assets` or scripts under
`tools/blender/`; they are not current build instructions. Do not restore Blender
or raylib as dependencies. Preserve their useful reconstruction methods in a
native Unreal authoring workflow.

Current tools have specific limits:

- `make assets` runs `tools/prepare_project.py`, which builds the garage frontend.
  It does **not** generate a circuit.
- `FFMeshBuildLibrary` currently changes static-mesh shadow sections. It is not
  a road, terrain or mesh-generation library.
- The enabled Python/editor-scripting plugins can automate editor asset creation
  and placement. Python is an authoring tool, not a runtime requirement. See
  [Epic's editor Python documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python).
- Implement the missing per-track builder/importer as part of the map task. Use
  editor APIs supported by the installed engine, or a small editor-only C++ mesh
  builder exposed to the authoring script. Check local engine headers before
  assuming an API or plugin is available.
- Keep new recipes and small source metadata versioned. Scratch conversions go
  in `build/`; a necessary generation script must not live only there. Validate
  inputs, give units explicit names and make rebuilding repeatable.

A proposed new-track organization is below. `<slug>` is a placeholder, not an
existing tool or asset directory:

```text
Attribution/Sources/<slug>/       provenance, source URLs/hashes, licences, decisions
Content/Generated/<Track>/        native track assets and Review.umap
Content/Generated/<Track>/Data/   surface, limits and render manifest
Source/FormulaForge/Native/track_data/<slug>_*.inc
Source/FormulaForge/FF<Track>Geometry.cpp
tools/build_<slug>.py             new Unreal authoring entry point, if needed
build/references/<slug>/          raw inputs and reference frames
build/reviews/<slug>/             runtime captures, profiles, metrics and review notes
```

Silverstone predates the per-track subdirectories: its `Track`, `Data`, textures,
materials and environment are directly under `Content/Generated`. Do not move
those shared paths as a side effect of adding a circuit.

## 3. Build a source package before building scenery

Use multiple sources for different questions. No single map, video or point
cloud supplies the whole track.

| Question | Preferred evidence | Common mistake |
| --- | --- | --- |
| Circuit variant and turn order | Operator/FIA documents for the chosen event/year | Mixing historic and current layouts |
| Plan and footprint | Licensed orthophoto, mapped geometry, regional survey | Treating a schematic circuit map as a metric plan |
| Driving width and runoff | Georeferenced edges, operator dimensions, matched views | Confusing white-line width with total paved width |
| Road and terrain heights | Classified lidar, bare-earth DTM, engineering profile | Sampling roof, vegetation or underpass height as asphalt |
| Building volume | Licensed regional 3D data, footprints, roof/eave observations | Guessing every building from one frontal frame |
| Appearance and sight lines | Supplied onboard video, dated photographs, oblique views | Treating a commercial game's terrain as a survey |
| Materials | Reusable project assets, licensed texture sources | Copying reference-video pixels into textures |

Start with the retained examples:

- [Silverstone provenance](../Attribution/Sources/silverstone/provenance.json):
  Environment Agency bare-earth lidar, coordinate system, vertical datum,
  filtering choices and explicitly limited accuracy.
- [Monza source notes](../Attribution/Sources/monza/SOURCES.md) and
  [regional 3D manifest](../Attribution/Sources/monza/regional_3d/manifest.json):
  Regione Lombardia DBGT building volumes, roof elements, spot heights,
  acquisition fields and paginated source requests.
- [Interlagos provenance](../Attribution/Sources/interlagos/provenance.json) and
  [elevation notice](../Attribution/Sources/interlagos/elevation/source-license.md):
  PMSP GeoSampa classified ground data and the recorded licence discrepancy.
- [Shared source index](../Attribution/Sources/README.md): leads for other circuits,
  including regional elevation datasets and operator profiles. Verify availability,
  dates and terms again; historical notes are not fresh source verification.

For each source record its URL or service request, provider, download date,
**acquisition date**, area, CRS, vertical datum, units, resolution, licence,
attribution, checksum, intended use and uncertainty. Retain feature IDs and
source classifications through processing. When paginating a service, use stable
ordering and check for duplicates, missing IDs and transfer limits.

Separate source evidence from reconstruction decisions. An inferred roof height,
smoothed grade or estimated barrier offset needs its own justification and
confidence. Do not relabel estimates as measurements or storage precision as
accuracy. A centimetre-encoded grid is not necessarily accurate to a centimetre.

### Reference footage and Google views

Inventory the user's reference folder before asking for material. If the video
was removed, find permitted alternatives or request the missing reference. Never
claim to have reviewed a clip that is absent or inaccessible.

Create a frame index with timestamp, landmark, approximate lap station, direction,
camera type, visible road edges, structures, barrier side and observation. Include
starts, approaches, apexes, exits, crests, compressions and pit merges. Match by
landmarks and station rather than elapsed video time, since speeds differ.
Retain the full frame alongside any annotated crop.

Google Maps/Earth oblique and street views can help inspect scale, silhouettes,
roof lines, road furniture and terrain relationships when available. For this
project treat them as reference-only: do not extract their 3D tiles, bake their
imagery into assets or assume a right to redistribute screenshots. Follow
[Google's geographic-content terms and guidelines](https://about.google/brand-resource-center/products-and-services/geo-guidelines/)
for the specific use, and keep attribution where required. Viewing content is
not a blanket asset licence. Keep commercial game/broadcast imagery out of
shipping textures too.

OpenStreetMap and other reusable datasets have separate obligations; retain
required notices and derivative-data terms. See [OSM's attribution requirements](https://www.openstreetmap.org/copyright)
and the project's [asset licence records](../Attribution/ASSET_LICENSES.md).
An original model can use factual observations without copying branded graphics,
reference photographs or another game's meshes. Do not treat a code licence as
covering every asset.

## 4. Solve registration, dimensions and coordinates first

1. Select a metric projection suitable for the venue, a local horizontal origin
   and a documented relative height origin. Record both horizontal and vertical
   datums. Transform every source into that system once.
2. Register road controls, imagery, lidar and building footprints using several
   distributed landmarks. Report residual error and conflicting dates. A single
   aligned straight can hide a rotated or distorted remainder of the circuit.
3. Build an ordered, closed centreline in driving direction. Check crossings,
   chicanes, pit branches and start/finish station. Use arc-length sampling;
   uneven source-node density must not change the apparent curve.
4. Compare measured length with the published layout length. Investigate a large
   discrepancy instead of stretching it away. Distinguish plan length from 3D
   surface length. If a small uniform correction is justified, record it and
   apply it consistently to all registered horizontal features.
5. Define both road edges and width transitions. Inspect normals at tight turns
   so offset edges do not fold or self-intersect. Build kerbs and runoff from
   those edges, with explicit local exceptions where the real layout requires.

Monza's retained notes distinguish a measured 5,798.513 m plan from the normalized
5,793 m loop and record the correction. That is an example of documenting a
choice, not a universal normalization factor.

### Coordinate contract in the current implementation

These are different spaces. Use explicit conversions and verify a known point,
left/right edge, tangent and elevation in every export. Historic comments call
the source plane "Blender metres"; that is a coordinate convention, not a current
Blender dependency.

| Quantity | Current convention |
| --- | --- |
| Local source/drive-surface point | `(x, y, z)` in metres |
| Simulation position | `(17*x, -17*y)`; elevation `17*z` |
| Unreal world position | `(-100*y, -100*x, 100*z)` in centimetres |
| Simulation to Unreal | `(sim.y, -sim.x, sim.z) * 100/17` |
| Lap station, lap length, `FFTrackProjection.halfWidth` | Metres |
| `FFTrackProjection.position`, `.lane`, `.elevation` | Simulation units; divide by 17 for metres |
| `FFTrackProjection.grade`, `.bankSlope` | Dimensionless slopes |
| Catalogue width / bank | Full road width in metres / angle in degrees |
| Render manifest bounds | Unreal world centimetres |

The car's mesh coordinates and wheel mounts are already Unreal centimetres.
Do not multiply them by 17. Inspect `WorldPosition`, `ComponentPenetration`,
`FFSimulation::Sample` and `authoredGridElevationMeters` before generating data.
The plan sampler also uses `centerlineScale` and `mirrorCenterlineY`; preserve
that contract rather than applying an additional reflection or scale.

Check road width numerically and in the cockpit. A narrow-looking road may be a
wrong width, wrong camera, oversized building, wrong barrier setback or a
perspective mismatch. Measure before choosing which one to change.

## 5. Reconstruct road and terrain as related surfaces

### Use the right observations

Bare-earth data, a surface model and the racing deck are different things.
Classify source points before interpolation. Monza DBGT ground classes `01` and
`0101` were useful; roof and building-foot observations were not road heights.
Interlagos used class-2 ground points. Recheck the source schema at a new venue.

Keep the raw observations immutable. Remove duplicate XY samples deliberately,
record outlier rejection and bound extrapolation. Sparse or nearly collinear
points can make an unconstrained local plane create extreme heights. The
Interlagos reconstruction used containing triangles among nearby ground points
with bounded fallback interpolation; do not assume a dense-looking point file
covers every part of the road.

### Author a continuous road profile

Maintain a longitudinal road height `z(s)` and crossfall/bank profile. Preserve
supported broad climbs, dips, crests and braking compressions while filtering
sampling noise. Check height, grade and grade-change plots, including closure at
the start line. A closed height loop with a discontinuous tangent still makes a
bump. Check width and banking continuity at that seam too. Use cross-sections
through the road, shoulders and barriers to catch lateral
steps that a centreline plot misses.

Choose smoothing distances from source resolution and observed features. Record
any anchors and uncertainty. Do not apply one circuit's smoothing length to all
tracks or flatten real elevation merely to stop camera movement.

Monza needed a continuous road profile independent of its coarse park raster.
Its recorded reconstruction used a 40 m filter, a broader 60 m Serraglio treatment
and explicit straight/deck anchors. Those are historical reconstruction choices,
not survey facts or default parameters for the next circuit. The original false
humps near Rettifilo/Curva Grande, Serraglio and the Parabolica-to-straight seam
must not become a reusable terrain recipe.

### Handle decks, crossings and adjacent ground

Access tunnels under Monza's straight supplied low ground observations beneath
the racing deck. The road must follow the deck, while those observations remain
valid for the tunnel. Do not solve a multi-level crossing by averaging its heights.

The current `FFDriveSurface::Height` is an XY height query and selects the upper
surface where triangles overlap. A single ground grid also cannot represent two
roads at different heights over the same XY. A circuit with a drivable lower
branch, such as a figure-eight crossing, needs explicit surface/route selection
in simulation and matching tests. That is additional engineering; never hide
it by lifting the lower road or deleting the bridge.

Blend surrounding terrain into the road corridor without copying raster cell
steps onto the asphalt. Keep realistic runoff slopes and retaining walls. Project
onto road segments rather than selecting the nearest centreline vertex. At tight
adjacent sections, blend using the intended branch and region masks so one road
does not pull its neighbour's terrain into a ridge.

Cut or mask coarse terrain below the road/runoff where needed. Avoid coplanar
surfaces, raised ground covering the track, cracks and visible hanging edges.
Carry deck corrections through shoulders and barrier bases, not just along the
centreline. Keep interpolation diagonals consistent between rendered terrain and
the simulation grid.

Rebuild from canonical source coordinates. Applying the same terrain warp twice
must not raise buildings or deepen dips. Save transforms and revision hashes;
regenerate dependent road, runoff, barrier and collision data together.

### Stop and inspect when any of these appears

- A hump with no supporting road-profile evidence.
- Alternating light/dark terrain bands caused by geometry or normals.
- A slope break at a tile boundary or the lap seam.
- A barrier whose lower edge floats above the verge or disappears underground.
- Different heights for the rendered road and the simulation contact surface.
- A crest that disappears only after changing vehicle/camera settings.

## 6. Build one representative section to the target quality

Start with the main straight, pit frontage and first braking zone. Include enough
of an adjacent slope or turn to exercise the terrain. This is the early quality
sample, not the whole deliverable.

Build dimensions before decoration: road edges, pit wall, runoff, building
footprints, roof heights, grandstand depth and setbacks. Use regional 3D geometry
where licensed and relevant, then correct the visible architectural features
using dated evidence. Monza's early reconstruction mistook a press room for a
full-height tower; additional survey and oblique views corrected the interpretation.

Review this section in the normal packaged driving view. Capture the same
landmarks and travel direction as the reference. Fix large shape, scale and
perspective errors before adding facade detail, crowds or event graphics.

The shared cockpit camera currently has a 90-degree FOV, local position
`(-52, 0, 126)` cm and a base downward pitch of 3.5 degrees. Chase view has its
own 80-degree FOV. Read `AFormulaTrialPawn::UpdateVisual` for the complete slope
and damping behavior; these numbers alone are not a camera implementation.
Do not make a track-specific FOV or widen the car to make the road look correct.

Uphill visibility is an acceptance check. The cockpit eye must remain attached
to the car as it climbs while pitch/roll smoothing handles road motion. World-Z
lag previously let the camera enter the body on Interlagos's Ferradura approach
and the climb after Juncao. Test crests and compressions at speed, not only a
stationary pose on flat ground. Inspect near-plane clipping and helmet/halo
occlusion as well as the horizon.

Send the representative section for user feedback when requested, and use the
reviewer protocol below between iterations. Continue independent research while
waiting. Do not require approval for every reversible modeling choice. When user
sign-off is explicitly required, treat reviewer acceptance as provisional and
wait before expanding work that depends on that approval.

## 7. Extend around the entire circuit

Divide the lap into named sectors and retain a coverage checklist. Each sector
needs plan, width, road profile, cross-sections, both barrier sides, runoff,
vegetation, scenery and driving captures. Give the less photogenic sections the
same geometry and protection review as the straight.

### Barriers, runoff and pit routes

Generate the visible protection and custom collision segments from one surveyed
path and one elevation revision. Keep posts upright; interpolate rail/fence
endpoints along slopes. Document the intended base, top, thickness, joins and
openings. A low-detail collision proxy still has to agree with the visible wall.

Unreal collision on the streamed decorative mesh is disabled in the current
presentation code. Vehicle contact is handled by `FFSimulation` and its authored
barriers. Adding a visible wall alone will not stop the car; adding collision alone
creates an invisible wall. Test both slow contact and high-speed swept contact,
including segment joins, changes in height and inside corners.

Audit left and right protection continuously, especially pit entry/exit, merges,
runoff boundaries, track crossings and climbs. Interlagos required explicit fixes
for missing pit-exit barriers, uneven Reta Oposta protection and the unprotected
inside of the run from Juncao. A barrier count cannot prove that coverage is right.
Use an overhead coverage overlay plus cockpit inspections and targeted sweeps.

Preserve justified real openings and any existing user-approved closures.
Document intentional fictional closures separately from the real-world layout.
Do not create a new pit-lane speed rule or open a previously closed route without
an explicit gameplay requirement. New pit support also needs loader/progress tests;
the current extra pit datasets are loaded only for Silverstone.

Runoff must join the track without lips or pits. Place trees behind the intended
protection and outside escape routes; inspect the full canopy footprint as well
as the trunk. The trees at Interlagos T5 exit were an example of attractive scenery
placed where an exiting car needed a protected runoff area.

### Infield layout

Model the infield as part of the venue, using registered access roads, service
areas, parking, drainage features, embankments, buildings and vegetation regions.
Do not fill every unused polygon with flat grass or scatter trees wherever the
road mesh ends. The Interlagos infield needed its own layout and elevation review,
including the relationships between nearby sections at different heights.
Check overhead geometry, then check what is visible from each driving sector;
landmarks and distant banks affect perceived scale even when they are off track.
Record uncertainty in service layouts or seasonal vegetation rather than claiming
that every aerial detail is current.

### Materials, vegetation and buildings

Use the accepted project's licensed surface sources and native materials when
appropriate, then match the new venue's colour, wear, scale and weather reference.
Record physical tile size. Resolve diffuse/normal/roughness channels, sRGB flags,
normal orientation, UV seams and alpha filtering in Unreal, not just the importer.
A tiny repeating asphalt texture can make a correctly sized road look miniature.

Keep exposure and rendering settings comparable to the accepted maps. Use lighting
to express the scene; do not use saturation, bloom or ambient light to conceal
missing geometry. Compare asphalt, kerb, grass, gravel, glazing, distant foliage
and sky together under the actual game settings.

Use detailed geometry where it affects cockpit silhouettes and near-field depth.
Distant trees/crowds can use reviewed cards or simpler meshes with stable LODs.
The [Silverstone vegetation notes](../Attribution/Sources/silverstone/vegetation/README.md)
record occupied alpha bounds, physical crown size, edge-colour dilation and
multiple crown views. Those lessons still apply when producing native assets;
the historical Blender commands in that file do not.

Avoid dense transparent layers, repeated identical tree outlines and crowds that
float or cover railings. Place crowds on real seating/deck surfaces. Build original
event artwork; do not paste sponsor strips or screens from the reference video.

## 8. Implement the Unreal assets and runtime data together

Derive both visible surfaces and driving data from the same final revision. Keep
export transforms in one place and validate small known geometry before exporting
a whole circuit. Preserve UVs, vertex colours, normals, material assignments and
LODs when importing or generating meshes. Check Unreal's cooked result.

### File contracts to inspect

The loaders are the authoritative specification. These summaries describe the
current files on the supported little-endian desktop platforms; implement explicit
float32/uint32 encoding and exact byte counts, not padded host-language structs.

| File/data | Current contract and reader |
| --- | --- |
| `drive_surface.bin` | `FFSURF1\0`, uint32 count, then 36 bytes per XYZ triangle; source metres. `FFDriveSurface::Load` validates counts, finite values and triangles. |
| Silverstone surface parts | `.bin.0`, `.bin.1`, `.bin.2` concatenate into one complete stream before parsing. Parts are byte slices, not independently headed files. |
| `track_limits.bin` | `FFTL`, uint32 count, six float32 values per XY triangle in simulation-oriented metres. See `FFTrackLimits::Load`; this Y convention differs from drive-surface source XY. |
| `render_tiles.csv` | No header; mesh name and six Unreal-centimetre bounds: min XYZ, max XYZ. Names must start with `Tile_` or `Building_`; crowd behavior recognizes `Building_Crowd_`. |
| `*_survey.inc` | Centreline, elevation, full width and banking controls consumed by the catalogue. Preserve their units and sampling convention. |
| `*_ground.inc` | `AuthoredGroundGrid`: source XY in metres, int16 heights in centimetres relative to the chosen datum; matching cell diagonals. Check range before quantizing. |
| `*_boundaries.inc` | Native barrier/runoff geometry, using the conventions in `authored_track_collision.hpp` and the selected circuit geometry wrapper. |
| `pit_lane.bin`, if supported | `FFPIT1\0\0`, count, entry/exit distances, then nine float32 values per section. Inspect `FFPitLane::Load` and `FFPitSection` for field order and validation. |
| `pit_barriers.bin`, if supported | `FFBAR1\0\0`, count, seven float32 values per segment in simulation units. `LoadPitBarriers` currently appends Silverstone-specific Chapel barriers; generalize deliberately before reuse. |

`FFDriveSurface` supports up to four million triangles and uses an XY spatial
index. It is not Unreal's mesh collision. Do not feed roofs or scenery into a
surface query just because they are triangles in the same visible tile.

The current render components are placed at world zero: tile vertices already
carry the required placement. If generating local-origin meshes instead, add a
consistent transform contract to the loader and bounds. Do not offset both the
vertices and component, or emit local bounds for world-positioned geometry.

Separate road/contact geometry from decorative LOD reductions. A lower LOD must
not alter the collision profile, erase a kerb or create holes in terrain. Avoid
regenerating shared car/driver/environment assets during a track-only iteration.

### Add support through the entire game

Search the current code for circuit names, fixed counts and default branches.
A new enum entry alone is insufficient. Some existing fallbacks treat every
unknown non-Monza circuit as Interlagos or every other circuit as Silverstone.

| Location | Integration work |
| --- | --- |
| `Native/track_types.hpp`, `Native/track_catalog.cpp` | Unique ID, catalogue entry, direction, start phase, length, profiles and shape expectations |
| `FFCircuitGeometry.hpp`, new `FF<Track>Geometry.cpp` | Explicit geometry bundle and generated includes |
| `FFSimulation.cpp` | Select the correct geometry; review per-circuit assumptions without retuning shared vehicle physics |
| `FFGame.cpp` | Explicit slug-to-layout/data-directory mapping, required data files and chunk-loading rules |
| `FFPresentation.cpp` | Track visual root, environment selection and appropriate streaming/detail treatment |
| `FFSession.cpp` | Slug/title/map mapping, command-line selection, action counts and navigation |
| `FFFrontend.cpp` | Track selector layout, action IDs and matching catalogue order |
| `Config/DefaultGame.ini` | Map cooking, always-cooked soft-loaded assets and staged raw Data files |
| `Makefile`, `Tests/`, `FFSessionAudit.cpp` | Compile the new native geometry in checks and actually exercise the new circuit |
| `README.md`, attribution records | Supported-track list, new source records and relevant instructions |

Prefer one small shared track description over adding more scattered three-way
ternaries. Keep such a refactor focused on what the new track needs. The current
frontend uses three fixed buttons with lap/start/quit actions following them;
adding a fourth button without updating action IDs and layout breaks input.
The flow audit also has circuit-specific stages and a three-circuit sequence.
Update it deliberately; an old test passing is not evidence for a new map.

`FFSimulation::GripScale` also contains track-specific corner targets. Do not
accidentally apply Silverstone's targets to a new layout or retune them to hide
wrong geometry. Identify this coupling during planning and resolve any required
handling-policy change with the user; keep it distinct from surveyed map data.

Keep the native frontend as the startup map. Use Unreal level travel for driving.
Include the new map's soft-loaded track meshes, dependencies and UFS data in the
package. A file that happens to exist in an editor workspace may be missing from
a cooked package. A level named `Review` can still be the playable circuit level;
its game mode determines whether it is a driving or free-camera session.

## 9. Run a repeatable build, capture and review loop

Use the engine version supported by [README.md](../README.md) and set `UE_ROOT`
to the installed engine directory containing `Engine`. The commands below run
from the repository root. Replace placeholder paths with local values.

```sh
export UE_ROOT="/absolute/path/to/UnrealEngine"
make build
```

For a newly implemented authoring script, run it through the existing guard:

```sh
# Requires implementing this script first; it is not supplied by this guide.
bash tools/unreal.sh python "tools/build_<slug>.py"
```

Replace `<slug>` before executing; shell angle brackets are not literal arguments.
Prefer adding a concrete per-track Make target for the authoring command once the
script exists. Do not confuse it with the frontend-only `make assets` target.

After changing source/data, and after regenerating native assets:

```sh
make check
make package
make session-check
make flow-check
```

Run serially. `make check` covers native circuit/camera/surface checks; extend its
coverage for the new track. `make session-check` checks lap-limit session behavior.
`make flow-check` uses injected input and offscreen rendering capped at 30 fps;
it does not replace physical-controller checks, uncapped performance measurements
or a human/reference visual review. Run `make script-check` when build helpers
change. Do not repeatedly rebuild unchanged assets just to produce more checks.

### Capture the actual driving view

The following example uses an existing Monza level. It selects the circuit and
opens the driving game mode explicitly. `-FFCircuit` alone only selects the menu
entry; it does not start driving. For a new circuit, register it first, then change
the slug, level path, station and output folder together.

```sh
mkdir -p build/reviews/monza
make run ARGS="-windowed -RenderOffscreen -ForceRes -ResX=1600 -ResY=900 -FFCircuit=monza -FFStation=0 -FFCapture=\"$PWD/build/reviews/monza/start.png\" -FFCaptureDelay=15 -FFQuitAfterCapture '-ExecCmds=open /Game/Generated/Monza/Review?game=/Script/FormulaForge.FormulaTrialGameMode'"
```

`FFStation` is lap station in metres; `FFLane` is lateral offset in metres.
Use absolute output paths built from `$PWD` and quote them because repository
paths can contain spaces. Allow textures and tiles to settle before capture;
increase the delay if the image/log shows loading. The driving capture path does
not itself prove all streaming is complete. Inspect the image and its JSON sidecar.

Useful existing facilities, with their limitations:

| Facility | Use and limitation |
| --- | --- |
| `-FFChase` | Car/ground support inspection; keep cockpit view as the primary acceptance view |
| `-FFDrive` | Slow diagnostic driving, roughly 70 km/h; not a racing-speed test or tuned AI racer |
| `-FFCapture`, `-FFCaptureDelay`, `-FFQuitAfterCapture` | Screenshot plus pose/support metadata; its average FPS is not a frame-time distribution |
| `-FFRecord`, `-FFRecordSeconds=60`, F9 | Bounded runtime recordings and input/tick/step journals in `build/unreal/recordings`; do not combine with single-shot capture/audit |
| `-FFReplay`, `-FFReplayRealtime` | Compare visual presentation along compatible recorded poses; bypasses live driving physics and requires the loader's CSV format under the recordings directory |
| `/Script/FormulaForge.FFCircuitReviewGameMode` | Diagnostic free camera with `FFViewX/Y/Z`, `FFViewPitch/Yaw/FOV`; world centimetres and degrees, not lap coordinates |
| `-FFAudit` | Existing support/streaming diagnostics; contains Silverstone assumptions, so inspect/extend before claiming new-track coverage |
| `-FFRacingLine`, racing audits, National pit diagnostics | Existing Silverstone-specific facilities; do not assume they work on another circuit |

The recorder's journals are not automatically a compatible replay CSV. Inspect
`FFVisualReplay::Load` before producing one. Never describe a pose replay as a
successful physics lap. Free-camera captures explain geometry but do not stand
in for the production driving POV.

### Match the comparison conditions

For each saved comparison record the commit/asset revision, source timestamp,
station and lane, heading, camera mode, FOV, resolution/aspect ratio, render scale,
quality settings and whether the frame is stationary, live or replayed. Keep the
unmodified reference/runtime images and annotate copies with measured differences.

Compare these features in order:

1. Road boundaries and vanishing point, with consistent car/camera scale.
2. Horizon and grade, including visible braking and turn-in sight distance.
3. Barrier setback/height, building silhouette and depth relationships.
4. Kerbs, runoff shape, pit separation and dangerous gaps.
5. Materials, lighting, foliage and crowds.
6. Motion: surface smoothness, camera stability, texture shimmer and LOD changes.

Match aspect ratio and view context before interpreting apparent dimensions.
Do not stretch, crop or change FOV just to make a comparison look favourable.
A different season, focal length or commercial-game camera needs an explicit
caveat. Uncertainty is a reason to seek another view, not invent certainty.

## 10. Use an independent critic and close the findings

The user previously selected **Luna with low reasoning effort** as the visual and
playing critic. When subagent review is authorized for the task, use that reviewer
if available; otherwise identify the substitute. This document does not require
spawning agents merely to read it. Give agents separate responsibilities and keep
one owner for shared edits and the heavy-job lock.

Useful assignments are source/geometry verification, independent visual critique
and live driving/performance review. Reviewers can inspect existing images and
logs in parallel; they must not launch competing Unreal builds or unguarded games.
A model that can only inspect captures must report that limitation rather than
claiming it played the game. The implementation agent must inspect the evidence
too; delegating review does not delegate responsibility for the result.

Give the critic the reference frames/video sections, accepted baseline captures,
new runtime captures, station index, known uncertainty and measured dimensions.
Do not give it only the new screenshots or lead it with "this is almost done."

Copyable review request:

> Review this circuit against the supplied reference and accepted Interlagos and
> Silverstone driving captures. Inspect the images, not just the implementation
> summary. Prioritize dimensions/POV, road and verge continuity, protection,
> uphill visibility, materials and motion quality. For every mismatch give the
> station or timestamp, side of track, visible evidence, severity and confidence.
> Distinguish a demonstrated defect from uncertain perspective/source-age effects.
> Say which criteria pass, fail or remain untested. Return blocking findings and
> the smallest next comparison that could resolve each one. If you cannot open a
> clip, run the game or inspect an asset, state that limitation. Do not call the
> full track acceptable from one good straight.

Track findings in a compact table:

| ID | Station/view | Evidence | Severity | Proposed cause | Fix/revision | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| Example | Uphill approach, left edge | Camera enters body before crest | Blocking | Height lag or support mismatch; not yet isolated | Pending | Same live approach at the same speed |

For each iteration, reproduce the defect, change the responsible data or code,
regenerate dependent outputs, recapture the same view and ask for a recheck.
Do not replace a failing camera view with a flattering one or resolve a finding
only by changing its wording. Numeric checks and visual review should challenge
each other. A positive reviewer verdict does not override a demonstrated gap,
invalid lap route or terrain spike.

## 11. Check performance without trading away the baseline

Use the same machine, resolution, render scale, AA, quality preset and camera for
the accepted track and candidate. Separate cold loading from warm steady driving.
Measure frame-time median, p95/p99, long stalls, peak memory and loaded tiles over
comparable runs, including the busiest straight and a full lap. State the input
route and any recording overhead. A capped 30 fps screenshot run cannot answer
whether a new map is as smooth as Interlagos.

The current renderer is forward-shaded with expensive features disabled in
`Config/DefaultEngine.ini`. Do not silently enable Lumen/Nanite, raise texture
budgets or lower resolution to make one map appear better. Treat a renderer-wide
change as a separate, explicitly scoped decision and check all existing tracks.

Inspect `FFPresentation` before choosing mesh granularity. Current behavior includes
roughly 950 m tile and 1,800 m building loading radii, a 250 m release margin,
synchronous near loading within 180 m and at most two outstanding async requests.
Its tile bounds and name prefixes affect those decisions. Small inaccurate bounds
can load a building too late; one huge tile can keep most of the circuit resident.
These are current implementation details, not targets to copy blindly.

Profile where the time goes before optimizing. Common costs are too many material
sections, shadow draws, foliage overdraw, unnecessary crowd shadows, large tile
loads and garbage collection. Preserve near-road silhouettes and contact surfaces
while simplifying distant geometry. The existing ground-shadow section helper can
be useful, but do not disable building/barrier shadows indiscriminately. See
[Epic's mesh drawing discussion](https://dev.epicgames.com/documentation/en-us/unreal-engine/mesh-drawing-pipeline-in-unreal-engine)
for the distinction between geometry and draw-call costs.

Test LOD transitions while driving both directions of approach. Investigate
popping, missing tiles and memory that grows across repeated sessions. A faster
empty scene is not a successful optimization. Agree any numerical performance
budget with the task; until then, compare repeatable runs against the accepted
baseline and report the measured difference without inventing a universal FPS pass.

## 12. Final acceptance and handoff

Do a complete live lap at normal driving pace, then inspect the risky sectors
again at speed and near their edges. Verify starts, first corner, both sides of
every sector, kerbs, off-track recovery, pit separation, crests, crossings and the
finish seam. Exercise unlimited laps and a finite session, including an invalid
lap, pause/resume, restart and return to the menu. Test keyboard and controller
selection/driving; distinguish injected events from physical-controller testing.

After shared code or materials change, recapture the affected accepted maps and
run their relevant checks. Do not silently alter Silverstone, Monza or Interlagos
to accommodate the new circuit. Verify the cooked package without relying on
ignored source downloads or editor-only assets.

Before saying the work is complete:

- All blocking review findings have been reproduced and closed with new evidence.
- The full circuit meets the geometry, POV, protection, terrain and visual criteria;
  the main straight alone is not sufficient.
- The package includes required native assets and data, with no missing dependencies.
- Focused tests and integration checks pass, and the new circuit is actually covered.
- Frame-time and memory evidence supports the performance claim and respects the
  11 GB limit. Platform/hardware checks not performed are explicitly identified.
- Source licences, provenance, transformations and estimated features are recorded.
- Asset generation is repeatable; shared assets and gameplay parameters are preserved.
- Git contains the necessary source/native assets, not raw reference videos, caches,
  engine binaries, personal paths or generated review captures.

Check individual Git blob sizes. Silverstone's surface is split into 48 MiB parts
to keep ordinary Git practical; any new chunking needs matching loader and test
changes. Do not byte-split a `.uasset`; divide large scenery into independently
loadable native assets instead. Prefer useful shared assets and scoped rebuilds
to repeated binary churn.
Do not assume deleting a large file in a later commit removes it from history.

Keep bulky evidence in `build/reviews/<slug>/` and record a concise durable summary
under `docs/`: tested revision, source/input hashes, capture stations, closed and
open findings, test commands/results, performance conditions and known limits.
Do not overwrite historical validation records with claims from a different build.

The final handoff should say what is playable, what changed, how it was checked,
which comparisons passed and what remains uncertain. If the available evidence
cannot meet the requested standard, describe the exact missing input or technical
blocker. Continue useful independent work and request targeted help; do not label
a visibly unfinished track "done" or wait for the user to rediscover the defects.

## Task prompt for the next agent

> Add **[circuit and layout/year]** using `docs/map.md`. References are in
> **[repository-relative folder or supplied links]**. Use accepted Interlagos for
> graphics, terrain and smoothness, and preserve the shared vehicle and driving
> POV. Work only in this repository, with no worktree or engine changes, below
> 11 GB used memory and one heavy job at a time. First inventory sources and the
> missing authoring tools, then build a representative straight/turn section and
> review matched Unreal driving views before extending the lap. Use **[authorized
> reviewer, e.g. Luna low]** for independent critique. Deliver the playable native
> Unreal circuit, complete collision/terrain coverage, source/licence records,
> repeatable authoring steps and measured validation. Keep failures visible and
> close them with evidence. Follow the task's commit instructions; do not merge or
> push without an explicit request.
