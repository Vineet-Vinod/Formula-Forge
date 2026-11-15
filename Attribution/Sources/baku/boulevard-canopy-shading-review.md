# Baku legacy boulevard crown lighting trial

**Decision: PASS for the bounded private lighting trial; native and cooked appearance remain unreviewed.** This is a tightly scoped candidate worth testing against the existing Sahil normal/material improvement.

## Frozen scope

- Handoff: `build/reviews/resume-20261115/baku/legacy-crown-lighting-private/frozen-handoff.json`, SHA-256 `b89cce22855ca65249e70449068449d302c936fa7ad6d23766b1515500b80e5b`.
- Proof: `private-proof.json`, SHA-256 `ac3b4982019ca218c525cadd99ba2e4aba98c3ba0d103d5a5ec51523d8d1f5af`.
- Nine literal source calls cover 163 existing boulevard poses. 4,890 leaf triangles receive normal/material changes only; all 11,736 trunk rows are byte exact, and all 16,626 old rows match. XYZ, UVs, winding, bounds, ground, and native assets remain unchanged.
- Packed normals are unit within `4.46e-8`; minimum normal Z is `0.1245`. Other selected and unselected trees are not changed.

The current-pose opaque-card rays identify likely foliage owners, but do not sample alpha or prove botanical species. Therefore the trial is appropriately limited to lighting representation; it should not add leaves, widen crowns, shift roots, or recolor ground.

The comparable Sahil A/B images show softer leaf shading but still visible card seams. A native comparison of these nine calls can determine whether the same normal treatment reduces the old boulevard's vertical striping without changing its silhouette. Keep the 163-pose scope and exact original rows as hard gates. Do not claim visual closure from the private packed proof.
