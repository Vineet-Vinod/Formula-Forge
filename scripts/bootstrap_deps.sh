#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="$repo_root/third_party/_cache"
deps_dir="$repo_root/build/deps"
src_dir="$deps_dir/src"
install_dir="$deps_dir/install"

sdl_version="3.4.10"
xext_version="1.3.6"
sdl_tar="$cache_dir/SDL3-${sdl_version}.tar.gz"
xext_tar="$cache_dir/libXext-${xext_version}.tar.xz"
sdl_sha="12b34280415ec8418c864408b93d008a20a6530687ee613d60bfbd20411f2785"
xext_sha="edb59fa23994e405fdc5b400afdf5820ae6160b94f35e3dc3da4457a16e89753"

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

require_file "$sdl_tar"
require_file "$xext_tar"
verify_sha "$sdl_sha" "$sdl_tar"
verify_sha "$xext_sha" "$xext_tar"

mkdir -p "$src_dir" "$install_dir"

if [[ ! -d "$src_dir/SDL3-${sdl_version}" ]]; then
    tar -xzf "$sdl_tar" -C "$src_dir"
fi

if [[ ! -d "$src_dir/libXext-${xext_version}" ]]; then
    tar -xJf "$xext_tar" -C "$src_dir"
fi

sdl_src="$src_dir/SDL3-${sdl_version}"
sdl_x11sym="$sdl_src/src/video/x11/SDL_x11sym.h"
sdl_patch="$repo_root/third_party/patches/SDL3-${sdl_version}-x11-missing-extension.patch"

if grep -q 'SDL_X11_SYM(int,XMissingExtension' "$sdl_x11sym"; then
    patch -d "$sdl_src" -p1 < "$sdl_patch"
fi

xorg_include="$deps_dir/xorg-include"
mkdir -p "$xorg_include/X11/extensions"
cp "$src_dir/libXext-${xext_version}"/include/X11/extensions/*.h "$xorg_include/X11/extensions/"

# The repository path can contain spaces. SDL's CMake checks are most reliable
# when the injected Xorg include path is a space-free symlink.
tmp_xorg_include="/tmp/harbor-karts-xorg-include-$$"
rm -f "$tmp_xorg_include"
ln -s "$xorg_include" "$tmp_xorg_include"
trap 'rm -f "$tmp_xorg_include"' EXIT

cmake -S "$sdl_src" \
    -B "$deps_dir/sdl-build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$install_dir" \
    -DCMAKE_INCLUDE_PATH="$tmp_xorg_include" \
    -DCMAKE_C_FLAGS="-I$tmp_xorg_include -DNO_SHARED_MEMORY" \
    -DSDL_SHARED=OFF \
    -DSDL_STATIC=ON \
    -DSDL_TESTS=OFF \
    -DSDL_EXAMPLES=OFF \
    -DSDL_INSTALL_TESTS=OFF \
    -DSDL_WAYLAND=OFF \
    -DSDL_OPENGL=OFF \
    -DSDL_OPENGLES=OFF \
    -DSDL_VULKAN=OFF \
    -DSDL_CAMERA=OFF \
    -DSDL_ALSA=OFF \
    -DSDL_JACK=OFF \
    -DSDL_PIPEWIRE=OFF \
    -DSDL_PULSEAUDIO=OFF \
    -DSDL_LIBUDEV=OFF \
    -DSDL_X11=ON \
    -DSDL_X11_SHARED=ON \
    -DSDL_X11_XCURSOR=OFF \
    -DSDL_X11_XDBE=ON \
    -DSDL_X11_XFIXES=OFF \
    -DSDL_X11_XINPUT=OFF \
    -DSDL_X11_XRANDR=OFF \
    -DSDL_X11_XSCRNSAVER=OFF \
    -DSDL_X11_XSHAPE=OFF \
    -DSDL_X11_XSYNC=OFF \
    -DSDL_X11_XTEST=OFF

cmake --build "$deps_dir/sdl-build" --target SDL3-static -j "$jobs"

rm -rf "$install_dir"
mkdir -p "$install_dir/include" "$install_dir/lib" "$install_dir/share/licenses/SDL3"
cp "$deps_dir/sdl-build/libSDL3.a" "$install_dir/lib/"
cp -R "$sdl_src/include/SDL3" "$install_dir/include/"
cp "$deps_dir/sdl-build/include-revision/SDL3/SDL_revision.h" "$install_dir/include/SDL3/"
cp "$sdl_src/LICENSE.txt" "$install_dir/share/licenses/SDL3/LICENSE.txt"

echo "Dependencies are ready in $install_dir"
