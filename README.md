# Formula Forge

Formula Forge is an open-source, Linux-native arcade formula racing game built
in C++20. Race a six-car grid or chase lap times on five original,
real-world-inspired circuits with controller and steering-wheel input.

![Three Formula Forge cars racing](docs/images/formula_forge.png)

## Highlights

- Spa, Suzuka, Silverstone, Monza, and Interlagos-inspired circuits with
  authored elevation, track limits, runoff, barriers, scenery, and pit areas
- Five logo-free car liveries sharing one Blender-authored formula car and
  driver specification
- Race and Time Trial sessions with configurable race distances
- Eight-speed manual sequential transmission and momentum-preserving arcade
  handling with tire grip, downforce, drag, load transfer, and trail braking
- Six-car races against curvature-aware AI that uses racing lines, passing
  moves, safe following gaps, and modest player-pace adaptation
- Fixed broadcast T-cam, responsive HUD, procedural vehicle audio, and a full
  loading/menu/garage/race/results flow
- Deterministic audits for vehicle dynamics, race rules, collisions, assets,
  track geometry, performance, and AI pace on every circuit

## Build and run

Formula Forge currently targets Linux. You need a C++20 compiler, CMake 3.20+
and GNU Make, plus X11/EGL/OpenGL ES runtime libraries. SDL3 and raylib source
archives are pinned in `third_party/` and compiled automatically on the first
build.

```sh
make
make run
```

The executable is written to `build/game/formula_forge`. Run it from the
repository root so it can find `assets/`. The game starts fullscreen; use this
for a window while debugging:

```sh
./build/game/formula_forge --windowed
```

## Controls

Formula Forge is designed for gamepads and steering wheels. A DragonRise Wired
Wheel (`0079:189c`) is recognized automatically. Multiple SDL input devices are
merged, so a wheel and gamepad can stay connected together.

- Left stick, D-pad, or wheel rim: steer and navigate menus
- RT or accelerator pedal: accelerate
- LT, B/Circle, or brake pedal: brake; hold at low speed to reverse
- RB/right paddle and LB/left paddle: shift up and down
- A/Cross: confirm
- B/Circle: go back
- Start: pause
- Back/Select: resume or reset to the last checkpoint
- Start + Back/Select: quit

## Test and diagnostic tools

Run the full CTest suite:

```sh
make test
```

Useful focused checks include:

```sh
make smoke
make asset-audit
make race-audit
make handling-audit
make track-catalog-audit
make ai-pace-audit
make ai-pace-audit-spa
make ai-pace-audit-suzuka
make ai-pace-audit-silverstone
make ai-pace-audit-interlagos
```

The Monza AI audit is calibrated around a 75-second player lap. Each other
circuit has its own deterministic pace and track-limit contract.

For model-driven playtesting, `make agent-play` starts a persistent JSONL
harness that accepts menu/driving inputs, advances fixed simulation frames,
returns telemetry, and writes requested observations under `build/`. See the
[agent play protocol](docs/agent_play_protocol.md) for its command schema.

Additional capture and audit targets are listed by `make -qp` and in the
[Makefile](Makefile).

## Blender asset pipeline

Editable `.blend` sources, runtime `.glb` exports, previews, and metadata live
together under `assets/`. Python 3.11 and `bpy` 5.0.1 are pinned by `uv`:

```sh
uv sync --frozen
make assets-validate
```

To regenerate all production assets:

```sh
make assets
```

The pipeline uses meter-scale Blender scenes and verifies dimensions, required
nodes and materials, animations, mesh budgets, circuit geometry, and
clearances. Read [the asset pipeline guide](tools/README.md) and
[the track guide](tools/blender/tracks/README.md) before changing generated
assets.

## Repository layout

- `src/`: game, rendering, vehicle, race, audio, HUD, asset-loading, and track code
- `assets/`: fonts plus editable and runtime vehicle, driver, UI, and circuit assets
- `tools/blender/`: reproducible Blender generators and validators
- `scripts/`: pinned SDL3 and raylib bootstrap scripts
- `docs/`: engineering notes, demo material, and repository images
- `third_party/`: pinned source archives, patches, and license texts

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and
please run `make test` before submitting a change.

Formula Forge is MIT licensed. Third-party code and fonts retain their own
licenses; see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
