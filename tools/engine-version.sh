#!/usr/bin/env bash

check_engine_version() {
    local version_file="$1/Engine/Build/Build.version"
    local major minor patch
    if [[ ! -f "$version_file" ]]; then
        echo 'UE_ROOT must point to the engine installation containing Engine/Build/Build.version.' >&2
        return 1
    fi
    major="$(sed -nE 's/.*"MajorVersion":[[:space:]]*([0-9]+).*/\1/p' "$version_file")"
    minor="$(sed -nE 's/.*"MinorVersion":[[:space:]]*([0-9]+).*/\1/p' "$version_file")"
    patch="$(sed -nE 's/.*"PatchVersion":[[:space:]]*([0-9]+).*/\1/p' "$version_file")"
    if [[ "$major" != 5 || "$minor" != 8 || ! "$patch" =~ ^[0-9]+$ ]] || ((patch < 3)); then
        echo "Unreal 5.8.3 or a newer 5.8 patch is required; found $major.$minor.$patch." >&2
        return 1
    fi
}
