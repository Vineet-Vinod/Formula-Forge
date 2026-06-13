# Harbor Karts

Harbor Karts is an original Linux/C++ beach-harbor kart racer built for this
workspace. It uses X11 software rendering and the Linux joystick API directly,
so it has no SDL/raylib/GLFW dependency.

This project intentionally does not copy proprietary Beach Buggy Racing content.
It provides an adapted baseline: beach-harbor course, cosmetic racer roster,
eight maxed-out kart classes, no powerups, no character supers, infinite laps,
controller-first play, and arcade kart handling tuned for a familiar feel.

## Build

Requirements on a typical Linux desktop:

- `g++`
- `make`
- X11 runtime and development headers/libraries
- Linux joystick devices exposed as `/dev/input/js*`

```sh
make
```

The executable is:

```sh
./build/harbor_karts
```

## Controls

Gamepad required for normal play.

- Left stick or D-pad: steer / menu navigation
- Right trigger: accelerate
- Left trigger: brake or reverse
- A / Cross: confirm
- B / Circle: back
- Start: pause or resume
- Select / Back: reset car to the last safe racing line
- Start + Select / Back: quit

## Baseline Features

- 10 adapted cosmetic racers
- 8 maxed-out cars unlocked from the start
- Fullscreen X11 renderer
- Forward chase camera that starts close and pulls back at speed
- 3 original beach-harbor course layouts with tighter technical sections
- Infinite laps with live position, speed, and FPS display
- No powerups and no character supers
- Lightweight X11 software renderer targeting 60 FPS

## Development

Run a headless physics/input smoke test:

```sh
make self-test
```

There is also a development-only keyboard flag for machines without a gamepad:

```sh
./build/harbor_karts --dev-keyboard
```
