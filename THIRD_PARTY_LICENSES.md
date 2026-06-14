# Third-Party Licenses

This project vendors source archives for Linux platform support only. The game
assets, track, car roster, and handling code are original to this repository.

## SDL 3.4.10

- Source: <https://github.com/libsdl-org/SDL/releases/download/release-3.4.10/SDL3-3.4.10.tar.gz>
- SHA-256: `12b34280415ec8418c864408b93d008a20a6530687ee613d60bfbd20411f2785`
- Use: windowing, fullscreen display, controller/gamepad input, timing.
- Local modification: `third_party/patches/SDL3-3.4.10-x11-missing-extension.patch`
- Full license text: `third_party/licenses/SDL3-3.4.10-LICENSE.txt`

```text
Copyright (C) 1997-2026 Sam Lantinga <slouken@libsdl.org>

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
```

## libXext 1.3.6

- Source: <https://www.x.org/releases/individual/lib/libXext-1.3.6.tar.xz>
- SHA-256: `edb59fa23994e405fdc5b400afdf5820ae6160b94f35e3dc3da4457a16e89753`
- Use: X11 extension headers needed while building SDL on this laptop.
- Full license text: `third_party/licenses/libXext-1.3.6-COPYING.txt`

The libXext distribution contains multiple permissive copyright notice blocks;
the full upstream `COPYING` file is included verbatim at the path above.

## raylib 6.0

- Source: <https://github.com/raysan5/raylib/archive/refs/tags/6.0.tar.gz>
- SHA-256: `2b3ee1e2120c7a0796b33062c7e9a694dd8a8caa56a96319ac8c8ecf54a90d0b`
- Use: 3D rendering, camera, geometry helpers, and gamepad abstraction for the
  new playable 3D build.
- Local build choice: compiled as a static library with the SDL3 platform
  backend, OpenGL ES 2 renderer, and audio disabled. This avoids relying on
  missing system GLX development headers while still using hardware EGL/GLES
  acceleration on the target laptop.
- Full license text: `third_party/licenses/raylib-6.0-LICENSE.txt`

raylib is distributed under the zlib/libpng license; the full upstream
`LICENSE` file is included verbatim at the path above.
