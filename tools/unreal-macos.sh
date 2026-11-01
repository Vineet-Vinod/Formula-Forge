#!/usr/bin/env bash
set -euo pipefail
ulimit -c 0

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-help}"
case "$action" in
    help|-h|--help) echo 'Usage: tools/unreal.sh build|package|run [GAME_ARGS]'; exit 0 ;;
    build|package|run) ;;
    *) echo "Operation $action is only available in the Linux developer tools." >&2; exit 2 ;;
esac
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'This script requires macOS. Use tools/unreal.sh for Linux.' >&2
    exit 1
fi

engine_root="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
project="$repo_root/FormulaForge.uproject"
local_root="$repo_root/build/unreal"
if [[ "$action" != run ]]; then
    source "$repo_root/tools/engine-version.sh"
    check_engine_version "$engine_root"
    if ! command -v xcodebuild >/dev/null; then
        echo 'Install full Xcode and select it with xcode-select. See README.md.' >&2
        exit 1
    fi
fi
mkdir -p "$local_root"/{home,logs,tmp,ddc,shaders,dotnet,nuget}
if ! mkdir "$local_root/operation.lockdir" 2>/dev/null; then
    echo "Another operation is active. If a previous run was killed, remove $local_root/operation.lockdir after confirming it has stopped." >&2
    exit 1
fi
trap 'rmdir "$local_root/operation.lockdir"' EXIT
export TMPDIR="$local_root/tmp/"
export DOTNET_CLI_HOME="$local_root/dotnet"
export NUGET_PACKAGES="$local_root/nuget"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_PROCESSOR_COUNT=2
export UE_ENGINE_ROOT="$engine_root"
export FF_REPO_ROOT="$repo_root"
export uebp_LogFolder="$local_root/logs/uat"
export uebp_FinalLogFolder="$local_root/logs/uat"
common_args=("-UserDir=$local_root/home/" -SaveToUserDir -NoSplash -NoSound -NoAnalytics -notraceserver)

case "$action" in
    build)
        bash "$engine_root/Engine/Build/BatchFiles/Mac/Build.sh" FormulaForgeEditor Mac Development "$project" -MaxParallelActions=1 -NoUBA "-Log=$local_root/logs/build.log"
        ;;
    package)
        bash "$engine_root/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun "-project=$project" \
            -noP4 -platform=Mac -clientconfig=Development -build -cook -stage -pak -iostore \
            -compressed -unattended -utf8output -nocompileuat -nodebuginfo \
            "-stagingdirectory=$local_root/package" '-ubtargs=-MaxParallelActions=1 -NoUBA' \
            "-AdditionalCookerOptions=-partialgc -notraceserver -NoCrashDialog -NoAnalytics -DDC=InstalledNoZenLocalFallback -NoSharedDDC -LocalDataCachePath=\"$local_root/ddc\" -ShaderWorkingDir=\"$local_root/shaders\" -abslog=\"$local_root/logs/cook.log\""
        if grep -Eq 'Failed to compile Material|ShaderCompileWorker.*crash|Fatal error:' "$local_root/logs/cook.log"; then
            echo 'Cook has shader errors.' >&2
            exit 1
        fi
        ;;
    run)
        game="$local_root/package/Mac/FormulaForge.app/Contents/MacOS/FormulaForge"
        if [[ ! -x "$game" ]]; then
            echo 'Run make package first.' >&2
            exit 1
        fi
        cd "$(dirname "$game")"
        "$game" "${common_args[@]}" "-abslog=$local_root/logs/game.log" "${@:2}"
        ;;
esac
