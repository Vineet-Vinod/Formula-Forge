# Third-Party Licenses

This project vendors source archives for Linux platform support and the font
documented below. The track, car roster, and handling code are original to this
repository.

## Noto Sans Display Bold

- Asset: `assets/fonts/NotoSansDisplay-Bold.ttf`
- Upstream recorded by the package:
  <https://github.com/googlei18n/noto-fonts>
- Local provenance: copied without modification from
  `/usr/share/fonts/truetype/noto/NotoSansDisplay-Bold.ttf`, installed by the
  Debian `fonts-noto-core` package version `20201225-2`.
- Font metadata: family `Noto Sans Display`, style `Bold`, PostScript name
  `NotoSansDisplay-Bold`, font revision `2.003` (`fontversion` 131269).
- Copyright: 2010, 2012-2020 Google Inc.; 2015-2020 Google LLC.
- License: SIL Open Font License, Version 1.1.
- SHA-256:
  `1640ba8acb852d9e00406e166d1fc0cedd62a4c20342fd92f1f6dbc7baa61de2`
- Complete package copyright and OFL 1.1 text:
  `third_party/licenses/fonts-noto-core-copyright.txt`

The vendored TTF is the unmodified package file.

## Lato Heavy Italic

- Asset: `assets/fonts/Lato-HeavyItalic.ttf`
- Upstream: <http://www.latofonts.com>
- Local provenance: copied without modification from
  `/usr/share/fonts/truetype/lato/Lato-HeavyItalic.ttf`, installed by the
  Debian `fonts-lato` package.
- Copyright: 2010-2011, Łukasz Dziedzic.
- License: SIL Open Font License, Version 1.1.
- SHA-256:
  `4c9af8df580f1b7a2e3336d69b225a38364a636dc014d8fd9c2b72adea68dd2d`
- Complete package copyright and OFL 1.1 text:
  `third_party/licenses/fonts-lato-copyright.txt`

The vendored TTF is the unmodified package file and is used only by the
pre-race Formula Forge menus; the race HUD retains its existing face.

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
- Use: X11 extension headers needed to build SDL without a system development
  package.
- Full license text: `third_party/licenses/libXext-1.3.6-COPYING.txt`

The libXext distribution contains multiple permissive copyright notice blocks;
the full upstream `COPYING` file is included verbatim at the path above.

## raylib 6.0

- Source: <https://github.com/raysan5/raylib/archive/refs/tags/6.0.tar.gz>
- SHA-256: `2b3ee1e2120c7a0796b33062c7e9a694dd8a8caa56a96319ac8c8ecf54a90d0b`
- Use: 3D rendering, camera, geometry helpers, and gamepad abstraction for the
  game.
- Local build choice: compiled as a static library with the SDL3 platform
  backend, OpenGL ES 2 renderer, and audio disabled. This avoids requiring GLX
  development headers while retaining hardware EGL/GLES acceleration.
- Full license text: `third_party/licenses/raylib-6.0-LICENSE.txt`

raylib is distributed under the zlib/libpng license; the full upstream
`LICENSE` file is included verbatim at the path above.
