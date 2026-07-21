# Third-Party Dependencies

The game vendors only the source release archives needed to produce the Linux
executable. Generated dependency and game build trees stay under `build/`.

## Vendored Archives

- `SDL3-3.4.10.tar.gz`
  - Source: `https://github.com/libsdl-org/SDL/releases/download/release-3.4.10/SDL3-3.4.10.tar.gz`
  - SHA-256: `12b34280415ec8418c864408b93d008a20a6530687ee613d60bfbd20411f2785`
  - Purpose: windowing, fullscreen, controller/gamepad input, timing.
- `libXext-1.3.6.tar.xz`
  - Source: `https://www.x.org/releases/individual/lib/libXext-1.3.6.tar.xz`
  - SHA-256: `edb59fa23994e405fdc5b400afdf5820ae6160b94f35e3dc3da4457a16e89753`
  - Purpose: headers needed to build SDL's X11 backend without a system
    development package.
- `raylib-6.0.tar.gz`
  - Source: `https://github.com/raysan5/raylib/archive/refs/tags/6.0.tar.gz`
  - SHA-256: `2b3ee1e2120c7a0796b33062c7e9a694dd8a8caa56a96319ac8c8ecf54a90d0b`
  - Purpose: 3D rendering, camera, geometry helpers, and gamepad abstraction.

## Rebuilding

```sh
scripts/bootstrap_deps.sh
scripts/bootstrap_raylib.sh
```

The SDL script verifies the SDL/libXext archive checksums, extracts them into
`build/deps/src`, builds static SDL3, and installs it into `build/deps/install`.
The raylib script verifies the raylib archive checksum, builds a static raylib
library against that SDL3 install, and installs it into
`build/deps/raylib-install`.

## Local Patches

- `patches/SDL3-3.4.10-x11-missing-extension.patch`
  - Removes SDL's dynamic lookup for the unused `XMissingExtension` Xlib symbol.
  - Reason: some `libX11.so.6` installations do not export that symbol, which
    can make SDL's dynamic X11 backend reject Xwayland before connecting to
    `DISPLAY`.

## Local Build Flags

- `NO_SHARED_MEMORY`
  - Disables SDL's optional X11 MIT-SHM framebuffer path.
  - Reason: this build intentionally avoids a hard Xext dependency; without
    XShm symbols loaded, SDL's X11 framebuffer path can crash while probing MIT-SHM.
- `SDL_OPENGLES=ON`
  - Enables SDL's X11/EGL OpenGL ES window path.
  - Reason: this laptop has EGL/GLES runtime libraries but not GLX development
    headers.
- `GRAPHICS_API_OPENGL_ES2`
  - Builds raylib's 3D API on OpenGL ES 2 through SDL3.
  - Reason: this gives hardware acceleration without relying on missing system
    GLX development headers.

No proprietary Beach Buggy Racing assets, names, tracks, character art, or
game data are vendored here.
