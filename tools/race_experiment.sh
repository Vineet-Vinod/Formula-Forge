#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
mkdir -p build/discrete-race
exec 8>build/discrete-race/operation.lock
flock -n 8 || { echo 'Another racing experiment is running.' >&2; exit 1; }
baseline_file=build/discrete-race/storage-baseline.txt
if [[ ! -f "$baseline_file" ]]; then du -s -B1 . > "$baseline_file"; fi
baseline_bytes="$(awk '{print $1}' "$baseline_file")"
unit="formula-race-$$.scope"
log="build/discrete-race/resources-$$.csv"
printf 'elapsed_s,machine_used_bytes,additional_storage_bytes\n' > "$log"
# One scope includes compilers, solver, telemetry and all sweep children.
setsid systemd-run --user --scope --quiet --collect --unit="$unit" \
    -p MemoryMax=4000000000 -p MemorySwapMax=0 -p OOMPolicy=kill "$@" &
child_pid=$!
stop_job() {
    systemctl --user kill --kill-whom=all --signal=KILL "$unit" 2>/dev/null || true
    kill -KILL -- -"$child_pid" 2>/dev/null || true
}
trap 'stop_job' EXIT
trap 'exit 130' INT TERM
started=$SECONDS
while kill -0 "$child_pid" 2>/dev/null; do
    used="$(awk '/^MemTotal:/ {total=$2} /^MemAvailable:/ {available=$2} END {printf "%.0f", (total-available)*1024}' /proc/meminfo)"
    current="$(du -s -B1 . | awk '{print $1}')"
    growth=$((current - baseline_bytes))
    printf '%s,%s,%s\n' "$((SECONDS-started))" "$used" "$growth" >> "$log"
    if ((used >= 9800000000 || growth >= 4500000000)); then
        echo "Racing experiment stopped: memory=$used bytes, added storage=$growth bytes." >&2
        stop_job
        wait "$child_pid" || true
        exit 1
    fi
    sleep 0.5
done
status=0
wait "$child_pid" || status=$?
trap - EXIT
exit "$status"
