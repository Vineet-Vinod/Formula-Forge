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
