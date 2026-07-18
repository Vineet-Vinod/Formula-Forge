# Formula Buggy

Formula Buggy is an original Linux/C++ arcade kart racer aimed at a
bright tropical beach-buggy feel without copying proprietary Beach Buggy
Racing assets, names, tracks, or game data.

The primary build is `harbor_karts_3d`: vendored SDL3 input plus vendored
raylib on SDL/EGL/OpenGL ES 2. The game uses a fixed-step arcade vehicle model,
checkpoint-validated races, custom GPU meshes, a stylized lighting/fog pass,
procedural SDL3 vehicle audio, and a responsive HUD. The older SDL software
framebuffer build remains only for diagnostics and comparison.

## Build

Requirements:

- `g++`
- `make`
- `cmake`
- Linux with X11 runtime libraries

The SDL3 source dependency is vendored and pinned. The first build verifies and
builds it automatically:

```sh
make
```

The executable is:

```sh
./build/game/harbor_karts_3d
```

## Run

```sh
make run
```

`make run` launches the 3D game. It opens fullscreen by default. For debugging:

```sh
./build/game/harbor_karts_3d --windowed
./build/game/harbor_karts_3d --dev-keyboard --windowed
./build/game/harbor_karts_3d --diagnose-controller --windowed
```

## Controls

Gamepad and keyboard are both supported.

- Left stick / D-pad or A/D / arrows: steer; change the highlighted menu choice
- RT: accelerate
- LT or B / Circle: identical hard brake and corner-entry slide; hold at low
  speed to reverse
- W / up and S / down: keyboard accelerate and brake
- D-pad or arrows/WASD: navigate driver, car, map, lap, pause, and results screens
- LB/RB or Q/E: previous/next choice on selection screens
- A / Cross or Enter: confirm, select, or start
- B / Circle or Backspace: return to the previous selection stage
- Start or Escape: pause the race
- Back / Select: resume from pause; R resets to the last valid checkpoint while racing
- Start + Back / Select or F10: quit

## Current Gameplay

- Six selectable circuits: the original Sunset Cove, retained Spa Coast, and
  arcade-scale Suzuka, Silverstone, Monza, and Interlagos layouts
- Staged driver, car, map, and 2/5/10/infinite-lap race selection
- Formula Buggy startup screen, beach-themed selection flow, full race results, replay/home actions, and pause controls
- 6-car racing pack with AI opponents
- Four original Blender-authored cars: Tidebreaker XR, Sunskipper GT,
  Reefrunner R4, and Boardwalk Bruiser
- Six original Blender-authored drivers: Imani Reef, Dax Calder, Marina Quill,
  Niko Brass, Sol Vega, and Bea Torque
- No powerups and no character super powers
- Blender-authored circuit worlds with roads, curbs, runoff, sandy terrain,
  ocean, palms, coastal houses, rocks, and start gantries
- Meter-scaled GLB car and driver meshes with named `idle`, `accelerate`,
  `brake`, `turn_left`, and `turn_right` animation clips
- Runtime dust, brake lights, ground shadows, soft particles, body pitch/roll,
  and airborne presentation; the procedural track, car, and driver renderers
  remain as fallbacks when an authored GLB cannot be loaded
- Speed-reactive ground-referenced chase camera with slide framing, restrained
  pullback, smooth FOV, collision shake, and landing kick
- Momentum-preserving arcade handling with bounded tire grip, speed-sensitive
  steering, binary brake oversteer, forgiving shoulders, real gravity,
  airborne control, landing compression, vehicle-specific collision strength,
  and automatic stuck recovery
- Procedural engine, drivetrain, road, wind, tire-scrub, and landing audio
- Reference-calibrated 49-53 second baseline race laps with pack interaction
- Metric lap-length, elevation, road-width, and grade-separation contracts for
  Spa Coast, Suzuka, Silverstone, Monza, and Interlagos
- Race and Time Trial sessions: full-grid finite races or solo infinite-lap
  running with current and best lap timing
- Grid countdown, ordered checkpoints, shortcut-resistant laps, wrong-way
  detection, finish order, and checkpoint reset ghosting
- Fullscreen Linux build with controller/gamepad support

## Blender Asset Pipeline

The production flow is:

`Blender Python source -> .blend -> .glb -> C++ GlbAsset loader -> raylib`

`uv` pins the Python and `bpy` versions. Editable sources, runtime exports,
preview renders, and integration metadata live together under
`assets_src/{vehicles,drivers,tracks}/<asset>/`.

```sh
uv sync --frozen

# Manifest-driven pipeline smoke asset
uv run --no-sync python tools/build_assets.py list
uv run --no-sync python tools/build_assets.py build smoke_kart
uv run --no-sync python tools/build_assets.py validate smoke_kart
uv run --no-sync python tools/build_assets.py preview smoke_kart

# Production cars and drivers
uv run --no-sync python tools/blender/generators/generate_vehicles.py --asset all
uv run --no-sync python tools/blender/generators/generate_drivers.py --asset all
uv run --no-sync python tools/blender/generators/verify_assets.py

# Production circuit worlds
uv run --no-sync python tools/blender/tracks/generate_tracks.py --track all
uv run --no-sync python tools/blender/tracks/verify_tracks.py --track all
```

Vehicle exports range from 1.84-2.04 m wide, 3.73-4.13 m long, and
1.27-1.63 m high. Seated driver exports stay near 0.64 m wide,
0.65 m deep, and 1.07-1.16 m high, and attach at the common seat anchor. The verifiers check dimensions,
required nodes and materials, mesh budgets, previews, skins, and exactly one of
each gameplay animation; the C++ loader independently enforces runtime bounds.
Blender authoring uses X width, Y length, Z height; raylib/glTF runtime bounds
use X width, Y height, Z length. See `tools/ASSET_PIPELINE.md` and
`tools/blender/tracks/README.md` for the full coordinate and track-alignment
contracts.

## Verification

```sh
make self-test
make race-audit
make capture-playtest
make perf-audit
make smoke-3d
make audio-audit-3d
make vehicle-audit-3d
make race-flow-audit-3d
make capture-playtest-3d
make handling-audit-3d
make race-audit-3d
make spa-audit-3d
make track-catalog-audit-3d
make time-trial-audit-3d
make capture-spa-tour-3d
make capture-map-gallery-3d
make capture-time-trial-3d
make spa-perf-audit-3d
make collision-audit-3d
make perf-audit-3d
./build/game/harbor_karts --smoke-render --dev-keyboard
SDL_VIDEODRIVER=offscreen ./build/game/harbor_karts_3d --asset-audit
```

`--self-test` runs a deterministic physics/AI smoke test without SDL.
`--audio-audit` runs nine hardware-independent DSP checks for engine load,
speed, tire scrub, landing response, output bounds, and determinism.
`--vehicle-audit` runs 27 deterministic unit checks for momentum, steering,
binary brake oversteer, surfaces, jumping, landing, and fixed-step consistency
without opening a window. `--race-flow-audit` runs 20 checks for countdowns, checkpoints,
wrong-way state, finish ordering, infinite races, and discontinuity handling.
`--race-audit` runs a longer headless simulation and reports progress jumps,
cave transitions, turn balance, no-brake corner speed, and off-road excursions.
`--capture-playtest` writes deterministic loading, selection, pause, result, and race frames to
`build/playtest_frames` so visual and camera changes can be inspected without a
working video device.
`--perf-audit` renders 420 worst-case section frames without sleeping and fails
if p95 frame time misses the 60fps budget.
The smoke render verifies SDL startup and framebuffer presentation.
`capture-playtest-3d` writes deterministic 3D frames to `build/playtest_frames`
for visual inspection.
`race-audit-3d` runs the 3D scripted player against live AI and validates lap
pace, pack pressure, contact rate, overtakes, and every kart's progress stability.
`spa-audit-3d` verifies Spa Coast's lap length, sampled FIA elevation stations,
overall relief, mesh length, road width, two-kart passing room, and non-local
branch clearance without opening a window.
`track-catalog-audit-3d` verifies the lap length, elevation relief, road-width
range, and grade separation of Suzuka, Silverstone, Monza, and Interlagos.
`--asset-audit` opens every production GLB through the C++ loader and requires
all four cars, six drivers, and six tracks to pass dimension and animation
contracts. `capture-map-gallery-3d` writes a selection-screen preview for every
circuit.
`time-trial-audit-3d` drives a complete solo Spa lap and verifies one-racer
flow, infinite laps, best-lap timing, parked opponents, and no results transition.
`capture-spa-tour-3d` writes nine course views for visual inspection.
`capture-time-trial-3d` writes the live and paused solo timing HUD states.
`collision-audit-3d` runs deterministic rear-end, head-on, and side-swipe
contact cases and fails if the kart bodies remain overlapped.
`perf-audit-3d` records 3D frame timings and fails if p95 misses the 60fps
budget.
`--diagnose-controller` prints both raylib and direct SDL controller readings,
which helps with USB receivers that expose a partial or unusual mapping.

## Source Layout

- `src/main.cpp`: process entry point only
- `src/main3d.cpp`: 3D process entry point only
- `src/arcade_vehicle.*`: deterministic arcade vehicle dynamics and unit audit
- `src/arcade_audio.*`: procedural SDL3 vehicle soundscape and DSP audit
- `src/arcade_race.*`: checkpoint race director and unit audit
- `src/arcade_render.*`: GLES2 lighting, authored asset integration, and procedural fallbacks
- `src/glb_asset.*`: RAII raylib GLB loader, dimension checks, and named animation sampling
- `src/arcade_hud.*`: responsive loading, selection, race, countdown, pause, and results UI
- `src/track_renderer.*`: textured, chunk-culled GPU road mesh
- `src/core_math.hpp`: math, color, and geometry helpers
- `src/renderer.hpp`: low-overhead software renderer and bitmap text
- `src/harbor_karts.cpp`: SDL platform loop, renderer, simulation, controller input
- `src/harbor_karts_3d.cpp`: raylib 3D renderer, simulation, controller input,
  capture harness, and 3D race loop
- `src/harbor_karts_3d.hpp`: 3D entry-point declaration
- `src/track_layout.hpp`: Sunset Cove and Spa Coast centerline/elevation data
- `src/track_catalog.*`: Suzuka, Silverstone, Monza, and Interlagos geometry contracts
- `tools/build_assets.py`: manifest-driven Blender source/export/validation CLI
- `tools/blender/generators/`: production vehicle and driver generators and verifier
- `tools/blender/tracks/`: production circuit-world generator and verifier

## Third-Party Code

See `THIRD_PARTY_LICENSES.md` and `third_party/README.md`.
