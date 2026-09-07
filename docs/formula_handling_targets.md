# Formula handling targets

This document explains where handling targets live, how the game uses them,
and how to validate an authorized handling change. Follow [AGENTS.md](../AGENTS.md)
for scope; map maintenance follows [map.md](../map.md).

## Targets and tuning

The `k*FormulaTargets` arrays and `formulaCornerTargets()` in
[game.cpp](../src/game.cpp) define each circuit's corner targets. Each entry has
an identifying name, lap fraction, speed in km/h, gear and full-throttle flag.
Use those tables for current values. Keep numerical targets in the code so
this document does not become a second, conflicting copy.

These targets guide corner-grip calibration and handling audits. A target
speed is a calibration input, not a guaranteed speed through a corner.
The full-throttle flag identifies the target's intended driving condition;
it does not apply player input.

| Implementation | Responsibility |
| --- | --- |
| `tuningForSpec()` and `selectedTrackTuning()` in [game.cpp](../src/game.cpp) | Vehicle configuration, track-unit conversion, grip, downforce and transmission settings |
| `formulaCornerGripScale()` in [game.cpp](../src/game.cpp) | Local grip calibration using track curvature, target speed and live car speed |
| `drivingSurfaceFor()` in [game.cpp](../src/game.cpp) | Transition from calibrated road grip to kerb and runoff response |
| [arcade_vehicle.cpp](../src/arcade_vehicle.cpp) and [arcade_vehicle.hpp](../src/arcade_vehicle.hpp) | Vehicle integration, combined grip, steering response and transmission behaviour |

The corner calibration blends in around each target's lap fraction and as
speed approaches the target. Its measured maximum depends on the circuit
geometry and tuning. Read current grip measurements and calibration maxima
from the audit output instead of maintaining snapshots here.

## Reference material

The original target selection recorded these sources for five circuits:

- Suzuka: [2024 Verstappen pole lap](https://www.formula1.com/en/video/onboard-max-verstappens-2024-pirelli-pole-position-award-lap-at-the-japanese-grand-prix.1795576994761470754) and [Mercedes 2024 circuit guide](https://www.mercedesamgf1.com/races/japanese-grand-prix-2024).
- Spa: [F1's 2022 technical analysis](https://www.formula1.com/en/latest/article/tech-tuesday-how-red-bull-engineered-the-rb18-to-dominate-at-spa.3QCa91D0rv2PNbjXx802Wz).
- Silverstone: [2023 Verstappen pole lap](https://www.formula1.com/en/latest/article/watch-ride-onboard-with-verstappen-at-silverstone-as-he-takes-his-fifth.1IHzD4zxRuZz1pKe6ndM0X).
- Monza: [2024 Norris pole lap](https://www.formula1.com/en/video/onboard-lando-norris-2024-pirelli-pole-position-award-lap-at-the-italian-grand-prix.1808919989852209304/).
- Interlagos: [2023 qualifying results](https://www.formula1.com/en/results/2023/races/1224/brazil/qualifying).

These are historical context links. A results page alone does not establish
corner speed or gear, and this list does not document every current circuit's
targets. When revising a target, record the lap/session, corner location and
supporting observation or telemetry. State any uncertainty in the measurement.

## Validation

`runHandlingAudit()` in [game.cpp](../src/game.cpp) exercises acceleration,
braking, coasting, corner control and named-corner driving scenarios. Its
per-circuit loops check target gears through the automatic transmission,
lateral response at target speeds, and grip calibration around target stations.
The audit output reports its check counts, measurements and failures.

Run from the repository root:

```sh
make
SDL_VIDEODRIVER=offscreen ctest --test-dir build/game -R '^handling_dynamics_audit$' --output-on-failure
```

For the full diagnostic output, run
`SDL_VIDEODRIVER=offscreen build/game/formula_forge --handling-audit`.
Keep captured logs under `build/` and identify the tested revision. This
document describes the checks; their result must come from the tested build.

After a route revision, check that target lap fractions still identify the
intended corners before interpreting a handling failure. Correct misplaced
target stations or map geometry within the authorized scope. Changes to grip,
speed, gear shifts or audit thresholds require handling-specific authorization.
