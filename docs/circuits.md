# Circuit sources

The playable catalogue contains **22 circuits**: the preserved Silverstone, Monza, Interlagos and Las Vegas baselines, plus 18 venues reconstructed from the supplied reference videos. Hanoi remains excluded. An enum entry alone does not make a layout playable.

## Current native profiles

The 18 reconstructed venues each export 8,192 native road samples. The table below
uses the current exported length, elevation relief and legal racing-width range.
Outside pavement and runoffs are separate surfaces; their width is not added to
the legal lane. Native station zero is not always the timing line; use each
venue's registered station anchors.

Racing profiles and surrounding terrain have separate sources:

- Austria, Spa, COTA and Zandvoort use retained classified-ground elevation products. Portimão uses retained DGT class-2 lidar points. Suzuka uses processed GSI ground data with separate bridge treatment. Turkey uses a digitised closed engineering profile; Buddh retains GLO-30 outside its source-corrected climb. Other published-profile and coarse-DEM reconstructions retain their stated uncertainty.
- Surrounding ground now uses the same regional ground providers at Austria, Spa, COTA, Zandvoort and Portimão, IGN RGE ALTI at Monaco, and GSI at Suzuka. The other venues retain documented GLO DSM sources and bounded local ground corrections. Grid spacing does not establish source accuracy.

Published profiles are digitised reconstructions; DSMs can include roofs and vegetation. These are not engineering surveys. Widths, banking, shoulder offsets and local escapes use the retained operator evidence and authored estimates documented per venue.

| Circuit | Native m | Relief m | Width m | Racing profile | Surrounding terrain |
| --- | ---: | ---: | ---: | --- | --- |
| [Bahrain](../Attribution/Sources/bahrain/provenance.json) | 5412 | 16.900 | 14.0–22.0 | [F1 profile](../Attribution/Sources/bahrain/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/bahrain/scenery-terrain.json) |
| [Jeddah](../Attribution/Sources/jeddah/provenance.json) | 6174 | 3.936 | 12.0–15.0 | [Retained GLO-90](../Attribution/Sources/jeddah/provenance.json) | [GLO-30 DSM](../Attribution/Sources/jeddah/scenery-terrain.json) |
| [Australia](../Attribution/Sources/australia/provenance.json) | 5278 | 2.600 | 12.0–15.0 | [F1 profile](../Attribution/Sources/australia/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/australia/scenery-terrain.json) |
| [Japan (Suzuka)](../Attribution/Sources/japan/provenance.json) | 5807 | 40.576 | 10.0–15.0 | [Processed GSI 5 m](../Attribution/Sources/japan/provenance.json) | [GSI 5 m](../Attribution/Sources/japan/provenance.json) |
| [China](../Attribution/Sources/china/provenance.json) | 5451 | 7.400 | 13.0–16.0 | [F1 profile](../Attribution/Sources/china/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/china/scenery-terrain.json) |
| [Canada](../Attribution/Sources/canada/provenance.json) | 4361 | 5.200 | 12.0–13.5 | [F1 profile](../Attribution/Sources/canada/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/canada/scenery-terrain.json) |
| [Monaco](../Attribution/Sources/monaco/provenance.json) | 3337 | 42.000 | 10.5–12.0 | [F1 profile](../Attribution/Sources/monaco/elevation-corrections.json) | [IGN RGE ALTI](../Attribution/Sources/monaco/scenery-terrain.json) |
| [Austria](../Attribution/Sources/austria/provenance.json) | 4318 | 63.338 | 12.0–13.0 | [Styria classified-ground DGM](../Attribution/Sources/austria/elevation-corrections.json) | [Styria DGM](../Attribution/Sources/austria/scenery-terrain.json) |
| [Spa](../Attribution/Sources/spa/provenance.json) | 7004 | 102.256 | 12.0–15.0 | [SPW classified-ground MNT](../Attribution/Sources/spa/elevation-corrections.json) | [SPW MNT](../Attribution/Sources/spa/scenery-terrain.json) |
| [Zandvoort](../Attribution/Sources/zandvoort/provenance.json) | 4259 | 8.718 | 12.0–14.0 | [AHN5 ground DTM](../Attribution/Sources/zandvoort/elevation-corrections.json) | [AHN5 DTM](../Attribution/Sources/zandvoort/scenery-terrain.json) |
| [Baku](../Attribution/Sources/baku/provenance.json) | 6003 | 26.800 | 7.6–14.0 | [F1 profile](../Attribution/Sources/baku/elevation-corrections.json) | [GLO-90 DSM](../Attribution/Sources/baku/scenery-terrain.json) |
| [Malaysia (Sepang)](../Attribution/Sources/malaysia/provenance.json) | 5543 | 22.000 | 16.0 | [F1 profile and local T15 reconstruction](../Attribution/Sources/malaysia/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/malaysia/scenery-terrain.json) |
| [Singapore](../Attribution/Sources/singapore/provenance.json) | 4940 | 5.300 | 8.8–14.0 | [F1 profile](../Attribution/Sources/singapore/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/singapore/scenery-terrain.json) |
| [COTA](../Attribution/Sources/cota/provenance.json) | 5513 | 30.956 | 12.0–16.0 | [USGS 3DEP 1 m](../Attribution/Sources/cota/elevation-corrections.json) | [USGS 3DEP](../Attribution/Sources/cota/scenery-terrain.json) |
| [Turkey](../Attribution/Sources/turkey/provenance.json) | 5338 | 47.888 | 14.5–21.0 | [METU engineering profile](../Attribution/Sources/turkey/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/turkey/scenery-terrain.json) |
| [Portimão](../Attribution/Sources/portimao/provenance.json) | 4653 | 28.738 | 14.0–18.0 | [DGT class-2 lidar](../Attribution/Sources/portimao/elevation-corrections.json) | [DGT ground](../Attribution/Sources/portimao/scenery-terrain.json) |
| [Buddh](../Attribution/Sources/buddh/provenance.json) | 5141 | 16.234 | 13.0–25.0 | [FIA climb + retained GLO-30](../Attribution/Sources/buddh/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/buddh/scenery-terrain.json) |
| [Hockenheim](../Attribution/Sources/hockenheim/provenance.json) | 4574 | 4.286 | 9.0–15.0 | [LGL classified-ground DGM025](../Attribution/Sources/hockenheim/elevation-corrections.json) | [GLO-30 DSM](../Attribution/Sources/hockenheim/scenery-terrain.json) |

Suzuka is the only figure-eight. Its back straight crosses the lower Degner road with about 6.14 m between the exported road surfaces. This is not underside clearance. Keep its separate deck protection; the planar boundary-union tool deliberately rejects this layout.

Native scenes include circuit-specific architecture, vegetation, protection, kerbs, escape surfaces, braking boards and pit paving. Pit access remains closed for the game. Source generation, native geometry checks and a clean simulated lap do not establish visual or performance acceptance. Follow the [whole-lap workflow](map.md) and compare the exact current assets against registered references.

Work is active through Sunday 15 November at 10am PST. The 18-map work remains
incomplete. Sixteen circuits retain compatible Luna High visual passes; Baku and
Monaco remain held. Carrying a review requires identical native scene, executable
and shared package payloads. Changed scenes need fresh packaged reviews; source
or bounded feature passes do not establish whole-circuit acceptance.

COTA's image-qualified approach has an approximately 13 m legal lane with
separate raised kerbs and flat painted aprons; the existing outside envelope is
retained. Its width remains an estimate within about 1 m. Jeddah's source-registered
Masarat group passes the night-lap review and closes the empty T27 skyline concern.
Its 144 m main-wing height and component dimensions retain their stated
reconstruction uncertainty.

Baku now includes the distinct Mariinsky gymnasium and De Bour mansion, Foundation,
Mirbabayev and waterfront 89/91 architecture. No5's photographed frontage has
source approval and is progressing to native review. Local material inputs that
incorrectly read unauthored baked AO/vertex data have a matched native PASS.
Sparse seafront planting, coarse DSM park banks and ordinary city detail remain
open. Roadside intersections alone do not establish incorrect street levels.

Monaco includes the Hermosa terrace, Villa de Rome architecture and separate
formal garden, chapel and grounded woodland. The roof has a bounded native
geometry PASS; the broader hillside remains held. Finite natural-ground material
partitions preserve the actual original terrain planes and keep the engineered
Marie/Rome junction separate. Property heights, garden levels and rock roles
retain their individual source qualifications.

The earlier Portimão, Sepang, Singapore, Buddh and remaining route reviews retain
their explicit scopes in the [validation checkpoint](additional_circuits_validation.md).
The rebuilt executable has fresh warmed Las Vegas/Interlagos baseline runs.
Earlier additional-circuit runs are historical; current comparisons are still pending.
Visual passes and clean automatic laps do not establish performance or surveyed
accuracy. Silverstone, Monza, Interlagos and Las Vegas remain preserved baselines.

Portimão's retained DGT class-2 ground produces steeper local grades than published
operator maxima whose measurement interval is unspecified. The source record keeps
this discrepancy open; heights have not been scaled or clipped to force agreement.
COTA's retained USGS road relief agrees with the official F1 chart at about 30.9 m.
The 133-foot promotional climb lacks matching endpoint definitions and does not
justify scaling that profile. Exact timing-line rise remains uncertain.
Event-corner reconstructions at Australia and Singapore retain explicit schematic
radius uncertainty. Neither dense controls nor a smooth rendered curve establishes
survey accuracy.

## Historical alignment inventory — 2026-11-04

This retained generator table records mapped alignment, uniform scale and the early footprint-count definition, including Las Vegas. It belongs to the initial 2026-11-04 source-fetch work; the Suzuka row already includes its later GSI update. Its relief and building columns are historical, not the current road or scene inventory. Most initial racing profiles used GLO-90. Scaling was applied only when mapped and published lengths already agreed within 1.5%.

| Circuit | Mapped m | Published m | Scale | Relief m | Turns found | Buildings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bahrain | 5422.5 | 5412 | 0.9981 | 19.7 | 13 | 45 |
| Jeddah | 6192.6 | 6174 | 0.9970 | 3.9 | 24 | 7 |
| Australia | 5307.6 | 5278 | 0.9944 | 6.9 | 20 | 21 |
| Japan | 5809.6 | 5807 | 0.9996 | 40.6 | 18 | 64 |
| China | 5460.8 | 5451 | 0.9982 | 8.7 | 12 | 26 |
| Canada | 4364.1 | 4361 | 0.9993 | 12.7 | 15 | 13 |
| Monaco | 3317.2 | 3337 | 1.0060 | 57.1 | 20 | 92 |
| Austria | 4303.0 | 4318 | 1.0035 | 67.7 | 11 | 10 |
| Spa | 6998.7 | 7004 | 1.0008 | 99.8 | 21 | 35 |
| Zandvoort | 4255.9 | 4259 | 1.0007 | 7.8 | 16 | 6 |
| Baku | 5971.0 | 6003 | 1.0054 | 36.9 | 17 | 214 |
| Malaysia | 5547.7 | 5543 | 0.9992 | 21.0 | 16 | 23 |
| Singapore | 4956.8 | 4940 | 0.9966 | 20.0 | 17 | 32 |
| COTA | 5504.3 | 5513 | 1.0016 | 21.9 | 18 | 22 |
| Las Vegas | 6179.1 | 6201 | 1.0035 | 16.2 | 13 | 65 |
| Turkey | 5347.9 | 5338 | 0.9981 | 35.3 | 15 | 8 |
| Portimao | 4661.4 | 4653 | 0.9982 | 27.9 | 16 | 11 |
| Buddh | 5137.1 | 5141 | 1.0008 | 13.2 | 16 | 1 |
| Hockenheim | 4567.2 | 4574 | 1.0015 | 9.2 | 13 | 41 |

Las Vegas's initial row is superseded by its [scenery inventory](../Attribution/Sources/lasvegas/scenery.json) and [recorded validation](lasvegas_validation.json). Its accepted reconstruction uses USGS 3DEP ground data and remains a separate baseline.

Hanoi was excluded because the retained OpenStreetMap relation contained two disconnected pieces of about 2.6 km and 2.3 km. Joining them into the published 5.607 km layout would require inventing roughly 600 m of circuit.

Per-venue provenance, reference indices, environment recipes and correction files live under `Attribution/Sources/<slug>/`. Preserve the retained raw data and earlier-source notes when revising a reconstruction. Native survey controls remain in [track_data](../Source/FormulaForge/Native/track_data/); use the guarded commands in the [map workflow](map.md) when applying changes.
