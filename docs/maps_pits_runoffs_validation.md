# Maps, pit lanes and street runoffs — 2026-11-16

The 18-map modeling work remains incomplete. This checkpoint covers the requested map orientation, pit lanes and bounded street runoff fixes.

All 22 HUD handedness/marker checks and all 22 native pit support, collision and progress audits pass. Pit lanes are implemented for 21 additional venues; Silverstone is preserved. Seven street escapes were corrected using the supplied videos, registered maps and FIA documents. Monaco’s buried pit slab and Singapore’s wrong-side yellow paint were addressed during review.

Last reviewed package at the cutoff: `56b52b95`. Detailed hashes and evidence are in [the validation record](maps_pits_runoffs_validation.json). The final Singapore paint change is committed as `9292f8ba`; its staging repair and cooked color recheck were unfinished at the cutoff. Pit review decisions are scoped to the new lanes; they do not approve whole circuits.

| Circuit | Native pit audit | Live traversal | Pit visual review |
| --- | --- | --- | --- |
| silverstone | pass | pending | pending |
| monza | pass | pass | pass |
| interlagos | pass | pass | pass |
| bahrain | pass | pass | pass |
| jeddah | pass | pass | pass |
| australia | pass | pass | pass |
| japan | pass | pass | pass |
| china | pass | pass | pass |
| canada | pass | pass | pass |
| monaco | pass | pass | pass |
| austria | pass | pass | pass |
| spa | pass | pending | pending |
| zandvoort | pass | pending | pending |
| baku | pass | pass | pass |
| malaysia | pass | pending | pending |
| singapore | pass | pass | paint correction awaiting cooked recheck |
| cota | pass | pending | pending |
| lasvegas | pass | pass | pass |
| turkey | pass | pending | pending |
| portimao | pass | pending | pending |
| buddh | pass | pending | pending |
| hockenheim | pass | pending | pending |

The seven escape regions are Monaco T1, Baku T1/T2/T15, Jeddah T27 and Singapore T1/T3. The Jeddah inner green ribbon was reclassified within its source-qualified asphalt envelope. The Monaco correction preserves its canopy and upper garage geometry. Singapore’s material correction preserves road heights, white markings and kerbs.

Canada’s Senna island/bypass and Australia’s exact corner/year surface roles still need registration. Other street corners, the earlier 18-map modeling holds and performance parity remain unfinished.

Focused validation: 13 Python tests, mypy/Ruff, native regression audits, editor HUD/mesh-clipping automation and packaged session automation passed. Peak machine memory so far: 8.84GB, below 11 GB.

Native assets, recipes and supplied reference videos are retained. Cook duplicates were removed after package verification. Bulky step/tick journals are losslessly compressed; use `gzip -dk <file.jsonl.gz>` before replay. Selected images, complete review videos and frame journals remain directly readable.
