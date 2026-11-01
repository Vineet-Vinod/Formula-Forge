#!/usr/bin/env bash
set -euo pipefail
ulimit -c 0

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(uname -s)" in
    Darwin) exec bash "$repo_root/tools/unreal-macos.sh" "$@" ;;
    Linux) ;;
    *) echo 'On Windows, use tools/unreal.ps1. See README.md.' >&2; exit 1 ;;
esac
case "${1:-help}" in
    help|-h|--help)
        echo 'Usage: tools/unreal.sh build|game-build|python SCRIPT|package|run [ARGS]|check|session-check'
        exit 0 ;;
    build|game-build|python|package|run|check|session-check) ;;
    *) echo "Unknown operation: $1" >&2; exit 2 ;;
esac
original_home="$HOME"
engine_root="${UE_ROOT:-$(dirname "$repo_root")/Unreal}"
project="$repo_root/FormulaForge.uproject"
local_root="$repo_root/build/unreal"
minimum_free_bytes=$((10 * 1024 * 1024 * 1024))
minimum_job_bytes=1000000000
available_bytes="$(df -B1 --output=avail "$repo_root" | tail -1 | tr -d ' ')"
if ((available_bytes < minimum_free_bytes)); then
    echo "Unreal operation refused: less than 10 GiB free." >&2
    exit 1
fi
if [[ "${1:-}" != run && "${1:-}" != check && "${1:-}" != session-check && ! -x "$engine_root/Engine/Binaries/Linux/UnrealEditor" ]]; then
    echo "Set UE_ROOT to an extracted Unreal Linux installed build." >&2
    exit 1
fi
if [[ "$1" == build || "$1" == game-build || "$1" == python || "$1" == package ]]; then
    source "$repo_root/tools/engine-version.sh"
    check_engine_version "$engine_root"
fi
if ! command -v bwrap >/dev/null; then
    echo "Bubblewrap is required to keep Unreal writes inside this project." >&2
    exit 1
fi
mkdir -p "$local_root"/{home,cache,config,data,state,tmp,logs,ddc,shaders,dotnet,nuget,engine-saved,engine-build/BuildCookRun}
exec 9>"$local_root/operation.lock"
if ! flock -n 9; then
    echo "Another Unreal operation is using this project." >&2
    exit 1
fi
export XDG_CACHE_HOME="$local_root/cache"
export XDG_CONFIG_HOME="$local_root/config"
export XDG_DATA_HOME="$local_root/data"
export XDG_STATE_HOME="$local_root/state"
export TMPDIR="$local_root/tmp"
export DOTNET_CLI_HOME="$local_root/dotnet"
export NUGET_PACKAGES="$local_root/nuget"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER=1
export DOTNET_PROCESSOR_COUNT=2
export DOTNET_GCHeapCount=1
export MSBUILDDISABLENODEREUSE=1
export UBA_ROOT="$local_root/uba"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export UE_USE_SYSTEM_DOTNET=0
export PYTHONDONTWRITEBYTECODE=1
export UE_PYTHONPATH="$repo_root/tools"
export SDL_GAMECONTROLLERCONFIG="${SDL_GAMECONTROLLERCONFIG:-}"
export XAUTHORITY="${XAUTHORITY:-$original_home/.Xauthority}"
common_args=("-UserDir=$local_root/home/" "-ShaderWorkingDir=$local_root/shaders/" -DDC=InstalledNoZenLocalFallback -NoSharedDDC "-LocalDataCachePath=$local_root/ddc" -SCCProvider=None -NoSplash -NoSound -NoCrashDialog -NoAnalytics -notraceserver -unattended)
guard_cpu_properties=()
case "${1:-help}" in
    check|game-build) guard_cpu_properties=(-p CPUQuota=100%) ;;
esac
export UE_ENGINE_ROOT="$engine_root"
export FF_REPO_ROOT="$repo_root"

machine_used_bytes() {
    awk '/^MemTotal:/ {total = $2} /^MemAvailable:/ {available = $2} END {printf "%.0f", (total - available) * 1024}' /proc/meminfo
}

stop_job() {
    systemctl --user kill --kill-whom=all --signal=KILL "$1" 2>/dev/null || true
    kill -KILL -- -"$2" 2>/dev/null || true
}

run_guarded() {
    local baseline_bytes job_limit unit memory_log
    baseline_bytes="$(machine_used_bytes)"
    job_limit=$((10500000000 - baseline_bytes - 1000000000))
    if ((job_limit > 4000000000)); then
        job_limit=4000000000
    fi
    if ((job_limit < minimum_job_bytes)); then
        echo "Unreal operation refused: insufficient memory below the 10.5 GB laptop limit." >&2
        return 1
    fi
    if ! systemd-run --user --scope --quiet --collect -p MemoryMax=268435456 -p MemorySwapMax=0 /bin/true; then
        echo "Unreal operation refused: kernel memory limits are unavailable." >&2
        return 1
    fi
    unit="unrealff-$$-$RANDOM.scope"
    memory_log="$local_root/logs/$unit.memory.csv"
    printf 'elapsed_seconds,machine_used_bytes,job_limit_bytes\n' > "$memory_log"
    echo "Memory guard: job capped at $job_limit bytes, no swap; stop at 10.0 GB laptop usage." >&2
    local engine_mounts=()
    local entry
    if [[ -d "$engine_root/Engine/Intermediate/Build" ]]; then
        engine_mounts+=(--bind "$local_root/engine-build" "$engine_root/Engine/Intermediate/Build")
        for entry in "$engine_root/Engine/Intermediate/Build/"*; do
            engine_mounts+=(--ro-bind "$entry" "$entry")
        done
    fi
    if [[ -d "$engine_root/Engine/Saved" ]]; then
        engine_mounts+=(--bind "$local_root/engine-saved" "$engine_root/Engine/Saved")
    fi
    setsid systemd-run --user --scope --quiet --collect --unit="$unit" \
        -p "MemoryMax=$job_limit" \
        -p MemorySwapMax=0 -p OOMPolicy=kill "${guard_cpu_properties[@]}" \
        bwrap --die-with-parent --unshare-pid --ro-bind / / --dev-bind /dev /dev --proc /proc \
        --bind "$repo_root" "$repo_root" --setenv HOME "$local_root/home" \
        "${engine_mounts[@]}" \
        --bind "$local_root/tmp" /tmp --bind "$local_root/tmp" /var/tmp \
        --ro-bind-try /tmp/.X11-unix /tmp/.X11-unix \
        -- "$@" &
    local child_pid=$!
    trap "stop_job '$unit' '$child_pid'" EXIT
    trap "stop_job '$unit' '$child_pid'; exit 130" INT TERM
    local started=$SECONDS next_disk_check=0 used_bytes machine_bytes
    while kill -0 "$child_pid" 2>/dev/null; do
        machine_bytes="$(machine_used_bytes)"
        printf '%s,%s,%s\n' "$((SECONDS - started))" "$machine_bytes" "$job_limit" >> "$memory_log"
        if ((machine_bytes >= 10000000000)); then
            echo "Unreal operation stopped before exceeding the 10.5 GB laptop memory limit." >&2
            stop_job "$unit" "$child_pid"
            wait "$child_pid" || true
            trap - INT TERM EXIT
            return 1
        fi
        if ((SECONDS >= next_disk_check)); then
            available_bytes="$(df -B1 --output=avail "$repo_root" | tail -1 | tr -d ' ')"
            used_bytes="$({ du -s -B1 "$local_root" "$repo_root/Content" || true; } | awk '{total += $1} END {printf "%.0f", total}')"
            next_disk_check=$((SECONDS + 5))
            if ((available_bytes < minimum_free_bytes || used_bytes > 35 * 1024 * 1024 * 1024)); then
                echo "Unreal operation stopped by disk guard: preserve 10 GiB free; experiment budget 35 GiB." >&2
                stop_job "$unit" "$child_pid"
                wait "$child_pid" || true
                trap - INT TERM EXIT
                return 1
            fi
        fi
        sleep 0.5
    done
    local status=0
    wait "$child_pid" || status=$?
    trap - INT TERM EXIT
    return "$status"
}

case "${1:-help}" in
 build|game-build)
  target=FormulaForgeEditor
  if [[ "$1" == game-build ]]; then target=FormulaForge; fi
  run_guarded bash "$engine_root/Engine/Build/BatchFiles/Linux/Build.sh" "$target" Linux Development "$project" -MaxParallelActions=1 -NoUBA -UBAStoreCapacityGb=2 -UBAMaxWorkers=1 -UBAHost=127.0.0.1 "-Log=$local_root/logs/build.log"
  ;;
 python)
  script="$(realpath "$2")"
  run_guarded env "UE-LocalDataCachePath=$local_root/ddc" UE-SharedDataCachePath=None "$engine_root/Engine/Binaries/Linux/UnrealEditor-Cmd" "$project" "${common_args[@]}" -run=pythonscript "-script=$script" -NullRHI -nosplash "-abslog=$local_root/logs/python.log" "${@:3}"
  ;;
 package)
  export uebp_EngineSavedFolder="$local_root/engine-saved/AutomationTool"
  export uebp_LogFolder="$local_root/logs/uat"
  export uebp_FinalLogFolder="$local_root/logs/uat"
  minimum_job_bytes=2000000000
  run_guarded env "UE-LocalDataCachePath=$local_root/ddc" UE-SharedDataCachePath=None bash "$engine_root/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun "-project=$project" -noP4 -platform=Linux -clientconfig=Development -build -cook -stage -pak -iostore -compressed -unattended -utf8output -nocompileuat -nodebuginfo "-stagingdirectory=$local_root/package" "-ubtargs=-MaxParallelActions=1 -NoUBA -UBAStoreCapacityGb=2 -UBAMaxWorkers=1 -UBAHost=127.0.0.1" "-AdditionalCookerOptions=-partialgc -notraceserver -NoCrashDialog -NoAnalytics -DDC=InstalledNoZenLocalFallback -NoSharedDDC -LocalDataCachePath=\"$local_root/ddc\" -ShaderWorkingDir=\"$local_root/shaders/\" -abslog=\"$local_root/logs/cook.log\" -NoLogTimes" "${@:2}"
  if grep -Eq 'Failed to compile Material|ShaderCompileWorker.*crash|Fatal error:' "$local_root/logs/cook.log"; then echo "Cook has shader errors" >&2; exit 1; fi
  ;;
 run|session-check)
  game="$local_root/package/Linux/FormulaForge/Binaries/Linux/FormulaForge"
  if [[ ! -x "$game" ]]; then echo "Run make package first." >&2; exit 1; fi
  if [[ "$1" == session-check ]]; then
    status=0
    : > "$local_root/logs/session-tests.log"
    run_guarded "$game" "${common_args[@]}" -SaveToUserDir -NullRHI \
      '-ExecCmds=Automation RunTests FormulaForge.Session.LapLimits' \
      '-TestExit=Automation Test Queue Empty' "-abslog=$local_root/logs/session-tests.log" || status=$?
    # Unix TestExit forces status 1; require both the test result and expected exit phrase.
    [[ $status -le 1 ]]
    grep -Fq 'Result={Success} Name={LapLimits}' "$local_root/logs/session-tests.log"
    grep -Fq 'TestExit: Automation Test Queue Empty' "$local_root/logs/session-tests.log"
  else
    run_guarded "$game" "${common_args[@]}" -SaveToUserDir -ResX=1600 -ResY=900 "-abslog=$local_root/logs/game.log" "${@:2}"
  fi
  ;;
 check)
  run_guarded make -j1 native-check
  ;;
 *) echo 'Usage: tools/unreal.sh build|game-build|python SCRIPT|package|run [ARGS]|check|session-check'; exit 2 ;;
esac
