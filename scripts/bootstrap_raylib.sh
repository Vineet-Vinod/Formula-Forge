#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="$repo_root/third_party/_cache"
deps_dir="$repo_root/build/deps"
src_dir="$deps_dir/src"
build_dir="$deps_dir/raylib-build"
install_dir="$deps_dir/raylib-install"
sdl_install="$deps_dir/install"

raylib_version="6.0"
raylib_tar="$cache_dir/raylib-${raylib_version}.tar.gz"
raylib_sha="2b3ee1e2120c7a0796b33062c7e9a694dd8a8caa56a96319ac8c8ecf54a90d0b"

jobs="${JOBS:-$(nproc 2>/dev/null || echo 2)}"

require_file() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        echo "Missing vendored dependency: $path" >&2
        exit 1
    fi
}

verify_sha() {
    local expected="$1"
    local path="$2"
    printf '%s  %s\n' "$expected" "$path" | sha256sum -c -
}

require_file "$raylib_tar"
require_file "$sdl_install/lib/libSDL3.a"
require_file "$sdl_install/include/SDL3/SDL.h"
verify_sha "$raylib_sha" "$raylib_tar"

mkdir -p "$src_dir" "$build_dir/obj" "$install_dir/include" "$install_dir/lib"

if [[ ! -d "$src_dir/raylib-${raylib_version}" ]]; then
    tar -xzf "$raylib_tar" -C "$src_dir"
fi

raylib_src="$src_dir/raylib-${raylib_version}/src"
obj_dir="$build_dir/obj"
rm -rf "$obj_dir"
mkdir -p "$obj_dir"

sources=(rcore rmodels rshapes rtext rtextures)
cflags=(
    -std=c99
    -O3
    -DNDEBUG
    -DPLATFORM_DESKTOP_SDL
    -DGRAPHICS_API_OPENGL_ES2
    -DUSING_SDL3_PROJECT
    -DSUPPORT_MODULE_RAUDIO=0
    -DSUPPORT_SCREEN_CAPTURE=0
    -DSUPPORT_GIF_RECORDING=0
    -I"$raylib_src"
    -I"$sdl_install/include"
)

# Build from inside raylib/src because the software renderer uses __FILE__ for
# an internal include. Compiling through a long relative path breaks that include.
printf '%s\n' "${sources[@]}" | xargs -P "$jobs" -I{} \
    bash -c 'cd "$0" && cc "${@:2}" -c "{}.c" -o "$1/{}.o"' \
    "$raylib_src" "$obj_dir" "${cflags[@]}"

ar rcs "$install_dir/lib/libraylib.a" "$obj_dir"/*.o
cp "$raylib_src/raylib.h" "$raylib_src/raymath.h" "$raylib_src/rlgl.h" "$raylib_src/rcamera.h" "$install_dir/include/"

mkdir -p "$install_dir/share/licenses/raylib"
cp "$src_dir/raylib-${raylib_version}/LICENSE" "$install_dir/share/licenses/raylib/LICENSE"

echo "raylib ${raylib_version} is ready in $install_dir"
