# Building and reviewing a Formula Forge track

Use this guide when adding a circuit or rebuilding one. Read [AGENTS.md](../AGENTS.md)
first. The deliverable is a track that looks right and drives smoothly in the
packaged Unreal game, with evidence for its dimensions and terrain. An overhead
render, successful import or passing unit test does not establish that quality.

The code paths and capture example were checked on 2026-11-03. Recheck the
loaders and commands when the implementation changes.
Whole-lap quality guidance was updated after the accepted Las Vegas review on
2026-11-06.
The additional-circuit workflow was revised on 2026-11-12 for source registration,
ground classification and dimension checks. These revisions do not establish
visual acceptance of the 18 additional venues.

This guide records the lessons from Silverstone, Monza and Interlagos. It also
maps those lessons to the current Unreal-only repository. It is not a claim that
an automatic track generator already exists here.

## 1. Establish the assignment and baseline

Confirm the circuit variant, direction, reference year and requested scope. A
historic layout, current Grand Prix layout and commercial game's interpretation
may differ. Record those differences before combining their sources. Adding a
track is authorized when the user requests it. Check the current project scope
and preserve its accepted baselines while adding the requested venue.

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
Some records describe historical Blender/GLB authoring whose payloads were removed
during earlier cleanup. Current supplied reference videos are in `Saved/Refs`;
current circuit recipes and retained survey inputs are under `Attribution/Sources`.
Inventory the actual files before assuming a manifest entry has a local payload.

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
- The additional circuits use `generate_circuit_scene.py` for offline geometry and
  `build_circuit_scene.py` for native Unreal imports. See the linked circuit scene
  workflow before introducing another builder. For extensions, check local engine
  headers before assuming an editor API or plugin is available.
- Keep new recipes and small source metadata versioned. Scratch conversions go
  in `build/`; a necessary generation script must not live only there. Validate
  inputs, give units explicit names and make rebuilding repeatable.

Use the existing circuit organization. `<slug>` denotes the venue identifier:

```text
Attribution/Sources/<slug>/       provenance, source URLs/hashes, licences, decisions
Content/Generated/<Track>/        native track assets and Review.umap
Content/Generated/<Track>/Data/   surface, limits and render manifest
Source/FormulaForge/Native/track_data/<slug>_*.inc
Source/FormulaForge/FF<Track>Geometry.cpp
tools/venues/<slug>.py            circuit-specific geometry and scenery
Saved/Refs/                      supplied reference videos; preserve these
build/reviews/<slug>/reference/   extracted reference frames
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

Uncertainty does not justify retaining a default that the reference contradicts.
A registered photograph can support a bounded architectural or ground estimate
without supplying survey coordinates. State what it establishes and what remains
estimated. Review visible defects at matched poses; do not turn missing survey
precision into an automatic visual failure.

A DSM includes trees and buildings. Check steep roadside banks against visible
verges, paths and tree roots before treating those heights as ground. Baku's
coarse seafront DSM produced exposed 15–21% banks where the reference shows a
curb-height promenade. A finite, source-supported ground estimate is preferable
to preserving that artifact. Document its uncertainty, protect the actual road
and structures, and join the retained outer ground through an explicit collar.

When a building outline conflicts with repeated primary roof imagery, retain both
observations and test the disagreement across acquisition dates. A reported
positional precision is not an absolute clipping boundary. Monaco's Villa de
Rome roof uses independently agreeing 2015 and 2019 traces while preserving the
conflicting IGN XYZ observations. Do not warp the image, compress roof objects or
invent a parallax correction merely to fit the older outline. Keep unresolved
height associations explicit and inspect both driving and whole-roof views.

Investigate conflicting height sources at their actual locations. At Portimão,
an unshifted primary orthophoto and the eight retained class-2 neighbours ruled
out embankment sampling and a bridge-deck step at the disputed climbs. The
operator's maximum uphill figure still differs from the measured profile,
including its global 100 m maximum. Preserve that discrepancy and the raw data;
do not cite an average at another location as reconciliation or scale the ground
to force agreement. See the [registration evidence](../Attribution/Sources/portimao/profile-registration-validation.json).

### Reference footage and Google views

Inventory the user's reference folder before asking for material. If the video
was removed, find permitted alternatives or request the missing reference. Never
claim to have reviewed a clip that is absent or inaccessible.

Create a frame index with timestamp, landmark, approximate lap station, direction,
camera type, visible road edges, structures, barrier side and observation. Include
starts, approaches, apexes, exits, crests, compressions and pit merges. Match by
landmarks and station rather than elapsed video time, since speeds differ.
Retain the full frame alongside any annotated crop.

Check continuity before registering a sequence. The Baku reference jumps from a
Niyazi Street approach on lap 1 to another sector on lap 2. A nearby video timestamp
therefore did not qualify the hotel's camera position. Record both sides of each
cut and use separate mapped or photographic evidence for the missing sequence.
For buildings, register each photographed elevation independently. An identifiable
building does not make its opposite entrance or side wing interchangeable.

### Is a reference video necessary?

A video is not a prerequisite, but a continuous onboard is the most useful
appearance reference for a whole-lap reconstruction. It reveals the order,
duration and scale of scenery, the vegetation between landmarks, braking boards,
kerbs, runoff mouths and night-lighting changes. A few famous-building photos
cannot supply that coverage. Las Vegas reached its accepted quality after the
supplied onboard was indexed around the entire lap, rather than used only for
the Strip and Sphere.

Use the requested layout, event year, time of day and weather where possible.
Register frames by corners and landmarks: cuts, accelerated playback and different
speeds make video time an unreliable distance measure. Keep footage reference-only;
author original geometry and artwork instead of shipping video pixels or game meshes.

Without video, assemble overlapping driving-direction stills for every sector,
including approaches, apexes and exits. Combine them with the circuit plan,
mapped footprints, operator/architect exterior views and elevation observations.
Record gaps and uncertain temporary structures explicitly. Video does not replace
metric geometry, height data or checking the finished game in motion.

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

Check the actual event route before smoothing it. A public-road centreline can
cross a temporary event corner by a chord, include an unused junction, or retain
a removed chicane. Portimão needed two route corrections; Australia and Singapore
needed event-corner curves absent from their street mapping. Use an event plan
and continuous reference views to choose the route. Keep schematic curve estimates
and their uncertainty explicit. Dense sampling alone cannot correct the shape.

After editing curves, audit the complete horizontal transformation. The native
sampler normalises the interpolated lap to the catalogue length. That extra scale
also affects where mapped buildings, trees, water and terrain must land. Record
the composed transformation in `scene-registration.json`; preserve the original
source scale separately. A station remap between two native curves uses their
relative transformation, rather than the full source-to-world transformation.
Rebase retained ground grids horizontally from their recorded `grid_uniform_scale`.
Keep their elevation datum and heights unchanged. Verify several mapped witnesses
around the entire lap, including the lap seam.

Prefer classified ground to a surface model for road heights. Retain raw samples,
classification, horizontal CRS, vertical datum, interpolation and missing-data
treatment. Compare local grades with primary evidence using a stated measurement
interval: a marketing maximum with no interval is not permission to flatten a
measured crest. Separate surveyed ground, reconstructed racing profiles and
estimated event widths in the source record.

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

A progressive bowl needs several lateral height samples. One bank angle only
represents a plane. The optional quadratic bank control preserves the centre
crossfall while varying slope across the road; outside the white lines it
continues the edge tangent. Fit those controls against registered cross-sections,
and record residuals and source precision. Tessellate both the visible surface
and tyre-support surface closely enough to follow the curve. Inspect the entire
paved outer bank up to the barrier, including entry and exit tapers. A correct
racing ribbon can still leave the car falling through its runoff if off-road
support blends back to a coarse terrain grid.

Do not extend the road's bank angle across a wide gravel trap by default.
Hockenheim's measured Sachs cross-sections flatten outside the kerb. Its optional
bank-edge controls join the road slope to the measured outer slope over a stated
distance. Use the same height function for rendering, tyre support and car roll.
Build one coherent lateral mesh partition at both ends of each road segment.
Merging nearly identical fractions from independently divided ends can create
strips that the degenerate-triangle filter removes, leaving contact holes.
Probe between the white line and the barrier as well as on the racing line.

Check elevation service precision before fitting crossfall. A service may return
integer metre heights even when queried at one metre intervals. Query spacing
does not establish measurement precision. Hockenheim uses the retained numeric
25 cm ground service for the road and bank fit; its integer metre scenery export
only supplies broad surrounding ground. Keep these roles separate in provenance.

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

Inspect the modifier domain as well as the height function. Offset ribbons can
fold and leave artificial notches; even a smooth kernel then creates steep
faces. Check actual packed cross-sections and locate the worst slopes. A valid
mesh with full coverage can still be a visibly wrong embankment.

An inherited DSM building base is also an estimate. If a low entrance and level
promenade contradict it, do not bend the public ground into a mound to preserve
that default. Qualify a relative base for the exact owner, preserve its footprint
and form, and prove its translated foundation contacts on the final ground.
Keep unrelated properties and the actual racing surface unchanged.

Keep authored role accuracy separate from mesh precision. A photographed verge
with half-metre uncertainty can support a documented millimetre boundary
adjustment around an existing triangle. That does not justify relaxing geometry
coverage tests or moving literal source polygons silently. Preserve the actual
post-deformation planes, normals and UVs when classifying the surface; replaying
old terrain to fix a material sliver can restore the very ridge being removed.

Cut or mask coarse terrain below the road/runoff where needed. Avoid coplanar
surfaces, raised ground covering the track, cracks and visible hanging edges.
Carry deck corrections through shoulders and barrier bases, not just along the
centreline. Keep interpolation diagonals consistent between rendered terrain and
the simulation grid.

For a local material change, compare the actual emitted triangles before and
after, including outside the painted region. Adding a small mask to a global
polygon union can change distant triangulation diagonals: the first Monaco
land-cover candidate moved an unrelated hillside surface by over 4 m despite
equal projected coverage. Preserve the original triangle planes, interpolated
normals and UVs. `CircuitScene.emitted_terrain_cells` lets a private producer
finish selected grid cells and skip only those cells in the final terrain loop.
Before using it, prove full coverage without overlap and preserve any deferred
verge or ground patches that share the cells.

Keep qualified polygon ring order stable when UVs depend on distance around a
perimeter. Equivalent GEOS unions can reorder holes without moving any vertex.
Hermosa's first full regeneration consequently shifted 934 new rock-face UVs
while preserving their XYZ and normals. Validate the derived domain against its
qualified source plan, then use that plan's ring order. Compare complete packed
faces after regeneration, including UVs and material names; equal silhouettes
alone will miss this failure.

Treat city foundations and public paving as a connected ground model. Roof-biased
DSM values cannot establish a building's ground-floor height. Check mapped street
connections, steps and property thresholds before fitting the surrounding paving.
Label assumed stair risers and reconstructed grades with their uncertainty.
At a bounded repair's outer edge, match the actual rendered terrain triangles.
Inserting vertices from a continuous height function can still leave a crack
against a coarse baked triangle whose plane differs from that function.

Check foundations against actual emitted ground around every exposed wall. A
missing ground probe may lie inside a separate retained building; inspect that
building's real walls and roof before filling the gap. For stepped entrances,
use one closed stair shell and check tread clearance, buried feet, winding and
paired edges. Nested boxes can overlap along their exposed sides even when their
top surfaces look correct.

Compare height sources at the same XY. A finer query interval does not establish
finer source resolution, accuracy or epoch. Plot sections through the proposed
repair and its outer collar: a smooth join can still introduce an unsupported
ridge or hollow. Check those locations in the cooked view before acceptance.
Inventory every existing tree and support rooted in the changed area. Reanchor
only the proven instances against actual packed ground, preserving their XY,
shape and all outside rows; a terrain correction can otherwise bury or float them.

Test triangle interiors as well as vertices. Spa's smooth vertex normals hid a
coarse mesh approximation that departed by up to 1.13 m from its unchanged ground
field. Refine a demonstrated problem locally, preserve the exterior triangle
planes, and measure the resulting render cost. More geometry needs a reason.

Check the entire inside offset, including shoulders and protection. A valid
asphalt edge does not guarantee a valid verge: Austria's T3 had a 12 m local
radius but an inside offset beyond 15 m. Folded grass quads were skipped and
seam triangles exposed their undersides. Register the real inner boundary;
do not narrow the road or cover the defect with another cap. An open infield
in the reference also does not justify an invented inside guardrail.

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

### Whole-lap quality workflow proven on Las Vegas

Use [Las Vegas's final validation](lasvegas_full_lap_validation.json) as an example
of the evidence and iteration required. Its recipes are
[route-environment.json](../Attribution/Sources/lasvegas/route-environment.json)
and [landmark-architecture.json](../Attribution/Sources/lasvegas/landmark-architecture.json).
Reuse the method; placements, heights and light values belong to that circuit.

1. Index the reference around the entire route before decorating. For each named
   sector record the visible structures, planting, stands, wall treatment, kerbs,
   escape roads and lights. Include ordinary connecting streets. Check the
   generator for station filters or clearance rules that silently omit a sector
   or delete a valid building. Vegas's missing trees and Wynn Plaza were such bugs.
2. Establish the correct building volumes before facade work. A resort's maximum
   height must not extrude its whole casino compound to tower height. Retain the
   mapped podiums and separate tower parts. Check whether the recipe's height
   already includes its crown; do not subtract or add the crown twice.
   `building:levels` multiplied by a standard floor height is only a fallback.
   Historic halls can have much taller floors: Baku's Court photo proportions
   contradicted its generic four-level envelope. Register a known facade width
   and several photo corners, retain perspective uncertainty, and model each
   floor's actual rhythm. An old estimate does not become a measured constraint.
3. Model the architecture that identifies each visible property: wings, curvature,
   roof profile, colonnades, projecting piers, balconies and entrance depth.
   Check operator or architect views when the onboard cannot resolve them.
   Distinguish roof outlines from ground-level walls. Covered terraces and eaves
   can extend beyond the building body; do not extrude their complete outline
   down to the ground or cut away terrain below an open overhang. Check fence
   panels and posts against the retained roof underside. Local decorative
   clearance corrections must preserve the actual concrete protection.
   Orthophotos show the uppermost visible surface. Register a driving-view hit
   in both XY and height before classifying it: Monaco's terrace roof was
   8–13 m above the sampled ground. Its pale paving did not identify the material
   below, or justify raising the ground to the roof.
   Establish neighboring property identities from route order, literal footprints
   and independent views. Category coordinates or an operator's directions point
   do not locate a particular facade. Baku's uphill gymnasium and downhill De Bour
   mansion were initially assigned to each other's footprints. Keep that rejected
   assignment separate from the corrected model. For photo dimensions, inspect
   crop and perspective-correction metadata before using EXIF camera intrinsics;
   edited photographs can still establish opening order without metric calibration.
   Hotel names on generic blocks do not meet this standard. Grand Chateau and
   Signature needed their own facade/crown designs, just as Venetian and Forum
   Shops needed their street-level architecture.
4. Give podiums separate floors and recessed shopfronts. Stretching a single
   window through a tall podium creates a blank wall. Keep ordinary glazing and
   interior lights subordinate to actual LED displays; alternating bright shop
   colours looked like invented advertisements. Place real displays at the
   correct level and around the footprint, with explicit exterior-clearance checks.
5. Fit temporary venues to the available space. Check complete stand depth,
   supports, roof, trees and balconies against mapped buildings and escape roads.
   Vegas's oversized Strip stand hid and intersected Harrah's entrance. Examine
   the full footprint of sidewalks and decorative panels too: a corner can
   overhang a runoff even when the panel centre and road-adjacent edge are clear.
6. Use the accepted assets and rendering style as the baseline. Copy materials
   into the new circuit's namespace before tuning them. For night scenes, compare
   road visibility, local lamp pools, facade fill, lit interiors, vegetation and
   displays together. Verify a test light actually affects the packaged renderer
   before replicating it hundreds of times. Vegas uses a registered irradiance
   field in private DefaultLit surface materials, preserving texture, specular
   and shadows; this is a venue-specific implementation, not a universal preset.
7. Review production cockpit captures across the whole lap. Vegas used sixteen
   settled detail views and a complete live lap sampled every 50 m, including
   all approaches and exits. Use enough samples for the circuit's complexity;
   those counts are examples, not a substitute for coverage. Add oblique views
   and a low driving view inside each escape road to reveal hanging panels,
   floating edges and protection defects hidden from the racing line.
8. Correct specific findings, regenerate the dependent native assets, and
   recapture the same view. Reviewers need reference frames, accepted-track
   captures and a station index. Distinguish a proven wrong property from regular
   windows that the real building also has. Check the final moving sequence
   after the last material change. Commit the recipes, native assets, provenance
   and validation together; preserve unrelated user edits.

Use a focused regression for a demonstrated generator defect. For the Vegas
sidewalk overhang, intersect exported pavement triangles with every escape
footprint; a test of panel centres would repeat the original mistake. Keep this
separate from the visual check that the exposed edge no longer floats.

Trace dark patches through the packaged material and lighting before changing
terrain. Spa's normal-strength experiment had no effect because the normal input
was flat. Preserve that failed result, then test the demonstrated cause with a
registered view. Keep a daylight direction consistent with the visible sky and
check the whole lap after rotating it; brightening one bank can darken another.
Do not use emissive grass or flatten supported ground to conceal poor lighting.

For foliage-card seams, separate crown coverage from shading. Check the texture's
occupied alpha bounds before enlarging the geometry, then inspect the saved native
material's normal input, tangent-space setting and two-sided response. A smooth
source normal does not prove that the packaged material uses it. Test a private
material on the affected trees, keeping their roots, texture, opacity and crown
positions fixed. Preserve the accepted shared material. Compare identical recorded
poses and verify camera position, rotation and FOV before judging the result;
follow that presentation test with a fresh live lap and uncaptured performance run.

Below a bridge, classify the ground independently from the deck visible in an
orthophoto. Ray-test the actual soffit and the complete plant volume, including
any material displacement. Query the saved material's world-position-offset input
before treating a nominal wind allowance as a proven bound. A garden above a
natural cliff also needs separate lawn, short retaining-wall and rock roles;
its total elevation change is not evidence for a masonry wall of that height.

Check landmark residency as well as authored geometry. A distant tower may exist
in the source scene but be absent from the live view because its tile is outside
the streaming range. Qualify the actual camera pose and tile bounds before
duplicating the building or declaring a skyline omission. Performance changes
must retain visible geometry and pass a moving-lap comparison at the same settings.

### Barriers, runoff and pit routes

Generate the visible protection and custom collision segments from one surveyed
path and one elevation revision. Keep posts upright; interpolate rail/fence
endpoints along slopes. Document the intended base, top, thickness, joins and
openings. A low-detail collision proxy still has to agree with the visible wall.

At a narrow bridge, distinguish the clear structural opening, girder axes,
legal racing width, kerb allowance, shoulder and wall thickness. Calculate both
the inner and outer wall faces. A wall can fit between the girders yet intrude
into the legal lane. Verify the emitted truss faces against the exported native
walls and limits, including both abutments. Anderson Bridge needs three
longitudinal trusses and two openings; the race uses the left opening. Removing
the central truss to fit an oversized road would conceal the alignment error.
Optional `kerb-margins.json` controls let a venue narrow its allowance with smooth
joins while other circuits retain their existing defaults.

Separate legal white-line width from the wider asphalt envelope. Sepang's 2016
designer specifies a constant 16 m legal lane; former outside asphalt becomes
runoff. Shrinking the asphalt with the legal line loses that pavement. Retain the
actual sampled width and shoulder lattice before changing it, and keep pit-wall
and garage offsets in world coordinates. A baseline that already includes a pit
transition must not have that transition applied again. Check effective native
shoulders too: runoff-width overrides can expand them beyond the raw controls.
See the [Sepang surface record](../Attribution/Sources/malaysia/racing-surface-review.json).

Validate compensation in compiled road exports. COTA's existing runoff minimum
overrode a correctly compensated raw shoulder profile, moving the effective
outer edge inward. The bounded fix preserves the original outer pavement after
that minimum, and the rendered apron uses the same retained width. Compare all
native samples and actual packed surfaces; Python profile arithmetic alone misses
runtime clamps and overrides. Keep raised kerbs separate from adjacent flat paint.
Retain literal control rows outside a finite correction. Adding interpolation
knots across the whole lap can round untouched shoulders differently, moving
terrain joins and spectators even when the intended lane edit is local.

Check physical contact beneath new flat aprons as well. COTA's back straight uses
the rendered apron planes for native height contact and asphalt grip, while its
legal limits follow the narrower white-line envelope. Colouring a grass shoulder
red would leave the wrong driving surface. Rebuild its contact with
`make cota-paving CIRCUIT_PYTHON=<circuit-python>` after profile edits, and compare
actual packed paint and native contact at both joins and along both sides.
Exercise `FFSimulation::Ground` and the native surface classifier directly. A
height file can contain correct planes while the simulation never queries them
on a flat track. Test asphalt and the grass just beyond it without changing
shared grip constants. Use unbuffered packed barycentric probes as well: a
buffered Python containment test hid an eight-micrometre F32 seam on COTA. Its
contact exporter now adds a bounded 0.3 mm bevel overlap on the original planes;
triangulate the complete bevel polygon and check overlapping height agreement.
Keep such repairs local rather than weakening every circuit's query tolerance.

Keep surface classification separate from height support. Buddh uses compact XY
unions for paved and gravel footprints, and separate original-plane triangles for
driving height. The existing classifier interprets a false asphalt flag as gravel;
grass requires no classification hit. A tiny height-encoding repair must never
expand the paved/gravel footprint. Check the actual native loader's minimum
triangle area before declaring coverage complete. If a verified source island
cannot be represented within the normal overlap, prove the encoding limit and
bound its height-only repair individually. Preserve the source plane and measure
overlaps with neighboring owners. Do not turn a numerical repair into a new
default tolerance or a change to rendered geometry.

Width changes can also alter the generated fallback height grid. Buddh retains
its old width for that grid while using the corrected width for legal limits.
Compare the compiled grid bytes, barrier exports, every road sample and original
outside controls. Verify the public authoring commands twice; a legacy profile
writer can silently restore an older wide lane after an otherwise correct fix.

Check face orientation independently of triangle size. An unnormalised cross
product measures area as well as direction: the old 0.35 cutoff left 12 cm road
stripes and small kerb tops facing downward. Road and kerb top emitters now use
only the sign; other surface roles keep their existing rules. Verify packed
winding, stored normals and attached UVs, then compare complete outside rows and
native physical data before regenerating an affected circuit. A changed byte
baseline needs a documented before/after scope proof, not just a new hash.
Reject triangles that collapse at the final float precision. The
[back-straight evidence](../Attribution/Sources/cota/backstraight-width-evidence.json)
retains the width estimate, source uncertainty and unchanged protection scope.

For clipped sloping ground, test the final encoded XY and Z together. Float
rounding can move a tiny outside fragment off its original plane and reverse its
geometric normal. Reproject its encoded XY onto that same parent plane before
encoding Z, preserving its normal and UV attributes. Keep strict normal checks,
measure any discarded subpixel fragments, and leave existing recipes unchanged
unless their own packed geometry demonstrates the problem.

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

Orient triangulated wall panels against the facade's known exterior. Check both
the source normal and the exported winding: the current `(-y, -x, z)` world
transform reflects the horizontal frame. A negative native cross/normal dot is
therefore not, by itself, an inward-face defect. Baku's actual defect was 4,833
source normals facing into their footprints. Reordering those triangles must keep
UVs attached to their vertices. Position and footing checks cannot detect this
rendering failure; inspect the corrected panels in the packaged cockpit view.

Keep exposure and rendering settings comparable to the accepted maps. Use lighting
to express the scene; do not use saturation, bloom or ambient light to conceal
missing geometry. Compare asphalt, kerb, grass, gravel, glazing, distant foliage
and sky together under the actual game settings.

Use detailed geometry where it affects cockpit silhouettes and near-field depth.
Register distinctive building parts to their literal mapped outlines. Baku's
Philharmonic towers occupy two explicit roof parts, not the ends of its bounding
rectangle; a nearby timber gallery is a separate low part. Qualify each visible
face from the corresponding photograph before repeating windows or balconies.
New facets created by clipping a building away from the road need their own span
checks. Assigning them the nearest long facade's window schedule can send trim
through protection. Compare emitted faces against the actual event envelope,
including fence height, and keep uncertain bases or hidden returns labeled.

Distant trees/crowds can use reviewed cards or simpler meshes with stable LODs.
The [Silverstone vegetation notes](../Attribution/Sources/silverstone/vegetation/README.md)
record occupied alpha bounds, physical crown size, edge-colour dilation and
multiple crown views. Those lessons still apply when producing native assets;
the historical Blender commands in that file do not.

Measure the occupied alpha bounds of the actual atlas cell. A small silhouette
inside a large cell produces a thin crown despite a plausible card width. Check
the native material's opacity threshold, mip settings and two-sided state; then
compare visible crown width and base height at the cockpit camera. Test the full
card rectangle against track protection as well as its visible alpha silhouette.

Avoid dense transparent layers, repeated identical tree outlines and crowds that
float or cover railings. Place crowds on real seating/deck surfaces. Build original
event artwork; do not paste sponsor strips or screens from the reference video.

For footprint-clipped seating, query heights at the clipped geometry. Unclipped
row corners can fall outside a corrected foundation and pick up unrelated DSM
roof heights. Check parcel-boundary tolerance, adjoining terrace heights, the
whole canopy and actual support endpoints. Hockenheim's Nord stand passed a
burial check while these queries still produced sawtooth seats and detached roofs.

### Baku waterfront frontages and park

`venues.baku_waterfront.finish(scene)` runs after the existing Mirbabayev finish.
Keep the original generic No. 89/91 emission so the adapter can replace only
those exact families. The photographed arch and dormer rhythms, literal building
plans, four mapped grass beds and 34 estimated park-tree poses have separate
source records under `Attribution/Sources/baku/waterfront/`. Absolute heights,
hidden details, thresholds and individual tree positions remain estimates.

The ground segmentation changes only 968 selected existing cosmetic parents.
It evaluates XYZ, normals and UVs on their original planes and retains the
unselected rows and material prefixes. Node and pack shared boundary vertices
before triangulating: the initial candidate's near-collinear 14–30 µm knots
collapsed onto a 78–156 µm native lattice and overlapped tiny ears. The final
construction preserves the strict overlap guard and retains the diagnosed
failed candidate. Check every tree foot again on the actual resulting fragments,
then review native alpha, shadows, texture scale and the complete driving view.

### Baku former No. 85

`venues.baku_no85.finish(scene)` follows the waterfront replacement and replaces
only generic owner279589354 on its literal plan. The current address5 and former
No.85 identity have separate primary mapping/photo evidence. Street edge9 and
long return10 are registered; absolute height, base and hidden elevations remain
estimates. Preserve the central double-height three-bay colonnade, lower
three-arched balcony tier, flanking loggias, corner oriels and stepped wings.
Do not turn those visible groups into a claimed full floor count. The source
recipe and exact-family/ground proofs are in `Attribution/Sources/baku/no85/`.

### Baku promenade, office and woodland

`venues.baku_park.finish(scene)` follows No. 85. It applies the reviewed finite
Ground replacement, translates only office owner 279935608 vertically, and
replaces the original 34-tree family with 98 source-fit trees. Keep the office's
literal plan and two-storey form; its relative base and the public-ground levels
remain estimates. The six mapped grass beds and photographed narrow verge have
separate role evidence. Source controls, exact output, contacts and review scope
live under `Attribution/Sources/baku/park-context/`. Compose semantic replacements
with the current parents, preserving No. 85 and every unrelated row. The earlier
Azneft/Niyazi public-junction problem is a separate, unapproved correction.

`tools/rebuild_baku_park.py --check` compiles the stored source-space control mesh
and verifies the exact reviewed Ground delta. Edit and requalify those authored
controls rather than relying on an ignored cache or silently patching the packed
output. The compile regression belongs in `make circuit-check`.

### Villa de Rome architecture

`venues.monaco_rome.finish_terrain(scene)` replaces only the exact 1,822-row generic Villa de Rome family in `Building_City_m1_01`. It operates on the current tile after other terrain/property producers, preserving every other packed row and the existing material-table prefix. It never reloads a saved parent City tile. Keep the call before final tile partition/save; Hermosa garden/tree updates and the underarch woodland remain independent.

The typed recipe and source qualification live in `Attribution/Sources/monaco/architecture/villa-de-rome/`. Developer evidence establishes the nine-storey building identity and south marble colonnade/loggias, balconies, mouldings and pediment. Eight estimated normal strata plus an occupied mansard represent that identity without claiming nine exposed floors on every elevation. The body/south façade remain the frozen V2 geometry.

The four-face upper hip, continuous mansard and thin closed soffit follow the qualified V3 source plan. Independent 2015/2019 primary traces set the nominal north roof eave and shoulder; their offsets from IGN remain explicit. Rooflight, fan tray and planted tray use direct source centres without an image warp. Original IGN XYZ are retained. Cornice 82.7 m, shoulder 86.6 m and apex 88.0 m absolute are architectural estimates; the unlocated 89.1 m maximum is unused. Exact north elevation, support/cantilever arrangement, secondary elevations and garden-floor contact remain unverified.

The adapter checks frozen geometry/body hashes, packed normals, closed main-roof/soffit edges, roof-plan coverage and direct object centres before replacing the old family. `Tests/test_monaco_rome.py` checks replacement preservation and atomic failure/source-registration guards. The native palette proposal uses explicit linear RGB values decoded once from the private diagnostic reference colours.

For the whole-roof native diagnostic, use the existing review game mode at world centimetres `(-42100, 3700, 11700)`, pitch `-46.7197392588`, yaw `-42.7275285141`, horizontal FOV `90`, resolution `1600×900`. The corresponding source coordinates are relative-Z metres, with `world_cm=(-100*y,-100*x,100*z)`. This constructed view supplements actual driving review; it does not change gameplay camera or establish in-route readability. Recorded frames 170/210/229/296 have roof occlusion/clipping limits.

### Villa de Rome garden

`venues.monaco_rome_garden.finish_terrain(scene)` follows the house replacement
and precedes final cliff classification. Its separate nominal 59.15 m absolute
lawn estimate retains higher actual relief with soil cover; it does not inherit
Hermosa's 8.5% north grade. The recipe preserves all old Ground rows and replaces
only the two exact mapped-tree families to support their feet on the new lawn.
Existing terrace materials and the stable qualified ring order are reused.
Pool and apron remain separate. Source stepping pads, the southern low rim and
unregistered barred opening remain held. See the explicit uncertainty and
coverage receipts in `Attribution/Sources/monaco/architecture/rome-garden/`.

### Monaco natural cliff cover

`venues.monaco_cliff_cover.finish_terrain(scene)` runs after property, support and
plant producers. It changes only 1,104 existing whole Grass faces to the existing
mixed `MonacoNaturalGround` material. The domain joins the qualified ravine with
literal woodland way 967508764 and retains formal-garden, path, building,
belvedere, barrier and racing exclusions. The former x = -12 m experiment crop
is not a mapped land-cover boundary. Preserve every packed XYZ, normal and UV,
all foliage and driving data. Whole-face area sum 89.18912134 m² and union area
89.18910511 m² differ by existing float-encoded boundary overlaps; compare the
same quantity rather than loosening an area guard. Mixed natural cover does not
establish exact bare-rock pixels, tree species or cliff elevations. Source
records are under `Attribution/Sources/monaco/architecture/cliff-cover/`.

`venues.monaco_ravine_roles.finish_terrain(scene)` follows that whole-face
classification. Its three photo-registered natural domains intersect 133.036 m²
of actual Runoff ground. Split the selected parents on their original planes;
preserve interpolated normals and UVs, every outside row, and the engineered
Marie/Rome junction. Eight natural slivers narrower than native float32 spacing
retain their complete original parent rows and an explicit classification miss.
Never remove ground to satisfy a material mask. The source recipe and coverage
proofs are under `Attribution/Sources/monaco/architecture/ravine-roles/`.

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

Verify that the simulation actually queries a new contact mesh in every intended
sector. A banking condition can make appended apron triangles reachable in a
banked corner but unreachable on flat straights. Exercise both cases and preserve
the protected road's existing height behavior. When rendered pavement supplies
contact, compare its actual packed vertices with the serialized contact data;
an analytic strip spanning the whole shoulder can cross a grass island or overlap
another branch even though the real apron is clear.

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
ternaries. Keep such a refactor focused on what the new track needs. The frontend
now derives its circuit list from the catalogue, but action IDs, selection state
and audit coverage still need checking when the catalogue changes. Flow audits
have also contained circuit-specific stages. Inspect the current sequence
deliberately; an old test passing is not evidence for a new map.

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

Before reviewing images, require the selected capture's `package.json` to match
the intended immutable package pin byte for byte. Verify its archive frame count
and resolve target filenames from that capture's own index. Check the report's
cited image and archive hashes against those exact files. A correctly named
report with the new pin can still describe an older capture: the first 7399
Monaco review accidentally used 32af images and its planting findings had to be
discarded. Preserve invalid reports as history and repeat the actual visual
review; replacing paths and hashes in the prose does not repair it.

The user selected **Luna with high reasoning effort** for the accepted Las Vegas
visual review. When subagent review is authorized for the task, use that reviewer
if available; otherwise identify the substitute. This document does not require
spawning agents merely to read it. Give agents separate responsibilities and keep
one owner for shared edits and the heavy-job lock.

Useful assignments are source/geometry verification, independent visual critique
and live driving/performance review. Reviewers can inspect existing images and
logs in parallel; they must not launch competing Unreal builds or unguarded games.
A model that can only inspect captures must report that limitation rather than
claiming it played the game. The implementation agent must inspect the evidence
too; delegating review does not delegate responsibility for the result.

Keep geometry preservation and appearance decisions separate. Monaco's corrected
land-cover geometry passed its plane and seam proofs, but the cockpit still
showed a stark faceted slope, an angular green patch and undersized vegetation.
That remained a visual hold. Trace disputed image pixels to their actual mesh
faces and then to the primary sources: gray areas can be a garden terrace,
another road, an omitted bridge or an unmodeled building. Each needs its own
treatment; expanding a grass mask cannot resolve all of them.

Bind those rays to the exact captured frame, package and current source manifest.
Project the changed domain into that same camera before attributing a defect to
it. Monaco's visible 240 m wedge was outside the new upper-bank patch; at 260 m
the patch was entirely offscreen. That finding concerned older surfaces, not the
new collar. A HUD, bridge or roof can also hide a correct projection. Record
insufficient visibility and add a useful comparison view instead of inventing a
patch-specific pass or failure.

Verify a claimed missing landmark against the current source and native asset,
then inspect its exact registered capture. Jeddah's Masarat was initially called
missing despite being baked and visible in the target. Conversely, an import log
alone does not prove visibility. A differing source SHA can also reflect material
slot ordering: establish material-name and packed-attribute equality before
calling that a missing geometry change. Preserve the exception's evidence chain.

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

Check test dependencies before pruning authoring caches. The Malaysia pavement
regression reads its packed `Tile_Street_*.mesh` files to compare rendered vertices
with native contact. Preserve those files or regenerate them before `circuit-check`;
require the regenerated manifest to match the retained baseline exactly. A cached
mesh is reproducible, but deleting it can still break the next required check.

Keep bulky evidence in `build/reviews/<slug>/` and record a concise durable summary
under `docs/`: tested revision, source/input hashes, capture stations, closed and
open findings, test commands/results, performance conditions and known limits.
Do not overwrite historical validation records with claims from a different build.

Preserve public Unreal asset classes and object paths during partial imports.
For example, keep an existing material instance and update its private parent
when replacing the shader. Unchanged meshes can retain imports naming the old
asset class; replacing that instance with a different class at the same path
can break those references despite a successful local material build.

A graph constructed under `-NullRHI` has not passed shader compilation. Set
texture-object sampler types explicitly for normal and mask maps, inspect the
saved nodes, and check the target-platform cook log. Unreal can finish a cook
while substituting its default material after a shader error. Treat any such
fallback as a failed build and fix it before capturing or reviewing the result.

Inspect inherited vertex-data inputs when copying an accepted material. FFLVM1
meshes provide UV0 and no authored vertex colors. The Monza surface parent also
supports baked AO encoded in UV1. Leaving `UseBakedAO` enabled on Baku's generated
stone made triangle-local UVs look faceted; continuous negative world UVs then
made the same walls nearly black. The textures were correctly set to wrap.
Disable unsupported baked-AO and vertex-color inputs in the local generated
instances, preserving the accepted parents and textures. Verify actual saved
parameters and compare the same native camera before declaring the fix complete.

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
> reviewer, e.g. Luna High]** for independent critique. Deliver the playable native
> Unreal circuit, complete collision/terrain coverage, source/licence records,
> repeatable authoring steps and measured validation. Keep failures visible and
> close them with evidence. Follow the task's commit instructions; do not merge or
> push without an explicit request.

For the additional video-backed venues, use the
[circuit scene workflow](circuit_scene_workflow.md) for the native sampling,
source corrections, physical envelope, private materials and review commands.
