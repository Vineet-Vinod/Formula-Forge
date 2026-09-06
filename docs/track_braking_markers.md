# Braking-marker policy

Use the usable approach length to select a sequence. Measure along the centreline from the previous corner complex's exit to the next braking corner's entry. A fast bend that requires no braking does not split an otherwise continuous approach. Treat a chicane as one complex, with one sequence before its first turn.

| Usable approach | Distance boards |
| --- | --- |
| 600 m or longer | 200, 150, 100, 50 m |
| 300–599 m | 150, 100, 50 m |
| 150–299 m | 100, 50 m |
| 100–149 m | 50 m |
| Under 100 m, no braking required, or a follow-up turn within a complex | None |

These thresholds are Formula Forge design choices, not an FIA standard or instructions to brake at a particular board. They leave at least 50 m between the previous exit and the first board. The reusable implementation is `tools/blender/tracks/braking_markers.py`.

Prefer a documented real-world sequence where a reliable reference resolves it. Otherwise use this policy, record entry/exit stations, and review the result at driving speed. Any override needs a short reason. If measured in-game braking begins before the 200 m board, review a longer warning sequence separately; do not change vehicle tuning to fit the signs.

Numbers show metres remaining to the recorded corner entry, not the apex or a guessed braking point. Place each board at `entry_station - distance`, wrapping around the lap. Keep it at that station when finding a suitable position behind the barrier. Do not measure the label's distance along the barrier.

Place boards on the outside of the upcoming turn unless track references or sightlines justify another side. Mount them above the rail, with opaque white panels and black digits facing approaching traffic. Keep posts outside the driveable area, preserve escape routes, and leave depth clearance between text and panel. Check readability and obstructions in the game renderer.

## Monza application

| Corner/complex | Entry station | Previous exit | Approach | Boards |
| --- | ---: | ---: | ---: | --- |
| Rettifilo, T1 | 609 m | 5,230 m | 1,172 m, across start/finish | 200 / 150 / 100 / 50 |
| Roggia, T4 | 1,817 m | 790 m | 1,027 m, through Curva Grande | 200 / 150 / 100 / 50 |
| Lesmo 1, T6 | 2,200 m | 1,970 m | 230 m | 100 / 50 |
| Lesmo 2, T7 | 2,545 m | 2,385 m | 160 m | 100 / 50 |
| Ascari, T8 | 3,630 m | 2,680 m | 950 m | 200 / 150 / 100 / 50 |
| Alboreto, T11 | 4,820 m | 3,940 m | 880 m | 200 / 150 / 100 / 50 |

No separate sequences at T2, Curva Grande/T3, T5, T9 or T10. This grouping is consistent with Brembo's description of six braking events per lap at Monza; the exact marker thresholds above are our own policy. [Brembo's 2025 circuit comparison](https://www.brembo.com/en/motorsport/formula1/infernal-circuits).

The corner-entry stations follow the current map's corner/kerb starts and remain aerial-scale approximations. The exported boards have their station, corner entry, direction and panel clearance recorded in `assets/tracks/monza/reconstruction/qa/braking_markers.json`.
