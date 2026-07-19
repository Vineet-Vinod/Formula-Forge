# Agent Play Protocol

`harbor_karts_3d --agent-play` exposes the production game as a persistent
JSONL process. It is intended for a vision-capable model, evaluation agent, or
other automation client. The session uses the same menus, fixed-step physics,
AI, race flow, renderer, and collision code as interactive play.

Build and launch it from the repository root:

```sh
cmake --build build/game --parallel
./build/game/harbor_karts_3d --agent-play
```

The process writes one JSON object per line and then waits for one JSON command
per line on standard input. Keep the process alive across the full play session.
The initial `ready` response contains protocol version `3`, the fixed timestep,
the frame directory, and the initial state.

## Commands

```json
{"cmd":"state","id":1}
{"cmd":"step","id":2,"frames":120,"input":{"throttle":1.0,"steer":-0.2}}
{"cmd":"step","id":3,"frames":1,"input":{"shift_up":true}}
{"cmd":"step","id":4,"frames":1,"input":{"confirm":true}}
{"cmd":"frame","id":5,"name":"turn_entry"}
{"cmd":"reset","id":6}
{"cmd":"help","id":7}
{"cmd":"quit","id":8}
```

`step` accepts between 1 and 2400 simulation frames. Analog `steer`,
`throttle`, and `brake` inputs remain held for the whole command. Digital inputs
fire only on its first frame:

| Input | Range | Meaning |
| --- | --- | --- |
| `steer` | -1 to 1 | Left to right steering |
| `throttle` | 0 to 1 | Accelerator |
| `brake` | 0 to 1 | Brake |
| `confirm` | boolean | Advance/select in menus |
| `cancel` | boolean | Cancel/back or pause-menu back |
| `pause` | boolean | Pause/resume |
| `recover` | boolean | Reset to track in a race; back in menus |
| `left`, `right`, `up`, `down` | boolean | Menu navigation |
| `page_left`, `page_right` | boolean | Alternate menu navigation |
| `shift_up` | boolean | Request one sequential upshift |
| `shift_down` | boolean | Request one sequential downshift |

Add `"render":true` and an optional `"name":"basename"` to a `step`
command to receive a rendered `frame_path` in the same response. `frame` renders
without advancing simulation. Frame names are sanitized and all PNGs stay under
`build/agent_play_frames`.

## Telemetry

Every successful `state`, `step`, `frame`, and `reset` response includes:

- Current screen, garage selection stage, and selected session/driver/car/map/laps.
- Race phase, countdown, race time, lap progress, position, and wrong-way state.
- Speed, position, heading, yaw, slip, steering, engine/brake load, and elevation.
- Transmission gear, engine RPM, normalized RPM, remaining shift-cut time, and
  whether the latest downshift was rejected to prevent an over-rev.
- Signed clearances to the road edge and physical barrier, plus road/contact/grounded flags.
- Separate `barrier_contact` and `vehicle_contact` flags, the last `contact_impulse`,
  and a `contact_cause` of `none`, `barrier`, or `vehicle`.
- Relative progress, lane, and speed for cars within 150 meters.

`road_edge_clearance_m` may be negative while the car is still in driveable
runoff. `barrier_clearance_m` reaches zero at the physical collision boundary.
Use the rendered frame to evaluate the visible scene and telemetry to make
precise control decisions.

Protocol v3 transmission telemetry is reported in the `car` object as `gear`,
`engine_rpm`, `rpm_normalized`, `shift_remaining_s`, and `shift_rejected`.
`shift_rejected` remains true only for the short rejection reporting window; a
client should sample it immediately after a downshift request.

Contact telemetry remains active for the short collision response window, so a
multi-frame `step` can still report an impact that happened near the end of the
command. `contact_impulse` is the resolved world-space impulse magnitude and is
zero when no impact is active.

## Agent Loop

For a low-cost vision model, a useful cadence is:

1. Navigate menus with single-frame digital commands.
2. Request a frame after entering the race and after each substantial decision.
3. Drive in 6 to 30 frame bursts near corners and 30 to 120 frame bursts on straights.
4. Use shorter bursts as barrier clearance falls or steering demand rises.
5. Record qualitative feedback with the associated frame number, screenshot, speed, and track progress.

Send `{"cmd":"help"}` to retrieve the machine-readable command contract from
the running process. Malformed commands return `ok:false` without ending the
session.
