# Baku Sahil canopy normal-field trial source review

## Decision

**PASS for a bounded private native realization and same-camera comparison. No appearance acceptance or canonical promotion.** The trial has a coherent, narrowly scoped explanation for the Sahil foliage card seams and preserves the already reviewed canopy geometry. Its most important remaining risks are native shader interpretation, foliage shadowing, and final normal quantization.

## Reviewed scope

- Frozen source plan: `build/reviews/resume-20261115/baku/sahil-volume-private/source-plan.json`, SHA256 `7e2e9521d24f507f128366029a7aef60ad249c94b7bc5646f64cb05e5f13a66c`.
- File map: SHA256 `59c44733244ebf4d5315ec7096ab394fc05b3ab378344bcd84edbd6d6f51402c`.
- Packed proof: `source-proof.json`, SHA256 `dd396c57e4d92a9af6832db892ae87ad2189a0640d83f73ab18a1a7b0e2b2f74`.
- Handoff: SHA256 `eb9514ff3cf538722503fed9ccbc4d0e6d3cc8ef9133b19f6ee8122bfed12bf0`.

The 31 existing poses, physical XYZ, UVs, triangle order/winding, bounds, tile ownership, and 2,976 trunk triangles remain exact. The 1,302 leaf triangles receive only the Baku-specific material binding and new vertex shading normals. The crown field is centered below the leaf vertices at the existing fork, uses the existing crown dimensions, and has positive packed normal Z at every vertex (minimum `0.0117977`). Its float32 normal error remains below the derived encoding bound. The proof explicitly retains the large raw-normal/face alignment range as intentional shading-normal bending; it does not claim that the cards became curved geometry.

The material plan is also bounded: clone the actual accepted SurfaceFoliage parent and Baku TreeCanopy instance; preserve all existing albedo, mask, UV, opacity, tint, subsurface, and shadow settings; change only the Normal input to `VertexNormalWS` with tangent-space normal interpretation disabled. The saved native query reports tangent-space normals enabled and the default neutral normal map connected in the current material. The recorded engine shader path supports the proposed world-space normal behavior. No shared foliage material or other tree family is modified.

## Required native comparison gates

Before promotion, compile the private parent/instance and verify that the cooked material has the intended world-space Normal connection and retained parameter values. Compare the exact 1179.57 m and 1272.17 m views against the accepted card-normal version at the same exposure, lighting, camera, and scene state. Inspect both card faces, crown silhouette, the old long vertical bands, contact at trunks, and cast/self-shadow changes. Capture final packed normals and confirm no zero/negative interpolated values after native mesh quantization. Preserve the existing geometry and the still-open Sahil/whole-Baku holds throughout this comparison.

Because the bent normals affect both BRDF lighting and shadow slope bias, disappearance of the bright/dark card bands alone is not sufficient: check shadow behavior and whether the overall crown becomes unnaturally smooth, flat-lit, or detached from the accepted foliage texture. Do not alter the shared material, disable shadows, or curve cards as part of this trial.

## Limits

The canopy widths/heights and continuous field are rendering approximations rather than botanical measurements. The reference association to `detail-0205.jpg` remains approximately ±60 m; this review does not qualify new tree positions, ground, park boundary, or whole-route fidelity. The source proof is not a native material or cooked-scene result.

Canonical source is a versioned native trial. Whole Baku remains HOLD; no native realization or appearance approval follows from this source review.
