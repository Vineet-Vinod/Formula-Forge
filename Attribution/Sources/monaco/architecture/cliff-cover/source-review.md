# Monaco cliff natural-ground V1 — bounded source/camera review

**Decision: PASS to a bounded material-only source/native trial for V1 and the adjacent mapped woodland domain.** This does not approve a cooked material appearance or close Monaco’s whole-scene hold. No height, geometry, planting, or protection changes are supported here.

## Frozen inputs

- V1 handoff SHA-256 `8990ffc5d09be4298e04d3e83a888cf98de581a99fa4fcec0726bc55c61285e4` (package `58cb50aa9c41d6863ee9d6cf68ce0cc6f514c7f3`).
- V1 changes 1,090 existing Grass rows over 76.4103 m² to the already installed mixed `MonacoNaturalGround`; XYZ, normals, UVs, row count/order, other materials, foliage, buildings, bridge, and driving data are unchanged.
- Fresh current camera witness: frame 189, camera station 229.7499 m, pixel `(480,168)`, existing row 1129 at `(-12.9873,352.1775,41.1163)`. This fresh hit supersedes the older frame-229 coordinates and the earlier report’s mistaken station reference.
- Adjacent proposal SHA-256 `39d8c61a69bd9dc88b479764e26392b11b9a1bc4323f6b21b2de4a983557c329`; overlay SHA-256 `4281095fd7072894808222414610fca401ff8cfa5ffeb66ff918315f80318874`.
- Reviewed the actual-frame before/after and source-domain projection studies, 2019 orthophoto, and the 2012, 2014, and 2024 oblique photos. The CPU previews use symbolic flat colors and opaque foliage/fence proxies; they do not prove native shader appearance.

## Source judgment

The oblique photos and orthophoto show a steep mixed ravine: exposed pale fractured rock, creeping vegetation, shrubs, and trees, with separately identifiable masonry belvedere, formal terrace walls, paths, buildings, bridge, and road. This supports the existing bounded ravine’s generic mixed natural ground material. It does not support calling the affected faces uniform lawn, painting the whole slope as bare rock, or extending the belvedere’s stonework over the ravine. The selected frame-189 background face is on that source-observed slope, but foliage and the distance do not reveal its exact local rock-versus-plant composition. `MonacoNaturalGround` is therefore a defensible mixed cover; it is not a pixel-level rock or plant classification.

The old straight `x=-12 m` experiment limit is not a mapped land-cover boundary. The author’s separate adjacent proposal corrects that issue by using the literal `natural=wood` polygon, OSM way 967508764, rather than borrowing the unrelated forest feature. It adds only 70.2717 m² after retaining the listed building, formal-garden, path, belvedere, racing, and protection exclusions. The exact frame-189 row 1224 witness at `(-8.8677,354.9299,44.1262)` lies inside that wood polygon and outside the stated guards (4.542 m nearest guard). The orthophoto shows a naturally covered rocky/wooded slope there, consistent with the oblique views. This finite owner-derived extension is supportable for the same mixed ground material.

## Limits

- Keep mapped tree positions, heights, and geometry unchanged; no individual canopy, species, stem, or ground elevation is qualified.
- Keep rock/ivy-specific rows and all crossing faces unchanged. Do not split rows or change normals, UVs, heightfield, structure, path, building, roof, bridge, or road.
- The domain boundary is a land-cover/source mask, not a surveyed substrate boundary. A future trial must preserve the proposal’s exclusions and exact existing triangle ownership.
- Native/cooked material behavior, shading, shadows, and the visible angularity of the ravine remain unreviewed. Monaco remains on whole-scene HOLD for other visible/source gaps.
