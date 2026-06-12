# Harbor Karts

Harbor Karts is an original Linux/C++ beach-harbor kart racer built for this
workspace. It uses X11 software rendering and the Linux joystick API directly,
so it has no SDL/raylib/GLFW dependency.

This project intentionally does not copy proprietary Beach Buggy Racing content.
It provides an adapted baseline: beach-harbor course, cosmetic racer roster,
eight maxed-out kart classes, no powerups, no character supers, infinite laps,
controller-first play, and arcade kart handling tuned for a familiar feel.

## Build

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
- A / Cross / right trigger: accelerate / confirm
- B / Circle / left trigger: brake or reverse / back
- Start: pause or resume
- Select / Back: reset car to the last safe racing line

## Development

Run a headless physics/input smoke test:

```sh
make self-test
```
