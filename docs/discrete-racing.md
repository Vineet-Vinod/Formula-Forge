# Discrete racing experiment

This opt-in experiment keeps 100 whole-lap trajectories and chooses which one to
join. It runs alongside the existing Time Trial code. Production driving still
uses the original vehicle simulation.

## Run it

On Linux, from the repository root:

```sh
make race-check
make race-run ARGS='--lines 100 --cars 12 --seconds 180 --seed 7'
make race-sweep
make race-report
make race-view ARGS='-FFCircuit=silverstone -FFRaceLines=100 -FFRaceCars=12'
```

`race-view` builds the editor module and launches the game in Unreal using the
source assets. It avoids recooking or duplicating the packaged game. C switches
between car zero's cockpit and an elevated view following the middle of the pack; pause and quit use the usual
controls. Restart the experiment by launching it again. R is disabled in this
mode. `-FFRaceSeconds=30` exits after 30 wall-clock seconds, including loading.

The native runner accepts `--circuit silverstone|monza|interlagos`, `--lines 4..256`,
`--cars 2..24`, `--samples 128..1024` divisible by 8, `--seed`, `--seconds 1..600`,
`--tolerance`, `--iterations`, `--range` and `--dropout`. `--fixed` holds the starting
line while retaining observation-based following. `--synchronized` deliberately
puts all decisions in the same frame. Normal decisions run at 5 Hz, staggered
across cars, while motion runs at 120 Hz.

Each run saves `trajectories.csv`, `race.csv` at 15 Hz and `summary.json` under
`build/discrete-race`. `--out` selects another directory. The sweep writes
`build/discrete-race/final`; set `RACE_OUTPUT_ROOT` to change that destination.
`make race-report RACE_OUTPUT=build/discrete-race/final/lines-100` makes a standalone
HTML replay with the sibling runs' summaries. It needs only Python's standard
library and opens directly in a browser.

The Linux experiment guard serializes work, caps native jobs at 4 GB without swap,
and stops before measured machine memory reaches 9.8 GB. The editor view can use
up to 5 GB when the measured machine budget permits it. It tracks cumulative
additional repository storage against the first experiment baseline and stops at
4.5 GB, leaving margin below the requested 5 GB. The baseline persists across
runs in `build/discrete-race/storage-baseline.txt`. Do not reset it during this
experiment. Resource logs are saved beside it. A failure to establish the systemd
memory limit stops the command. Guard checks run every half second; native count,
duration and buffer limits also bound allocations and telemetry.

## Model

A car's physical state is its current line, destination line, unwrapped track
station, speed and the start/length of an active switch. Station is shared by all
lines and measured along the reference centreline, not each line's arc length.
The path derivative converts physical speed into station progress. Speed and
switch progress are necessary to make a transition depend on the current state.

The generator optimizes a reference line for curvature, then uses deterministic
low-discrepancy biases and periodic preferences to create different corner and
straight choices. Narrow optimization corridors preserve these differences.
Every accepted pair differs by at least 0.30 m RMS across the sampled lap. This
does not imply 100 separate lanes at every corner. Cars share local sections.
Candidates more than 30% slower than the reference's original speed profile are
rejected. All profiles are then rebuilt conservatively for the experiment's
continuous paths and braking model.

Actions name destination line IDs. A quintic blend joins the two continuous paths
over at least 60 m and approximately two seconds at the current speed. It preserves
the starting position and heading and finishes on the destination. Switches cannot
be interrupted. A braking-reachability check can reject an action. Curvature,
downforce grip, conservative acceleration/braking and combined-grip usage limit
speed during execution. This is prescribed-path motion, not the production tire,
steering, suspension or contact simulation. Cubic path interpolation and the
1.8 m centre-to-edge generation margin approximate the road corridor; the runner
does not audit the rendered white-line triangles or barriers.

Each observer holds an independent categorical distribution over every opponent's
line, plus a station/speed estimate, station variance and observed lateral motion.
Sensors report noisy station, speed and lateral position within 160 m and no more
than 35 m behind. Default dropout is 12%. Opponent IDs are assumed known. There
is no occlusion model. Hidden line IDs, actions and transition phases are never
passed to the belief update. On missing observations, the estimate advances and
uncertainty grows. Line probabilities mix with a uniform switching prior and use
a lateral observation likelihood. Intent and transition uncertainty are therefore
approximations, not separately enumerated hidden states.

Offline value iteration operates on line × station states with nine sparse
macro-actions per state. Each edge spans eight station samples, estimates its
curvature-limited travel time and receives progress reward minus time and switch
costs. Time-dependent discount is `exp(-duration / 12 seconds)`. Iteration stops
at a maximum absolute Bellman update of 0.01 or fails at its iteration cap. This
convergence claim applies only to that approximate traffic-free graph.

Online planning ranks every target cheaply, then fully evaluates at most 16:
spatial alternatives from the graph, the current line and high-value targets.
Each gets a three-second rollout. Eight stratified samples of each nearby
opponent's categorical belief approximate collision risk. The terminal value
comes from the offline table. A separate belief-based following controller slows
for predicted merges. All observations/decisions use the same pre-motion fleet
snapshot.

This is a factored belief rollout with a value-iteration terminal value, similar
to QMDP. It is not an exact belief-space POMDP solution, a converged multi-agent
equilibrium, or a trained RL policy. It does not value future information or model
correlated opponent decisions. Offline edges also simplify speed and switch phase.
The three-second risk rollout has fixed depth, not a convergence criterion.

## Measurements

Measured on this laptop's Intel Core i7-1255U using GCC C++20 `-O2`, 512 samples,
seed 7, 180 simulated seconds, 12 cars. Native frame cost includes two motion
steps, observations and scheduled decisions. CSV writing and Unreal rendering
are excluded. Peak RSS is measured separately from the estimated persistent model
buffer size. Setup includes line generation, speed profiles and value iteration.

| Lines | p99 / max native frame, ms | Peak RSS, MiB | Clean passes / corners | Overlap episodes |
| ---: | ---: | ---: | ---: | ---: |
| 25 | 0.66 / 0.80 | 9.2 | 3 / 0 | 0 |
| 50 | 0.87 / 1.05 | 11.9 | 3 / 2 | 3 |
| 100 | 1.25 / 1.54 | 16.9 | 2 / 2 | 0 |
| 200 | 2.10 / 2.63 | 26.8 | 0 / 0 | 2 |

The 100-line solver converged in 38 iterations at residual 0.00956. Minimum
pairwise RMS separation was 0.3005 m; conservative profile laps ranged from
136.4 to 148.9 seconds. Setup took 2.1 seconds. The fixed-line baseline recorded one
clean corner pass and no overlaps.

Across 100-line seeds 7, 19 and 41, clean pass counts were 2, 3, 1.
Clean corner passes were 2, 2, 0; overlap episodes were 0, 1, 0.
These runs establish that overtaking occurs; they do not establish collision-free racing.

With 24 synchronized decisions, measured maximum native frame times were:

| Lines | Max frame, ms |
| ---: | ---: |
| 25 | 10.94 |
| 50 | 12.00 |
| 100 | 11.85 |
| 200 | 15.55 |
| 256 | 17.02 |

The 60-second Monza and Interlagos runs converged in 42 and 48 iterations.
Monza recorded two overlap episodes; Interlagos recorded none. These are reduced
model checks, not rendered-track or production vehicle lap audits.

The full scan before limiting rollouts reached about 62 ms with 100 lines and
24 synchronized cars. Bounding the expensive search to 16 targets is what keeps
that stress case practical. The number of modeled trajectories remains 100.

Passes require a change in unwrapped order with 5 m clearance. Clean passes exclude
pairings with a recorded overlap before the order change. A corner pass has a
heading change over the next 12 m greater than 0.035 radians. Overlaps use a
4.9 × 2.05 m rectangle in one car's heading frame; these are approximate contact
indicators, not a full oriented-body contact solver. There is no collision
response, so an overlap can pass through another car. Minimum centre distance
minus width is a different metric and does not establish body clearance.

The 100-line model is small enough for inference here. Racing quality remains
experimental: the planner creates clean corner passes but also overlaps, and
increasing the line count does not reliably improve racing. The next useful
change is a better merge/longitudinal opponent model or a chance-constrained
switch filter. More trajectories alone do not address those failures. Timing
results are observations under this load, not hard real-time guarantees or
end-to-end game FPS claims.
