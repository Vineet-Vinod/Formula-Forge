Canonical handoff note — 2026-11-15: the reviewed private revision emits 4,278 tree triangles instead of 3,162 (+1,116), with all 31 poses and packed roots unchanged. Independent canonical/private replay matches exactly. The reviewer text below is retained as source-only evidence; fresh native/cooked acceptance remains pending.

# Baku Sahil canopy private-trial review

**Decision: PASS for the bounded 31-pose canopy-shape trial. This is not canonical, Unreal-material, full-scene, or whole-Baku acceptance.**

## Frozen evidence

- Source plan `build/reviews/resume-20261115/baku/sahil-canopy-private/source-plan.json`, SHA-256 `53d9e4543a6f54fb842e6b69b1800bfa7d40bfb269660c620f854b9df23c7ab8`.
- Alpha-aware proof SHA-256 `cb95ebdba8b54949d38512b86e41c474a7ade47760dde7fdb3cdb7eab481c58d`; it confirms 31 unchanged poses/root positions, exact root corners, exact retained old tree subset, and zero nonzero-alpha projected bounds crossing the road.
- Actual-camera private comparison at frame 1188 / station 1,179.573 m: baseline `baseline-1188.png` SHA-256 `01cee27dea963f5561e36981224b14a8835a443ae7658ab0fab0cc266e3a9df5`; candidate `candidate-1188.png` SHA-256 `41505fc2533c35ce7b03ee1cff2022a79fff78f4db7ee3bbc004c470ab1395c3`.
- Actual-camera private comparison at frame 1238 / station 1,272.172 m: baseline SHA-256 `a80d63d262f013b5694fe710f47bef5ff684dade67edd135c002270b0022db37`; candidate SHA-256 `c33c043d0fa0ffbf33cc7e71b78f7c5a921afb67ade7c6142ac9d9f3488a86ad`.
- Comparison reference `build/reviews/baku/reference/detail-0205.jpg`, SHA-256 `b7506b5e82e42ae04137e9b68e8a6a837c636eea7206629c7d918d2645a82bc5`, remains a corridor-level visual comparison with approximately ±60 m station uncertainty, not an individual-tree map.

## Assessment

The candidate's wider overlapping crowns and lower fork produce the intended canopy mass at both registered actual cameras. The 1,179.57 m preview changes from separated small crowns with long exposed trunks to fuller mature street/park crowns; the 1,272.17 m preview similarly reads as a more continuous planted edge. The largest Sahil crowns have occupied alpha widths of about 8.1–11.5 m and lowest foliage about 4.15–5.10 m over the root. Those are declared visual estimates with ±2 m width and ±1.5 m lower-canopy uncertainty, consistent with the source description of mature park trees without claiming surveyed individual forms.

Keeping the roots and coordinates fixed is appropriate: there is no evidence here that new individual trunks are needed. Replacing the underfilled full atlas cell with padded nonzero-alpha bounds and omitting the unusually sparse row-2/column-2 cell directly addresses the diagnosed miniature-card cause. Reusing the accepted leaf atlas also keeps the trial bounded.

## Limits and next gate

The Sahil park outline (OSM 25359701) bounds context only. AZERTAC's Sahil Garden feature supports mature plane, ash and palm trees and three fountains; it does not provide exact tree locations or authorize uniform grass. Keep fountain basins, paved paths, other building/vegetation context and all ground/road/protection unchanged. No new tree roots are authorized by this trial.

The CPU comparison uses an explicit alpha threshold of 128, two-sided leaves, and depth-tested camera projections. That is useful for source-scale judgment but does not prove Unreal clip/mip, PBR, shadow, or packaged camera appearance. Root's material confirmation and a fresh native/cooked comparison remain required. The broad gray ground and other generic frontage concerns remain separate; this canopy pass does not reverse the whole-route Baku HOLD.


Subsequent material evidence: canopy-material-confirmation.json records the actual saved Baku MI as two-sided, masked, with effective Opacity1.0 and clip0.3332999945; its unchanged accepted atlas matches the guarded source asset. The private alpha128 study is conservative. Fresh native/cooked canopy and whole-Baku review remain pending.
