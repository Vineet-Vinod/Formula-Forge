# Rebuilding the additional circuit scenes

The video-backed additions are Australia, Austria, Bahrain, Baku, Buddh, Canada,
China, COTA, Hockenheim, Jeddah, Malaysia, Monaco, Portimao, Singapore, Spa,
Suzuka (`japan`), Turkey and Zandvoort. Their clips and appearance registrations
are listed in `Attribution/Sources/<slug>/reference-index.json`. Reference clips
remain in `Saved/Refs`; they are not packaged artwork.

Use the quality and review requirements in [map.md](map.md). A generated mesh,
passing geometry audit or attractive pit-straight screenshot is not acceptance.
Compare the whole route, including ordinary buildings, wooded banks, escape
areas, protection and the spaces between landmarks. Preserve the accepted
Silverstone, Monza, Interlagos and Las Vegas assets and vehicle settings.

Install the authoring dependencies into a project-local Python environment from
`tools/requirements-circuits.txt`. Unreal's embedded Python only imports the
prepared meshes and does not need the offline geometry dependencies.

```sh
make circuit-check CIRCUIT_PYTHON=build/tmp/lasvegas-python/bin/python
make check
make circuit-assets CIRCUIT=japan CIRCUIT_PYTHON=build/tmp/lasvegas-python/bin/python
make package
```

`circuit-assets` exports native samples, generates the selected venue and imports
four serial mesh batches through the memory guard. Do not run multiple Unreal
operations. Keep total machine memory below 11 GB, including authoring processes;
the guarded runner imposes a lower stop threshold. Keep video extraction sparse
and serial, and record peak memory for scene generation.

The exporter partitions dense tiles into independent native assets of at most
400,000 triangles. Each part retains the original vertex, normal, UV and material
data and has its own bounds and manifest entry. Keep every part in the import
and runtime manifests; partition the source geometry before Unreal builds its
assets. This preserves detailed architecture within the import memory budget.

Register the garage frontage in `pit-lane.json`: native start/end, driving side,
paving depth and pit-wall offset. Apply an edited registration with
`tools/circuit_profiles.py <slug>`, then export fresh samples and regenerate the
closed envelope as below. The source builder also consumes this registration.
Pit paving is a visual service area beyond the closed driving boundary; it must
not enlarge that boundary. Include garage bays, foundations and roof structure.

When relocating or shortening a pit, restore the retained original shoulder
lattice from `shoulder-baseline.json` before applying the new registration. Leaving
the old inset in place can put a closed wall on both sides of the straight.
Preserve locally varying original widths; a constant replacement loses them.
Check the driving side against forward-facing footage and a mapped event plan.
Primary building lengths and actual stand footprints take precedence over generic
station intervals. Audit both ends, depth, seating coverage and roof coverage.

Use typed `sections` in `shoulder-corrections.json` for locally registered
protection distances, with explicit side and cubic transition spans. Check the
exported columns against the intended physical side. An overly wide shoulder
also flattens terrain: it can depress a spectator bank or remove the land between
stacked streets even when the road profile itself is correct.

The 8,192-station samples for the new venues supply the visual road, contact
surface and simulation path. The accepted circuits retain their sampling.
Native station zero is an arbitrary retained source origin at several venues;
`start-line.json` registers the timing control line without rotating the world.
Its stated uncertainty also applies to the visible line. Starting-grid placement
is a separate visual reconstruction confined to the pit straight.

`RoadStation.point(+lane)` is driver-right in the source east/north frame.
Historical native shoulder column names follow a reflected simulation normal;
do not infer physical sides from those names. Confirm sides using mapped pits,
corner direction, footprint registration and cockpit views.

Venue geometry lives in `tools/venues/<slug>.py`. Register kerbs and runoff before
architecture so surrounding ground can join their extents. Keep water in
`water_shapes`, visual-only ground exclusions in `terrain_cutouts`, and physical
road/escape additions in `extra_corridors`. A water polygon must never become a
physical track boundary.

Check coastline topology against known dry streets and known sea points before
cutting terrain. A missing connector outside a query box can turn an entire city
into a water polygon. Model ordinary mapped frontage as well as landmarks; a few
hotel models do not fill an urban circuit. Use semantic tags and actual stand
footprints rather than classifying buildings by height or guessing stand spans.

Check foundations along the full footprint of long buildings. Spa's Endurance
pits descend beside the road; a single base height from the footprint centroid
left the downhill end in the air. Model graded garage bays and clip roofs to the
mapped footprint. Use the reference or a primary photograph to distinguish a
garage row from a spectator stand or office block.

Inspect tight inside corners for folded offsets. Albert Park's T3 produced
overlapping grass faces and a detached white edge stripe even though the native
lap passed. Trace suspicious pixels to their source triangles before changing
terrain or the driving line. Check winding, overlapping surfaces and the union
of the road footprint, rather than covering an artifact with another polygon.

Check black patches with the exact recorded camera pose and sunlight direction.
At Albert Park, a separate dark strip hit intact upward-facing paving; opaque
leaves blocked its sunlight. Include the foliage atlas alpha in shadow-ray
checks. Keep that finding separate from a missing face or folded curb elsewhere.

Audit visible coastlines and rivers explicitly. Singapore, Jeddah and Baku once
had no water geometry, so the urban terrain material filled their bays. Retain
complete shoreline relations, island and pier masks, wet/dry witness points and
the water's relative vertical datum. Bridge crossings need water below the road.
Water must never enlarge the physical driving envelope. Compare DSM terrain
against mapped buildings too: Singapore's apparent hills included the roofs of
The Shoppes and Flower Dome. Replace those footprints with grounded architecture.

Use ground elevations for dense city terrain. A surface model can include hotel
roofs and turn the gaps between stacked streets into cliffs. Monaco retains IGN
RGE ALTI samples in `scenery-ground.json` and the hashed compressed grid it names.
`circuit_terrain.py monaco` validates and materializes that grid before scene
generation, including when a terrain binary already exists. Its datum uses the
unchanged road profile outside the tunnel; unsupported samples retain the
documented fallback. The 12 m scenery grid does not replace racing elevations.
Its 2 m ground join and locally narrow shoulders preserve land between roads at
different heights. Check retaining walls and foundations in cockpit views after
changing either distance.

After changing road widths, banking, escape shapes or protection, regenerate the
physical envelope as a deliberate source change:

```sh
make build/tests/export-circuit-scene
build/tests/export-circuit-scene bahrain
build/tmp/lasvegas-python/bin/python tools/circuit_boundaries.py bahrain
make check
make circuit-assets CIRCUIT=bahrain CIRCUIT_PYTHON=build/tmp/lasvegas-python/bin/python
```

The closed envelope preserves islands and removes offset cusps that can put a
wall across a tight corner. Native checks require closed wall endpoints, road
containment, contact coverage and clear car footprints. The older constant-offset
wall check does not describe a union around an acute corner. Suzuka's crossing
requires separate branch handling; the planar boundary tool rejects it.

Resolved native shoulders can include the previous runoff-zone width. After
narrowing a runoff, export again after the new zones compile, regenerate the
envelope from those refreshed samples, and verify the final physical wall
distance. Suzuka uses its existing deck-aware protection instead of this planar
union; apply its shoulder recipe and rebuild/export directly.

The envelope also excludes occupied building footprints with a small foundation
clearance. Check the visible wall against the actual garage and stand fronts;
a barrier hidden behind a foundation still passes a centreline-only test.

Apply retained controls with `circuit_profiles.py --alignment <slug>` for XY,
`--racing <slug>` for elevation, width and registered official turns, and the
default operation for pit/shoulder corrections. Export and compile after each
dependent native change. The final `alignment-refinement.json`, when present,
takes precedence over `alignment-corrections.json`. Preserve its frozen input
and the recorded composed source-to-world transformation. If the primary event
curve changes, rebuild refinement from a fresh export of that curve; refining
the previous frozen input would silently discard the new event geometry.

`circuit_alignment.py` reconstructs the explicitly evidenced arcs; its optional
`--refine-sigma` operation removes bounded mapping noise and retains a one-metre
movement limit. It does not select the correct event route. Portimão's retained
replacement alignment includes two route changes and must not be reconstructed
from its historical false-route baseline. Avoid running the legacy global
`build_circuits.py` generator over curated source decisions without checking
every output it would replace.

Use `circuit_ground.py <slug>` only for a venue with a validated
`classified-ground.json` and retained classified points. It derives the road
profile and surrounding grid in the current registered frame. Retained regional
ground grids are materialised by `circuit_terrain.py`; their horizontal scale
can change after alignment edits, while source heights and datum stay fixed.
Use bounded processes for either operation, alongside the machine memory monitor.

Retained `elevation-corrections.json`, `banking-corrections.json`, width recipes,
layout reviews and pit-shoulder corrections are rebuild inputs. They must survive
source generation. Published elevation diagrams describe road profiles; coarse
surface models can instead sample roofs through a tunnel. Keep those sources
separate. Copernicus scenery windows are DSMs, not bare-earth surveys; building
foundations must not add another building height on top of a sampled roof.

The importer uses private material copies and recipe/source hashes. Rebuild all
four batches after a material change so every mesh slot is rebound. Check cutout
fencing and tree atlas UVs in the actual game: a plausible material name can still
refer to opaque corrugated panels or an atlas layout the mesh does not use.
Grandstands need oriented treads, closed risers, supports, end closures and roof
soffits; disconnected horizontal cards are not finished stands.

The private road material reuses Interlagos asphalt. Its UV contract is
longitudinal U and lateral V, both in two-metre units. Escape surfaces and their
paint follow the local road branch; scenery DSM heights must not lift them into
the surrounding banks. At a crossover, keep the two road branches separate.

Register paved triangles before painting them. Use `paint_surface` to project
paint onto those exact triangle planes with a 5 mm offset; a road-height estimate
can leave paint floating or buried. Verge geometry is emitted after all paving
and excludes its footprint. Inspect complete motifs, including their extremities,
against both the pavement and grass meshes. Tight infield islands need their own
reference-shaped polygons when parallel road offsets fold across the corner.

Night scenes need visible falloff between road-directed light pools, illuminated
roof undersides and readable garage detail. A saturated light field or excessive
emissive asphalt makes the road uniformly pale. Judge this in the cooked game;
an editor game preview with unresolved materials is not valid lighting evidence.

For full-lap review, build `build/tests/audit-circuit-lap` and run it with a circuit
slug. It writes a private review racing line and real fixed-step telemetry in
`build/circuits/<slug>`. The saved speed multiplier changes the review controller,
not vehicle tuning. Use `-FFRacingLine=<absolute review-line path>` with `-FFRecord`
for a packaged live run. Do not use the Silverstone-specific racing-stint audit
as a generated-circuit lap validator.

Capture with an absolute `-FFCapture` path. Inspect full-resolution frames at
regular route intervals, every corner/escape and all reported defects, plus
matching reference views. Record frame rate, contacts, off-track events,
airborne frames and rendered penetration. Require Luna High review of the final
packaged scene. Retain failed findings, fixes and final hashes; rerun acceptance
when the reviewed geometry or materials change. Keep native assets versioned and
commit completed checkpoints without pushing or merging.

Recorded surface-penetration telemetry checks the drive-surface mesh. It does not
prove that scenery walls, stand treads or roof slabs clear the cockpit. Inspect
those structures throughout the moving lap, and measure their actual generated
triangles against the road when an obstruction appears.

Replay cuts and camera poses matter. Verify reference corner identities using
the minimap, landmarks and lap timer; do not interpolate station through a cut.
Capture approaches and exits too: paint directly beside a stationary car at an
apex can be outside its field of view. Confirm missing geometry through moving
frames or projected mesh positions before relocating a correctly placed feature.

Pin each review finding to the exact capture path, image hash, station sidecar
and asset revision. Reopen that image before changing geometry: a stale capture
or swapped filename can turn a valid bridge into a reported obstruction elsewhere.
Measure projected visibility when needed. A grounded eleven-metre marking can
be only a few pixels tall in a distant, low cockpit view.

The packaged executable opens the menu by default. For an unattended driving
capture, explicitly open the existing review level with the trial game mode:

```sh
bash tools/unreal.sh run -windowed -RenderOffscreen -ForceRes -ResX=1600 -ResY=900 \
  -FFCircuit=japan -FFStation=2272 -FFCaptureDelay=8 -FFQuitAfterCapture \
  "-FFCapture=$PWD/build/reviews/japan/underpass.png" \
  '-ExecCmds=open /Game/Generated/LasVegas/Review?game=/Script/FormulaForge.FormulaTrialGameMode'
```

Create the output directory first. Shell-quote arguments containing spaces; do
not embed an additional pair of quote characters in their values. The review
level name does not select the circuit: `FFCircuit` controls its scene and
simulation. For a live lap, replace the capture options with `FFRacingLine`,
`FFStation` just before the registered timing line, `FFRecord`, `FFRecordLaps=1`
and `FFQuitAfterRecord`. A run left in the menu supplies no driving evidence.
