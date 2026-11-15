# Independent source-domain review

# Monaco remaining Runoff A/C/D source-domain review

**Decision: PASS for the finite private material-partition trial only.** This does not approve a mesh, a native scene, or the whole Monaco hillside.

Reviewed the frozen source proposal `opening-landscape-private/remaining-runoff-private/FROZEN-SOURCE-PROPOSAL.json` (SHA-256 `13579a7b81627baca0882dfd332eb4ee46844051fdf426eacbe5004b7e706f20`). Its bound inputs are `finite-natural-role-source-proposal.json` (SHA-256 `3f3006e76363f859f51eae0b47335649935ccb101d501704109694c1b52c47fb`), `proposed-natural-role-traces-on-ortho.png` (SHA-256 `e377fadf62c8d9449c0c4bb80da5c48fb9fe38cc0ef2c28a16b6153124dd1e90`), and the 7399 current-camera ray audit. That audit is bound to revision `7399cc6f94f47948420e7ec0c075a7abe515c90d`, frame 200 at 229.749924 m.

The registered 2019 government orthophoto shows mixed pale rock, vegetation, and planted ground in all three proposed areas. The dated 2012 ravine, 2014 bridge, and 2019/2024 chapel views corroborate that natural cliff-and-garden setting. They support a broad mixed-natural role, not exact soil pixels beneath canopy, a species census, or a new height profile.

- **A, below the formal coping:** the trace follows the visible irregular rock and planted slope immediately below the upper garden wall. The current ray at pixel `(380,175)` hits `Runoff` at `(-29.225, 363.533)` inside the clipped trace. Keep the white coping, paths, formal garden, structures, and held IGN terrace 4420 outside the material domain.
- **C, lower ravine between the chapel and Casa Mia:** the trace encloses the visible mixed vegetation and exposed rock while leaving the chapel apron, buildings, road, and path exclusions intact. The current `(420,310)` ray hits `Runoff` at `(-17.906, 335.888)` inside the trace.
- **D, Casa Mia southwest planted edge:** the trace is confined to the small visible planted bank. The `(600,320)` ray hits `Runoff` at `(4.184, 322.143)` inside the trace. Its small retained body-margin remainder must stay untouched.

The proposal correctly excludes **B** at `(542,140)`: its current hit is immediately beside Villa Marie Antoinette and the Casa Mia junction, where the orthophoto shows pale retaining, paving, and engineered terrace surfaces. It also preserves the formal and architectural exclusions across A/C/D.

The next private trial should split only intersecting old `Runoff` faces at the final packed XY coordinates, using each original face’s plane and interpolated normal/UV attributes. Preserve all complete outside faces and the small outside remainders identified in the proposal. Use the existing mixed `MonacoNaturalGround` role; do not recolor entire parent faces, alter heights, add plants, or change bridge, building, road, or contact data. The role boundary is a manual interpretation with about 0.5–1 m uncertainty, and canopy limits are not ground-material evidence. Require packed coverage/attribute checks and a same-camera native review after the private trial.


# Independent frozen candidate review

# Monaco A/C/D material partition: frozen private review

**Decision: PASS for bounded progression to native review.** This is not native appearance acceptance or a whole-route pass.

## Evidence reviewed

- Frozen handoff: `FROZEN-CANDIDATE-HANDOFF.json`, SHA-256 `aee81b9eb666d50dc234393ff503ec4d7e0224a926caedb71cbcf683a73a66ae`.
- Source geometry manifest: `4fc02c1722abbe393dc3b804d143f94d2f2bdae77400b0f2076f2947b6642ce5`.
- Private partition proof: SHA-256 `b7067696e1b9c12570fd4a5b50efde03d9c41ed3d2c08f170d5b4c71716476d8`.
- Exact-camera witnesses: frame 200 at station 229.749924 m, same 1600×900/FOV 90 camera for both views. Before image SHA-256 `811cb96793e4307469efd0bca66b824acb012526aaf7dbf18609d99782786f11`; after image SHA-256 `e9fe4e6befd5c3717138164fec3090218d86114df91e7b7395686f96cfbdf46b`.
- Prior source-domain decision: `monaco-remaining-runoff-acd-source-domain-review.md`, SHA-256 `e903f6769e99d57ebed6ecb02276d1872a6d1c426d1217c8ce39187d151064d1`.

## Finding

The exact-camera before/after pair shows the intended limited change on the source-identified natural slope while preserving the visible built junctions and major outlines. The candidate partitions only two Street assets: 181 selected parent faces, 41 whole-face role changes and 132 clipped partitions, yielding 370 additional rows. Eight sub-float32 natural ears remain raw/held. A, C, and D now first-hit the existing `MonacoNaturalGround` role; engineered area B remains `Runoff` and held. The Hermosa roof/body ray is unchanged.

The geometry proof reports zero coverage error beyond its encoding bound, maximum parent-plane error 2.31 µm, no encoded-envelope expansion, and all 115 other complete tiles and outside rows unchanged. It changes no height, normals beyond parent interpolation, UVs beyond parent interpolation, trees, architecture, roads, contacts, or native assets. The source-role boundary remains an approximate manual trace; this result does not validate bare ground under canopy or a height profile.

## Limits and next gate

The CPU render uses symbolic colors and simplified opaque foliage/fence, so it cannot establish how the existing mixed-material PBR appears in-game. The broad hillside and engineered Marie/Rome junction remain visibly unresolved in the source view. Proceed only to a same-camera native material review of this finite change; judge seams, shading, and whether the natural/built boundary reads correctly there. Do not count this patch as closing Monaco's wider hillside hold.
