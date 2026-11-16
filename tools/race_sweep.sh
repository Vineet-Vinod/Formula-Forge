#!/usr/bin/env bash
set -euo pipefail
make -j1 build/tests/discrete-race
output_root="${RACE_OUTPUT_ROOT:-build/discrete-race/final}"
for lines in 25 50 100 200; do
    build/tests/discrete-race --lines "$lines" --seconds 180 --out "$output_root/lines-$lines"
done
build/tests/discrete-race --seconds 180 --fixed --out "$output_root/fixed"
build/tests/discrete-race --seconds 180 --seed 19 --out "$output_root/seed-19"
build/tests/discrete-race --seconds 180 --seed 41 --out "$output_root/seed-41"
for lines in 25 50 100 200 256; do
    build/tests/discrete-race --lines "$lines" --cars 24 --seconds 30 --synchronized --out "$output_root/stress-$lines"
done
