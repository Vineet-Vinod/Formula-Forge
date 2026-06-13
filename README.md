# Shark Harbor Karts

Shark Harbor Karts is an original Linux/C++ arcade kart racer aimed at a
bright tropical beach-buggy feel without copying proprietary Beach Buggy
Racing assets, names, tracks, or game data.

The current build uses vendored SDL3 for fullscreen windowing and controller
input, then renders the game through a low-overhead software framebuffer. The
game starts in a controller-only garage where all 8 maxed cars and all cosmetic
drivers are available.

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
./build/game/harbor_karts
```

## Run

```sh
make run
```

The game opens fullscreen by default. For debugging:

```sh
./build/game/harbor_karts --windowed
./build/game/harbor_karts --dev-keyboard --windowed
```

## Controls

Gamepad is the intended input.

- Left stick / D-pad: steer, garage selection
- RT: accelerate
- LT: brake, reverse at low speed, drift setup while steering
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
- Speed-reactive camera that starts near hood view and pulls back at speed
- Drift handling with brake-and-steer initiation, lateral slip, speed retention,
  off-road drag, and barrier recovery
- Fullscreen SDL3 Linux build with controller/gamepad support

## Verification

```sh
make self-test
make race-audit
./build/game/harbor_karts --smoke-render --dev-keyboard
```

`--self-test` runs a deterministic physics/AI smoke test without SDL.
`--race-audit` runs a longer headless simulation and reports progress jumps,
cave transitions, turn balance, no-brake corner speed, and off-road excursions.
The smoke render verifies SDL startup and framebuffer presentation.

## Source Layout

- `src/main.cpp`: process entry point only
- `src/harbor_karts.cpp`: SDL platform loop, renderer, simulation, controller input
- `src/track_layout.hpp`: Shark Harbor control-point layout data

## Third-Party Code

See `THIRD_PARTY_LICENSES.md` and `third_party/README.md`.
