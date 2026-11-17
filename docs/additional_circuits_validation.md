# Additional circuit validation — 2026-11-15

This is the November 15 checkpoint. The subsequent pit and runoff changes are tracked in [the November 16 validation record](maps_pits_runoffs_validation.md). Those changes require their own review; the historical whole-circuit passes below do not complete the 18-map modeling work.

Checkpoint for the 18 additional circuits, current package `0463d68c`. The explicit review register records 18 visual passes, 0 holds and 0 pending reviews. This checkpoint does not declare the work complete.

Work remains incomplete. All 18 circuits have current-compatible visual passes. The incoming Niyazi source reconstruction and intermittent rendering stalls remain unresolved. Visual acceptance does not establish source completion or performance parity.

The [validation record](additional_circuits_validation.json) pins package payloads, exact scene identities, reports, archived frames, current profiles, runtime scope and performance evidence.

| Circuit | Captured revision | Visual review | Live frames | Route bins |
| --- | --- | --- | ---: | ---: |
| australia | 2e95c625 | pass | 4347 | 125/125 |
| austria | 2e95c625 | pass | 3606 | 125/125 |
| bahrain | 2e95c625 | pass | 4779 | 125/125 |
| baku | 0463d68c | pass | 5192 | 125/125 |
| buddh | a0d9e464 | pass | 4610 | 125/125 |
| canada | 2e95c625 | pass | 3866 | 125/125 |
| china | 2e95c625 | pass | 5215 | 125/125 |
| cota | 2e95c625 | pass | 5404 | 125/125 |
| hockenheim | 2e95c625 | pass | 4086 | 125/125 |
| japan | 2e95c625 | pass | 5002 | 125/125 |
| jeddah | 2e95c625 | pass | 4990 | 125/125 |
| malaysia | 2e95c625 | pass | 4945 | 125/125 |
| monaco | 357f04a7 | pass | 3473 | 125/125 |
| portimao | 2e95c625 | pass | 4421 | 125/125 |
| singapore | 2e95c625 | pass | 4825 | 125/125 |
| spa | 2e95c625 | pass | 5296 | 125/125 |
| turkey | 2e95c625 | pass | 4793 | 125/125 |
| zandvoort | 2e95c625 | pass | 4267 | 125/125 |

A prior capture is carried only when its complete per-circuit scene identity equals the current pin. Its original captured revision stays visible. Archived MP4 sample counts, recording counts and journals are checked; visual assessment remains separate from native/live lap validity.

## Source completion holds

These independent source findings remain unresolved despite retained visual passes. The visual decisions above remain separate. No held circuit is complete.

| Circuit | Outstanding source finding |
| --- | --- |
| baku | Incoming Niyazi carriageway and its immediate walk remain held for source completion. The ordinary traffic island and joined junction are a separate repair. A whole-route visual PASS does not resolve that source hold or establish survey accuracy. |

## Current native profiles

These figures are recalculated from the current road exports. Sample density is not survey accuracy. The JSON retains canonical source records and their stated uncertainty.

| Circuit | Samples | Relief m | Width m | Rise/fall % per chord | Rise/fall % over 100 m |
| --- | ---: | ---: | --- | --- | --- |
| australia | 8192 | 2.60 | 12.00–15.00 | 0.81/-1.11 | 0.74/-0.92 |
| austria | 8192 | 63.34 | 12.00–13.00 | 12.13/-9.16 | 12.01/-8.59 |
| bahrain | 8192 | 16.90 | 14.00–22.00 | 3.55/-4.85 | 3.46/-4.67 |
| baku | 8192 | 26.80 | 7.60–14.00 | 9.76/-7.59 | 9.12/-7.43 |
| buddh | 8192 | 16.23 | 13.00–25.00 | 10.17/-9.16 | 8.91/-6.19 |
| canada | 8192 | 5.20 | 12.00–13.50 | 3.41/-4.00 | 3.02/-2.77 |
| china | 8192 | 7.40 | 13.00–16.00 | 3.00/-6.98 | 3.00/-5.95 |
| cota | 8192 | 30.96 | 12.00–16.00 | 13.63/-12.37 | 12.30/-10.65 |
| hockenheim | 8192 | 4.29 | 9.00–15.00 | 2.22/-2.58 | 1.59/-2.20 |
| japan | 8192 | 40.58 | 10.00–15.00 | 8.80/-8.82 | 7.34/-7.26 |
| jeddah | 8192 | 3.94 | 12.00–15.00 | 3.54/-3.54 | 2.64/-2.45 |
| malaysia | 8192 | 22.00 | 16.00–16.00 | 5.72/-6.07 | 4.95/-5.88 |
| monaco | 8192 | 42.00 | 10.50–12.00 | 9.52/-9.30 | 9.27/-7.99 |
| portimao | 8192 | 28.74 | 14.00–18.00 | 10.16/-15.58 | 8.45/-11.64 |
| singapore | 8192 | 5.30 | 8.80–14.00 | 1.39/-1.35 | 1.30/-1.32 |
| spa | 8192 | 102.26 | 12.00–15.00 | 15.59/-8.40 | 14.23/-7.21 |
| turkey | 8192 | 47.89 | 14.50–21.00 | 8.15/-8.15 | 8.14/-8.14 |
| zandvoort | 8192 | 8.72 | 12.00–14.00 | 9.51/-8.84 | 6.29/-4.92 |

## Runtime and preservation scope

- Optional progressive quadratic banking and measured bank-edge fade now share height/slope functions between simulation, tyre support and rendered geometry. Default paths and unaffected physical data retain their exact outputs; shared vehicle tuning and camera code are unchanged.
- Spa alone rotates the sky, dome and sun by 120 degrees at unchanged energy, elevation and exposure. The ineffective 0.06 normal-strength trial was rejected and 0.18 restored. Source grid heights and native data are unchanged. A bounded 0.25 m mesh represents the existing field within 2.517 cm in the visible core and rejoins the actual old outer triangle planes. Fresh full-route visual review passes; residual tone and rounded-hollow differences lack matched source classification.
- Singapore-only generated road controls are aligned with Anderson Bridge driver-left opening, with an 8.8 m legal lane and separately accounted kerbs/shoulders/wall thickness. Local smooth joins replace the rejected infinite-axis exit shift. No shared vehicle/camera implementation changes.
- Malaysia alone uses a 16 m legal lane, exact frozen baseline widths for outside pavement, estimated adverse final-corner section and rising-exit warp. Generated paving triangles preserve actual render/contact agreement; Ground queries them outside the protected analytic road/kerb core. Focused source/native regression checks cover old core contact, flat apron contact, pit registration and packed vertex agreement. Other circuit behavior and vehicle tuning remain unchanged.
- COTA alone narrows the image-qualified 2,180–2,380 m approach to 13 m at 2,220–2,340 m, with about 1 m source uncertainty. Paired shoulders and retained-width compensation after the existing runoff minimum preserve the outer envelope within 0.0005012 m. Its field, alignment, elevation and banking remain exact, as does other circuit physical data. Shared handling and camera are unchanged.

The supplied scope proofs and their hashes are retained in the JSON. Accepted-circuit assets, shared runtime changes and car/input/camera scope are reported separately; asset preservation is not a claim that no runtime code changed.

Baku's native traffic island, closed low curb and connected paving replace 674 faces with 18,507 in one street mesh. Complete mesh comparisons and native checks preserve the accepted park, office, 98 trees, other 17 circuit scenes and physical data. The first recording stopped at the disk guard. Only the clean retry, with 5,192 frames and all 125 route bins, is selected for the new review. Niyazi source completion remains separately held.

Full source checks passed 392 tests, type checking across 208 files, and lint. The package and session checks passed. Cleanup retired 6.22 GB of duplicate cooker output and 2.57 GB of failed recording images, preserving the runnable package, source references and canonical game assets.

Sampled peak machine memory was 7.140 GB against 11 GB, using the 5 s monitor. One heavy job at a time is attested in the register.

## Uncapped performance

Moving measurements are separate from capped image recordings and stationary samples. Only explicitly current scene/runtime-compatible runs appear below; historical runs remain labelled in the JSON.

| Circuit | Kind | Measured frames | Median ms | p95 ms | p99 ms | Max ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| australia | moving | 7359 | 18.83 | 22.53 | 27.29 | 69.70 |
| austria | moving | 4948 | 22.89 | 26.82 | 41.23 | 71.31 |
| bahrain | moving | 7873 | 19.43 | 23.83 | 30.58 | 66.93 |
| buddh | moving | 6659 | 21.94 | 27.52 | 38.44 | 79.82 |
| canada | moving | 6249 | 19.66 | 23.75 | 29.65 | 66.43 |
| china | moving | 8836 | 19.04 | 23.65 | 27.83 | 87.32 |
| cota | moving | 9320 | 18.42 | 22.28 | 26.85 | 65.09 |
| hockenheim | moving | 6455 | 20.48 | 25.42 | 30.13 | 71.36 |
| japan | moving | 7421 | 21.95 | 26.83 | 33.57 | 74.94 |
| jeddah | moving | 7603 | 21.05 | 26.16 | 34.11 | 66.33 |
| malaysia | moving | 6633 | 24.24 | 35.47 | 39.45 | 48.90 |
| monaco | moving | 4350 | 29.02 | 39.29 | 51.72 | 80.89 |
| portimao | moving | 7730 | 17.90 | 23.06 | 28.75 | 49.01 |
| singapore | moving | 7054 | 22.04 | 26.28 | 29.04 | 49.78 |
| spa | moving | 6479 | 27.93 | 36.59 | 50.14 | 82.38 |
| turkey | moving | 8499 | 18.02 | 21.88 | 26.39 | 73.48 |
| zandvoort | moving | 6819 | 19.93 | 24.00 | 27.93 | 67.93 |
| lasvegas | moving | 6807 | 22.53 | 30.46 | 33.92 | 47.16 |
| interlagos | moving | 6502 | 19.68 | 24.80 | 28.40 | 53.64 |
| baku | moving | 7233 | 22.49 | 29.74 | 36.03 | 59.86 |

Moving runs require one full warmup route and complete measured route coverage. They use automatic driving input and do not establish physical-controller handling. Stationary numbers describe only their registered local scene. Capped recording intervals include readback and encoding overhead.

## Remaining source and platform limits

- Dense native controls do not make reconstructed widths, event radii, height fields or temporary architecture into surveys.
- Portimao classified DGT ground yields a maximum 100 m rise of 8.45%, inconsistent with the operator headline 6.2%. The source-definition difference is unresolved; no unsupported vertical rescaling was applied.
- Japan now uses registered GSI widths around 10 to 15 m; the operator 16 m extremum is not yet locally registered. Road-top separation at the crossing is not underside clearance.
- Zandvoort T3 now uses the measured progressive quadratic bowl and bounded paved bank. Cross-sections and source epochs still carry their stated uncertainties.
- Buddh T1-to-T3 has an FIA climb constraint; other terrain retains coarse DSM uncertainty. Generic width controls remain at several venues, including parts of Australia/Canada/China/COTA/Singapore.
- Ordinary city facades, vegetation and crowds remain stylized. A visual pass is limited to its exact current scene, whole-route sampled sheets and original critical views.
- Automated native/live laps do not establish physical-controller handling or all menu/input paths. Reference clips can contain edited cuts and different cameras.
- Only explicit uncapped moving samples establish measured whole-route frame times. Stationary samples and capped image recordings have separate scopes.
- Hockenheim visible stand-front join is closed; a hidden mismatch up to 1.479 m remains outside the bounded repair. No broad earth bank was invented to conceal it.
- Malaysia’s adverse T15 profile and rising exit are implemented and visually passed. The 16 m legal width is primary-designer supported; 4% mean/7% inner/1% outer crossfall, 15.4 m exit crest and local station warp are estimates, with ±1 m elevation and ±50 m station uncertainty, not civil survey values. Wider original pavement is preserved from the actual frozen 8192-row baseline; outside support-zone discretization differs by at most 4.5 cm.
- Masarat height 144 ± 12 m, lower wings and terrace/entry dimensions are architectural estimates. Its visual pass does not identify or survey every neighboring Jeddah building.
- Repeated 50–80 ms frame intervals occur in uncapped diagnostics across several added circuits. A warmed CPU-only control omitting detailed GPU trace/csvGpuStats still shows 13 occlusion-result waits above 40 ms in 8 episodes; driver/GPU scheduling cause remains unresolved. No runtime-default change or performance-fix claim.
- Incoming Niyazi carriageway and its immediate walk remain held for source completion. The ordinary traffic island and joined junction are a separate repair. A whole-route visual PASS does not resolve that source hold or establish survey accuracy.
- baku: Incoming Niyazi retains incompatible old upper-edge/lower-walk reconstruction constraints. Its true upper-edge height and exact dated-photo registration remain unknown. Separate source-completion HOLD persists despite this whole-route visual PASS.
- baku: Road/camber/island floor and 0.15 m curb are estimates tied to three actual racing-Road anchors, not a survey. Office/ground ±2 m and individual tree inventories retain their source limits.
- canada: Visual decision is bound to the unchanged 887 scene; performance is separate.
- china: No missing crossing-cylinder or parasol defect is established. Ordinary secondary façades remain simplified; no current blocker was demonstrated.
- cota: No confirmed blocker in the reviewed complete route; performance remains separate.
- cota: The source-estimated 13 ±1 m approach and separate raised curb/flat red apron pass fresh whole-route review. The outside protection/paving stays registered; no regression found at T1/T15. Geometry remains an image-derived reconstruction.
- hockenheim: A hidden stand-front terrain mismatch up to 1.479 m remains outside the repaired visible low end. Forest density and some secondary facilities remain simplified. Numerical closure does not establish survey precision.
- japan: Stylized forest/crowd/facility detail and width survey limits remain caveats, not demonstrated blockers.
- jeddah: Diamond remains a source-supported construction skeleton. Low urban frontage, mall and tower subparts need mapped/photo qualification; do not extrude an entire podium as the full-height tower.
- jeddah: Source-registered Masarat fills the T27 exit sequence at night, with no visible floating/overlap/pop. The five-part source-estimated volume is separate from Sail; unnamed neighbors and unsurveyed component dimensions remain stated limits.
- malaysia: Primary designer supports the 16 m legal lane and qualitative adverse/rising-exit shape. No primary numerical cross-section exists in retained sources; local slopes and crest are architectural/track reconstruction estimates.
- monaco: Garden datums, architectural heights, roof-to-ortho disagreements and the lower Marie/Rome junction retain their documented reconstruction uncertainty. The matched 357f04a7 whole-route visual review passes; missing survey precision alone is not a visual hold.
- monaco: The fresh uncapped Monaco run is GPU-bound at about 29 ms median/39 ms p95, with intermittent occlusion-result stalls. Visual acceptance does not establish performance parity with the accepted baselines.
- portimao: Retained DGT road samples are correctly registered to asphalt with no bridge-deck hump, but observed local grades remain in conflict with the operator-published headline values. The vertical/source-definition discrepancy is unresolved; do not clamp or rescale from the headline alone.
- singapore: Mapped landmark/frontage revisions are simplified in secondary city sectors; no current source-qualified blocker is demonstrated by the reviewed packet.
- spa: Source grid nodes and native data are unchanged. The refined mesh reproduces an existing interpolation, not finer survey data. Remaining bank tone/shape differences are unclassified, not declared wrong terrain.
- zandvoort: The progressive bowl and exact survey cross-section remain bounded reconstructions; no blocker was demonstrated in the reviewed route.
