# Formula Buggy

Formula Buggy is an original Linux/C++ arcade formula racer that combines
open-wheel cars and circuit driving with a bright tropical setting.

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

Gamepad, steering wheel, and keyboard input can be used together. The
DragonRise Wired Wheel (`0079:189c`) is detected automatically, with a linear,
low-deadzone steering profile and analog accelerator/brake pedals.

- Left stick / D-pad or A/D / arrows: steer; change the highlighted menu choice
- RT: accelerate
- LT or B / Circle: brake for corner entry; hold at low speed to reverse
- RB / E: shift up; LB / Q: shift down
- W / up and S / down: keyboard accelerate and brake
- D-pad or arrows/WASD: navigate driver, car, map, lap, pause, and results screens
- LB/RB or Q/E: previous/next choice on selection screens
- A / Cross or Enter: confirm, select, or start
- B / Circle or Backspace: return to the previous selection stage
- Start or Escape: pause the race
- Back / Select: resume from pause; R resets to the last valid checkpoint while racing
- Start + Back / Select or F10: quit

Wheel controls use the rim for steering, accelerator and brake pedals for RT
and LT, the wheel's A/B buttons for confirm/back, the D-pad for menus, and the
shoulder/paddle buttons for shifting. Multiple connected SDL input devices are
merged, so a wheel and gamepad do not need to be unplugged to switch between
them.

## Current Gameplay

- Five selectable meter-scaled circuits: Spa, Suzuka, Silverstone, Monza, and
  Interlagos layouts with audited turn order,
  handedness, dimensions, and elevation
- Staged driver, car, map, and 2/5/10/infinite-lap race selection
- Formula Buggy startup screen, beach-themed selection flow, full race results, replay/home actions, and pause controls
- 6-car racing pack with AI opponents
- Four original Blender-authored open-wheel formula cars: Tidebreaker FX,
  Sunskipper F1, Reefrunner FA, and Boardwalk Formula, each with front and rear
  wings, exposed suspension and wheels, sidepods, an open cockpit, halo, and diffuser
- Six original Blender-authored drivers: Imani Reef, Dax Calder, Marina Quill,
  Niko Brass, Sol Vega, and Bea Torque
- No powerups and no character super powers
- Blender-authored circuit worlds with medium-gray tarmac, continuous track
  limits, driveable curbs and runoff, collision-aligned safety walls, catch
  fences, grounded grandstands and spectators, pit buildings, trees, palms,
  rocks, sandy terrain, ocean, and start gantries
- Suzuka's only centerline crossover is an open bridge with audited vertical
  clearance; the other real circuits contain no false self-intersections
- Meter-scaled GLB car and driver meshes with named `idle`, `accelerate`,
  `brake`, `turn_left`, and `turn_right` animation clips
- Runtime dust, brake lights, ground shadows, soft particles, body pitch/roll,
  and airborne presentation; the procedural track, car, and driver renderers
  remain as fallbacks when an authored GLB cannot be loaded
- One fixed 80-degree broadcast T-cam mounted above and just behind the cockpit,
  with restrained road vibration and no chase interpolation or camera switching
- Momentum-preserving formula handling with a combined tire-grip budget,
  speed-sensitive steering, aerodynamic downforce, brake/load transfer,
  trail braking, high-speed understeer, stable braking zones, powered corner
  exits, real gravity, grounded low-speed tire contact, landing compression,
  visible-wall collision response, and stuck recovery
- Eight-speed manual sequential transmission with paddle edge detection,
  downshift over-rev protection, shift torque interruption, gear-dependent
  engine braking, rolling resistance, and speed-squared aerodynamic drag
- Formula-aware AI that scans upcoming curvature, brakes before turn-in,
  coasts at the tire limit, accelerates from the apex, and does not drift
- Procedural engine, drivetrain, road, wind, tire-scrub, and landing audio
- Circuit-specific AI pace with deterministic braking, track-limit, and
  progress-stability audits
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

Formula car exports are 2.02-2.04 m wide, 4.915 m long, and 1.03-1.12 m
high, with 3.17-3.20 m wheelbases and tire contact at Z=0. Seated driver exports stay near 0.64 m wide,
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
make capture-suzuka-tour-3d
make capture-map-gallery-3d
make capture-time-trial-3d
make spa-perf-audit-3d
make collision-audit-3d
make perf-audit-3d
make agent-play-audit-3d
./build/game/harbor_karts --smoke-render --dev-keyboard
SDL_VIDEODRIVER=offscreen ./build/game/harbor_karts_3d --asset-audit
```

Model-driven playtesting is available through the persistent JSONL harness:

```sh
make agent-play-3d
```

It accepts menu and driving inputs, advances deterministic fixed simulation
frames, returns gameplay telemetry, and writes requested observations to
`build/agent_play_frames`. See [the agent play protocol](docs/agent_play_protocol.md)
for the command schema and recommended vision-agent loop.

`--self-test` runs a deterministic physics/AI smoke test without SDL.
`--audio-audit` runs nine hardware-independent DSP checks for engine load,
speed, tire scrub, landing response, output bounds, and determinism.
`--vehicle-audit` runs deterministic unit checks for momentum, steering,
manual shifting, engine braking, drag, surfaces, jumping, landing, and fixed-step consistency
without opening a window. `--race-flow-audit` runs 20 checks for countdowns, checkpoints,
wrong-way state, finish ordering, infinite races, and discontinuity handling.
`--race-audit` runs a longer headless simulation and reports progress jumps,
pack balance, contacts, track-limit excursions, and lap pace.
`--capture-playtest` writes deterministic loading, selection, pause, result, and race frames to
`build/playtest_frames` so visual and camera changes can be inspected without a
working video device.
`--perf-audit` renders 420 worst-case section frames without sleeping and fails
if p95 frame time misses the 60fps budget.
The smoke render verifies SDL startup and framebuffer presentation.
`capture-playtest-3d` writes deterministic 3D frames to `build/playtest_frames`
for visual inspection.
`race-audit-3d` runs the 3D scripted player against live AI and validates lap
pace, pack pressure, contact rate, overtakes, and every car's progress stability.
`spa-audit-3d` verifies Spa Coast's lap length, sampled FIA elevation stations,
overall relief, mesh length, road width, two-kart passing room, and non-local
branch clearance without opening a window.
`track-catalog-audit-3d` verifies lap length, travel direction, turn landmarks,
elevation relief, road width, handedness, self-intersections, and Suzuka bridge separation.
`--asset-audit` opens every production GLB through the C++ loader and requires
all four cars, six drivers, and five tracks to pass dimension and animation
contracts. `capture-map-gallery-3d` writes a selection-screen preview for every
circuit.
`time-trial-audit-3d` drives a complete solo Spa lap and verifies one-racer
flow, infinite laps, best-lap timing, parked opponents, and no results transition.
`capture-spa-tour-3d` and `capture-suzuka-tour-3d` write nine course views for
visual inspection, including Suzuka's runtime bridge approach and crossover.
`capture-time-trial-3d` writes the live and paused solo timing HUD states.
`collision-audit-3d` runs deterministic rear-end, head-on, and side-swipe
contact cases; it also proves that curbs and runoff remain driveable, contact
begins at the visible barrier, and the rendered tires stay on the road datum at
low speed. `handling-audit-3d` checks formula acceleration, a 305-330 km/h speed
envelope in both track unit systems, progressive stopping distances, natural
coast-down, quadratic aero loss, trail braking, fixed T-cam geometry, and
flat-versus-braked behavior through named Monza and Suzuka corners. The
[formula handling targets](docs/formula_handling_targets.md) map representative
qualifying speeds and gears for all five real-world-inspired circuits,
including a full-throttle eighth-gear regression for Suzuka's 130R.
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
- `src/track_layout.hpp`: Spa Coast centerline/elevation data
- `src/track_catalog.*`: Suzuka, Silverstone, Monza, and Interlagos geometry contracts
- `tools/build_assets.py`: manifest-driven Blender source/export/validation CLI
- `tools/blender/generators/`: production vehicle and driver generators and verifier
- `tools/blender/tracks/`: production circuit-world generator and verifier

## Third-Party Code

See `THIRD_PARTY_LICENSES.md` and `third_party/README.md`.
