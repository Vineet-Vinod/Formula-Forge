# Additional circuit validation — 2026-11-12

The 18 additional circuits were rebuilt and packaged from `6a970d40`. At this checkpoint, Luna High records 12 visual passes, 0 holds and 6 pending reviews. The [validation record](additional_circuits_validation.json) pins payloads, per-circuit native assets, source inputs, captures, findings and measured limits.

| Circuit | Captured revision | Visual review | Live frames | Station coverage |
| --- | --- | --- | ---: | ---: |
| australia | 887f09f0 | pass | 4341 | 125/125 |
| austria | 6a970d40 | pass | 3602 | 125/125 |
| bahrain | 6a970d40 | pass | 4791 | 125/125 |
| baku | pending | pending | — | —/125 |
| buddh | 6a970d40 | pending | 4613 | 125/125 |
| canada | 887f09f0 | pass | 3857 | 125/125 |
| china | 887f09f0 | pass | 5283 | 125/125 |
| cota | 887f09f0 | pass | 5368 | 125/125 |
| hockenheim | 6a970d40 | pass | 4112 | 125/125 |
| japan | 887f09f0 | pass | 4937 | 125/125 |
| jeddah | pending | pending | — | —/125 |
| malaysia | pending | pending | — | —/125 |
| monaco | pending | pending | — | —/125 |
| portimao | 887f09f0 | pass | 4389 | 125/125 |
| singapore | 887f09f0 | pass | 4784 | 125/125 |
| spa | pending | pending | — | —/125 |
| turkey | 6a970d40 | pass | 4816 | 125/125 |
| zandvoort | 887f09f0 | pass | 4241 | 125/125 |

Each closed packet contains a real simulation lap, every captured frame in an archived video, original selected/target images and input/tick journals. Frame counts are checked before raw JPEGs are pruned. Review uses whole-route sheets and original critical views; it is separate from the clean-lap checks. Unchanged scenes retain their exact prior asset/data fingerprints; changed scenes require fresh evidence.

The final repair wave addresses inside-verge folds at Austria/Spa, clipped kerbs at Buddh, source-backed open infields at Turkey, Hockenheim seating/canopies, Bahrain light-pool contrast, Jeddah construction materials and the EDITION frontage, Sepang’s radial end canopy, Baku’s service street/park, and Monaco’s lower-quay ground/frontages. Per-venue source records retain dimensions, uncertainty and the original evidence.

Checks: 177 focused Python tests, mypy and Ruff pass. Native geometry, support, collision, timing and the preserved Las Vegas dynamic lap pass. The source-registered Turkey openings have exactly four permitted barrier ends; other barrier chains remain paired and independent white-line/collision checks remain active. Accepted Silverstone, Monza, Interlagos and Las Vegas content and the handling/camera implementation are unchanged.

Peak total machine RAM was 7.590 GB against the 11 GB ceiling, with one heavy job at a time.

## Performance scope

NOT RUN at this checkpoint. The prepared uncapped protocol uses 1600×900, 100% render scale, existing quality settings, VSync off and a stationary production cockpit. Each analyzes 900 frames after 500 startup frames, without image recording. These local samples do not establish moving whole-lap frame-time parity. The capped live recordings include readback/encoding overhead and are not benchmarks.

## Remaining source and platform limits

- Widths, crossfalls, event-corner radii and temporary structures remain reconstructions with per-venue uncertainty; dense samples do not make them surveys.
- Portimao retained DGT ground yields local+10.162/-15.582% grades versus published+6.2/-12%. Global100m uphill maximum8.450% remains inconsistent; averaging does not resolve the source-definition discrepancy. Ground was not vertically scaled to force agreement.
- Suzuka operator publishes10-16m width while current native envelope is12-15m. Local registrations of the extremal widths are still needed. Its6.144m road-surface separation at the crossing is not underside clearance.
- Buddh T1-to-T3 rise is14.0003m; other sectors retain coarse DSM-derived heights with3m allowance. Generic width controls remain at several venues, including Japan/Jeddah/China and most of Australia.
- Zandvoort uses scalar lateral banking; the progressive T3 bowl is represented by equivalent edge-to-edge rise. Other venues retain neutral camber where a crossfall profile was not registered.
- Visual judgments cover whole-route sampled sheets and original critical images, not frame-by-frame human inspection of every archived video frame. Reference views can include cuts, reversed bearings and different weather.
- Automated live racing-line laps exercise actual simulation. They do not establish physical-controller handling or new menu/input coverage for all18 venues.
- Uncapped stationary render samples measure one registered local scene per venue. They do not establish moving full-lap frame-time parity with accepted circuits. Capped recorded laps include GPU readback and encoder overhead.
