# Maps, pit lanes and street runoffs — 2026-11-16

The18-map modeling work remains incomplete. This checkpoint covers the requested map orientation, pit lanes and bounded street runoff fixes.

All22HUD handedness/marker checks and all22native pit support, collision and progress audits pass. Pit lanes are implemented for21additional venues; Silverstone is preserved. Seven street escapes were corrected using the supplied videos, registered maps and FIA documents. Monaco’s buriedpit slab and Singapore’s wrong-side yellowpaint were addressed during review.

Latest verified package: `56b52b95`. Detailed hashes and evidence are in [the validation record](maps_pits_runoffs_validation.json). Pit review decisions are scoped to the new lanes; they do not approve whole circuits.

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

The seven escape regions are MonacoT1, BakuT1/T2/T15, JeddahT27 and SingaporeT1/T3. The Jeddah innergreen ribbon was reclassified within its source-qualified asphalt envelope. The Monaco correction preserves its canopy and uppergarage geometry. Singapore’s material correction preserves road heights, white markings and kerbs.

Canada’s Senna island/bypass and Australia’s exactcorner/year surface roles still need registration. Other street corners, the earlier18-map modeling holds and performanceparity remain unfinished.

Focused validation:13Python tests, mypy/Ruff, native regression audits, editor HUD/mesh-clipping automation and packaged session automation passed. Peak machine memory sofar: 8.84GB, below11GB.

Native assets, recipes and supplied reference videos are retained. Cook duplicates were removed after package verification. Bulky step/tick journals are losslessly compressed; use `gzip -dk <file.jsonl.gz>` before replay. Selected images, complete review videos and frame journals remain directly readable.
