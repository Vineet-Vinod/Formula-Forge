# Monaco under-arch woodland frozen V3 source/camera review

**Decision: PASS for the bounded private source/camera candidate.** The review supports this finite low-woodland improvement only; it does not accept native materials, cooked appearance, performance, or the whole Monaco scene.

## Evidence binding

- Frozen handoff: `build/reviews/resume-20261115/monaco/opening-landscape-private/underarch-frozen-v3-handoff.json`, SHA256 `a25bc2de8ab03285464c961e7f4116d537cb1839534d11e0c840cf23d861ff15`.
- Source/projection proof: `underarch-private-proof.json`, SHA256 `52729049294dec16fc4f804cc7a4eb47e13823ef831a04c1c19a8005059e0331`.
- Independent volume/exclusion proof: `underarch-independent-exclusions-volume-proof.json`, SHA256 `a289baabcd911c666d107fbc788ead325e38c901bfdc802d3efc39dd8e7e19aa`.
- Projected coverage proof: `underarch-projected-coverage-proof.json`, SHA256 `612757735da5d849c21f00c21d6822d90e16d066dfc617a7487a88ef1a8b9464`.
- Frame 197 candidate view: SHA256 `a91a7f0b1aed9374a11b51bf63d1bee8d3d6e36d7a556867f80527634d07d415`.
- Frame 229 candidate view: SHA256 `a84defec6b59a924247c0b79a34282a5aa594c913dce74bf08a203ed6e92d382`.
- Wind/material gate: `underarch-native-wind-supplement.json`, SHA256 `05a8cf5381c198031ff64a0b2bd158dd062722e0caa874d057960e6e4496eab4`; it references the current native material proof showing no connected vertex displacement/WPO.

## Source and camera judgment

OSM way 941749869 is mapped mixed forest. The 2019 orthophoto shows the bridge deck over the area, so it cannot classify the ground beneath it. The retained 2024 oblique does show low trees and shrubs under and beside the bridge. Together these sources support a bounded under-arch woodland addition, but not a uniform forest-material repaint or a claim about surveyed stems/species.

The candidate uses a 403.49 m² finite mask within the forest/deck window and adds 28 low shrub forms. In the actual-pose frame 197, the prior open under-arch gap gains planted mass below the bridge; the plants remain under the deck and away from the racing corridor. Frame 229 shows a smaller corresponding patch in the distance without obscuring the church or the route. The shape reads as low woodland in these technical projections and does not overgrow the garden/bridge context.

The domain is bounded and exclusions are explicit: the bridge, chapel apron, both bridge approaches, Casa patios/stairs/landings, racing road, barriers, and protection remain clear. Rock witnesses 6 and 7 remain rock; witness 9 remains its existing Ivy material. Only the previously unresolved Runoff woodland candidates are changed. The proof retains 25,190 other Street rows exactly and reports all full foliage/wind proxy volumes outside supports and protected areas. Minimum actual vertex-to-soffit clearance is 2.199 m and minimum full 0.25 m wind-proxy clearance is 1.883 m, above the 1 m target.

## Acceptance limits

The 0.25 m proxy is conservative relative to the inspected TreeCanopy material, whose WPO input is unconnected and which does not use material attributes. This closes the geometric wind-clearance question for the current material graph; any later material change must recheck it. The rendered CPU previews use flat light and opaque atlas/fence cards, so they do not establish native transparency, shadows, PBR appearance, or cockpit-scale leaf quality. Shrub positions, species, and dimensions remain reconstruction estimates.

**Result:** The finite forest-domain and recorded-camera evidence justify advancing V3 to native/cooked review. Keep the classified rock and existing Ivy witnesses unchanged, and do not extrapolate the mapped forest across roads, paths, bridge structure, or the full ravine.
