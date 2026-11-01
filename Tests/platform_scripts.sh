#!/usr/bin/env bash
set -euo pipefail

# Command-contract tests with fake engine executables; not native OS build tests.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/build"
fixture="$(mktemp -d "$repo_root/build/platform-scripts.XXXXXX")"
trap 'rm -rf "$fixture"' EXIT
clone="$fixture/Clone With Spaces"
engine="$fixture/Engine With Spaces"
mkdir -p "$clone/tools" "$engine/Engine/Build/BatchFiles/Mac" "$fixture/bin"
cp "$repo_root"/tools/{unreal.sh,unreal-macos.sh,unreal.ps1,engine-version.sh} "$clone/tools/"
cp "$repo_root/FormulaForge.uproject" "$clone/"
export UE_ROOT="$engine"
export FF_TEST_CAPTURE="$fixture/arguments.txt"
export FF_TEST_LOCAL_ROOT="$clone/build/unreal"
export FF_TEST_EXIT=0
export FF_TEST_SHADER_ERROR=0
export POWERSHELL_TELEMETRY_OPTOUT=1
export XDG_CACHE_HOME="$fixture/cache"
export XDG_CONFIG_HOME="$fixture/config"
export XDG_DATA_HOME="$fixture/data"
mkdir -p "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"
printf '{"MajorVersion":5,\n"MinorVersion":8,\n"PatchVersion":3}\n' > "$engine/Engine/Build/Build.version"
cat > "$fixture/tool" <<'TOOL'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$FF_TEST_CAPTURE"
mkdir -p "$FF_TEST_LOCAL_ROOT/logs"
: > "$FF_TEST_LOCAL_ROOT/logs/cook.log"
if [[ "$FF_TEST_SHADER_ERROR" == 1 ]]; then
    echo 'Failed to compile Material' | tee "$FF_TEST_LOCAL_ROOT/logs/cook.log"
fi
exit "$FF_TEST_EXIT"
TOOL
chmod +x "$fixture/tool"
for tool in Mac/Build.sh RunUAT.sh Build.bat RunUAT.bat; do
    cp "$fixture/tool" "$engine/Engine/Build/BatchFiles/$tool"
done
printf '#!/usr/bin/env bash\necho Darwin\n' > "$fixture/bin/uname"
printf '#!/usr/bin/env bash\nexit 0\n' > "$fixture/bin/xcodebuild"
chmod +x "$fixture/bin/"*
export PATH="$fixture/bin:$PATH"

bash "$clone/tools/unreal.sh" build
grep -Fxq -- "$clone/FormulaForge.uproject" "$FF_TEST_CAPTURE"
grep -Fxq -- Mac "$FF_TEST_CAPTURE"
bash "$clone/tools/unreal.sh" package
grep -Fxq -- "-project=$clone/FormulaForge.uproject" "$FF_TEST_CAPTURE"
grep -Fxq -- "-stagingdirectory=$clone/build/unreal/package" "$FF_TEST_CAPTURE"
grep -Fxq -- '-ubtargs=-MaxParallelActions=1 -NoUBA' "$FF_TEST_CAPTURE"
grep -Fq -- "-LocalDataCachePath=\"$clone/build/unreal/ddc\"" "$FF_TEST_CAPTURE"
if bash "$clone/tools/unreal.sh" run 2>/dev/null; then
    echo 'Missing Mac package incorrectly succeeded.' >&2; exit 1
fi
game="$clone/build/unreal/package/Mac/FormulaForge.app/Contents/MacOS/FormulaForge"
mkdir -p "$(dirname "$game")"
cp "$fixture/tool" "$game"
bash "$clone/tools/unreal.sh" run '-FFArgument=space in value'
grep -Fxq -- '-FFArgument=space in value' "$FF_TEST_CAPTURE"
export FF_TEST_EXIT=23
if bash "$clone/tools/unreal.sh" package; then
    echo 'Mac build failure incorrectly succeeded.' >&2; exit 1
fi
test ! -d "$clone/build/unreal/operation.lockdir"
export FF_TEST_EXIT=0 FF_TEST_SHADER_ERROR=1
if bash "$clone/tools/unreal.sh" package; then
    echo 'Mac shader failure incorrectly succeeded.' >&2; exit 1
fi
export FF_TEST_SHADER_ERROR=0
mkdir "$clone/build/unreal/operation.lockdir"
if bash "$clone/tools/unreal.sh" build 2>/dev/null; then
    echo 'Mac build bypassed the operation lock.' >&2; exit 1
fi
rmdir "$clone/build/unreal/operation.lockdir"
echo 'macOS command contracts: paths with spaces, package/run routing, failure propagation and lock: PASS'

if [[ -n "${PWSH:-}" ]]; then
    export OS=Windows_NT
    "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" build
    grep -Fxq -- "$clone/FormulaForge.uproject" "$FF_TEST_CAPTURE"
    grep -Fxq -- Win64 "$FF_TEST_CAPTURE"
    "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" package
    grep -Fxq -- "-project=$clone/FormulaForge.uproject" "$FF_TEST_CAPTURE"
    grep -Fxq -- '-platform=Win64' "$FF_TEST_CAPTURE"
    grep -Fxq -- '-ubtargs=-MaxParallelActions=1 -NoUBA' "$FF_TEST_CAPTURE"
    if "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" run 2>/dev/null; then
        echo 'Missing Windows package incorrectly succeeded.' >&2; exit 1
    fi
    game="$clone/build/unreal/package/Windows/FormulaForge/Binaries/Win64/FormulaForge.exe"
    mkdir -p "$(dirname "$game")"
    cp "$fixture/tool" "$game"
    "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" run -GameArgs '-FFArgument=space in value'
    grep -Fxq -- '-FFArgument=space in value' "$FF_TEST_CAPTURE"
    export FF_TEST_EXIT=23
    if "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" package 2>/dev/null; then
        echo 'Windows build failure incorrectly succeeded.' >&2; exit 1
    fi
    export FF_TEST_EXIT=0 FF_TEST_SHADER_ERROR=1
    if "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" package 2>/dev/null; then
        echo 'Windows shader failure incorrectly succeeded.' >&2; exit 1
    fi
    export FF_TEST_SHADER_ERROR=0
    "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" package
    echo 'Windows command contracts under PowerShell: paths with spaces, package/run routing, failure propagation and lock release: PASS'
else
    echo 'Windows command contracts: SKIPPED; set PWSH to a PowerShell executable.'
fi

source "$clone/tools/engine-version.sh"
for version in '5 8 2' '5 7 9' '5 9 0' '6 0 0'; do
    read -r major minor patch <<< "$version"
    printf '{"MajorVersion":%s,\n"MinorVersion":%s,\n"PatchVersion":%s}\n' "$major" "$minor" "$patch" > "$engine/Engine/Build/Build.version"
    if check_engine_version "$engine" 2>/dev/null; then
        echo "Unsupported engine $version accepted." >&2; exit 1
    fi
    if [[ -n "${PWSH:-}" ]] && "$PWSH" -NoProfile -File "$clone/tools/unreal.ps1" build 2>/dev/null; then
        echo "PowerShell accepted unsupported engine $version." >&2; exit 1
    fi
done
printf '{"MajorVersion":5,\n"MinorVersion":8,\n"PatchVersion":4}\n' > "$engine/Engine/Build/Build.version"
check_engine_version "$engine"
echo 'Engine version checks: supported patches and incompatible versions: PASS'
