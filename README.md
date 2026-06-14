# Shark Harbor Karts

Shark Harbor Karts is an original Linux/C++ arcade kart racer aimed at a
bright tropical beach-buggy feel without copying proprietary Beach Buggy
Racing assets, names, tracks, or game data.

The primary build is now `harbor_karts_3d`: vendored SDL3 for Linux windowing
and controller input, plus vendored raylib on SDL/EGL/OpenGL ES 2 for a real 3D
camera, track, karts, props, particles, and HUD. The older SDL software
framebuffer build is still kept as `harbor_karts` for diagnostics and
comparison.

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

Gamepad is the intended input.

- Left stick / D-pad: steer, garage selection
- RT: accelerate
- LT: brake, reverse at low speed
- RB / R1: drift setup while steering
- A / Cross: confirm, race, resume
- B / Circle: back to garage from pause
- Start: pause or resume
- Back / Select: reset kart to racing line
- Start + Back / Select: quit

## Current Gameplay

- One original Shark Harbor course with beach, dock, market, cave, cliff, pier,
  and lagoon sections
- Infinite laps
- 8-car racing pack with AI opponents
- 8 maxed-out kart classes
- 10 cosmetic drivers
- No powerups and no character super powers
- Raylib 3D course with wide road mesh, shoulders, simple banking, tropical
  environment props, water/sand bands, and chunky 3D kart silhouettes
- Speed-reactive chase camera that pulls back at speed and looks toward the
  upcoming corner
- Drift handling on RB/R1 with locked drift direction, charge tiers, boost
  release, off-road drag, kart contacts, and wall speed scrub
- Fullscreen Linux build with controller/gamepad support

## Verification

```sh
make self-test
make race-audit
make capture-playtest
make perf-audit
make smoke-3d
make capture-playtest-3d
make handling-audit-3d
make race-audit-3d
./build/game/harbor_karts --smoke-render --dev-keyboard
```

`--self-test` runs a deterministic physics/AI smoke test without SDL.
`--race-audit` runs a longer headless simulation and reports progress jumps,
cave transitions, turn balance, no-brake corner speed, and off-road excursions.
`--capture-playtest` writes deterministic garage and race frames to
`build/playtest_frames` so visual and camera changes can be inspected without a
working video device.
`--perf-audit` renders 420 worst-case section frames without sleeping and fails
if p95 frame time misses the 60fps budget.
The smoke render verifies SDL startup and framebuffer presentation.
`capture-playtest-3d` writes deterministic 3D frames to `build/playtest_frames`
for visual inspection.
`race-audit-3d` runs the 3D scripted player against live AI and reports pack
pressure, overtakes, contacts, and progress stability.
`--diagnose-controller` prints both raylib and direct SDL controller readings,
which helps with USB receivers that expose a partial or unusual mapping.

## Source Layout

- `src/main.cpp`: process entry point only
- `src/main3d.cpp`: 3D process entry point only
- `src/core_math.hpp`: math, color, and geometry helpers
- `src/renderer.hpp`: low-overhead software renderer and bitmap text
- `src/harbor_karts.cpp`: SDL platform loop, renderer, simulation, controller input
- `src/harbor_karts_3d.cpp`: raylib 3D renderer, simulation, controller input,
  capture harness, and 3D race loop
- `src/harbor_karts_3d.hpp`: 3D entry-point declaration
- `src/track_layout.hpp`: Shark Harbor control-point layout data

## Third-Party Code

See `THIRD_PARTY_LICENSES.md` and `third_party/README.md`.
