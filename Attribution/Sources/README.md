# Circuit reconstruction sources

The eleven non-Monza directories retain the inputs used to rebuild their roads,
elevation, runoff, barriers and surroundings. Monza has its own manifest.
Normal generation is offline; nothing under `build/` is a required input.

## Retained inputs

- `circuit.osm.gz` and `osm_source.json`: compressed OpenStreetMap snapshot,
  request bounds, retrieval time, uncompressed hash and attribution.
- `reconstruction.json`: observed route and mapped features with OSM IDs,
  a WGS84 local metre projection, rotation/translation, source start anchor,
  published lap length and four-metre spline controls. `survey.json` records
  the earlier scenery registration and is retained for source history; its
  old fit errors do not describe the reconstructed road.
- `elevation_observations.json`: absolute source elevations sampled along the
  road and at lateral offsets, source requests and sampling provenance.
- `elevation/`: retained regional raster crops or classified ground points,
  with their source licences and acquisition metadata.
- `terrain_dem.npz` and `terrain_source.json`: cropped broad terrain samples,
  georeferencing, original URL and hash.
- `references/`, `photo_registration.json` and `photo_traces.json`: licensed
  aerials, author/license records, world-to-image transformation and explicit
  pixel traces. The registration records model type and residual errors.
- `layout.json`: reviewed road-width and bank stations, filtered elevations,
  individual runoff polygons, wall paths, kerbs, vegetation, paint, braking
  zones and pit closures. Inferred features identify their assumptions.
- `provenance.json`: source URLs, dates, licenses and venue-specific uncertainty.
- `profile_reference.json`: retained numeric observations from published
  longitudinal profiles, including station registration and uncertainty.
- `architecture.json`: venue-specific model choices linked to operator,
  designer and contractor references; photographs remain reference-only
  unless a redistribution licence is recorded.

OSM snapshots and derived geographic databases are © OpenStreetMap contributors
under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OpenStreetMap attribution](https://www.openstreetmap.org/copyright).
The exported scenes, GLBs and previews are produced works using these data.

## Aerial references and attribution

Images are retained for registration and manual digitization; no aerial photo is
used as a runtime texture. These are historical snapshots, not a synchronized
2026 event survey. Retrieval dates must not be interpreted as capture dates.

| Circuit | Image / creator | Capture | License |
| --- | --- | --- | --- |
| Spa | [Service public de Wallonie (SPW)](https://geoportail.wallonie.be/catalogue/a12b5915-e56e-4827-8e4c-1f774934a2b1.html) | 2024 campaign; exact tile dates not resolved | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Suzuka | [Geospatial Information Authority of Japan (GSI)](https://maps.gsi.go.jp/development/ichiran.html) | Seamless-photo tile epochs not resolved; retrieval is not capture date | [GSI Content Use / Public Data License terms](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html) |
| Silverstone | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Silverstone_Circuit,_July_2,_2018_SkySat.jpg) | 2018-07-02 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Interlagos | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Aut%C3%B3dromo_Jos%C3%A9_Carlos_Pace,_July_3,_2018_SkySat.jpg) | 2018-07-03 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Shanghai | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Shanghai_International_Circuit,_April_7,_2018_SkySat.jpg) | 2018-04-07 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Bahrain | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Bahrain_International_Circuit,_November_2,_2017_SkySat.jpg) | 2017-11-02 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Sepang | [CK Tan](https://commons.wikimedia.org/wiki/File:Bird-eye_view_of_Sepang_F1_Circuit_-_panoramio.jpg) | Taken on 8 September 2016 | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0) |
| Cota | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Circuit_of_the_Americas,_April_22,_2018_SkySat.jpg) | 2018-04-22 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Istanbul | [Adbar](https://commons.wikimedia.org/wiki/File:Istanbul_Park_aerial.jpg) | 2013-05 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| Hockenheim | [Planet Labs, Inc.](https://commons.wikimedia.org/wiki/File:Hockenheimring,_April_29,_2018_SkySat.jpg) | 2018-04-29 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| Buddh | [Swapnil1101](https://commons.wikimedia.org/wiki/File:Buddh_International_Circuit_aerial.jpg) | 2021-03-22 17:25:53 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |

Changes include mosaicking/resizing, geographic registration and manual tracing.
Photo-derived authored layouts and the reconstructed non-Monza visual assets
are distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
with the credits above. Original photographs retain their stated licenses;
ODbL source databases retain ODbL. This attribution does not relicense game code.

Spa orthophoto attribution: **Service public de Wallonie (SPW) – Orthophotos
2024 (2026-01-15)**. GSI attribution: Geospatial Information Authority of Japan,
[GSI tiles](https://maps.gsi.go.jp/development/ichiran.html), processed into a
mosaic and modified into authored geometry; these modifications are not a GSI
product. GSI's [content terms](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)
apply. Individual seamless-photo tile capture dates remain unresolved.

## Elevation sources and limits

| Circuit | Road source | Authored relief |
| --- | --- | --- |
| Spa | SPW 2021–2022 bare-earth lidar, 0.5 m raster | 102.21 m |
| Suzuka | Operator course-guide longitudinal profile, digitized vector trace | 40.38 m |
| COTA | USGS 3DEP Texas Central 2017 lidar DTM, 1 m | 30.80 m |
| Silverstone | Environment Agency 2022 composite bare-earth lidar, 1 m | 11.34 m |
| Interlagos | PMSP GeoSampa 2017 classified ground lidar | 43.48 m |
| Shanghai | F1 graphical profile, reconciled with designer/FIA grade limits | 7.38 m |
| Bahrain | F1 graphical longitudinal profile | 16.90 m |
| Sepang | F1 graphical longitudinal profile | 22.00 m |
| Istanbul | METU engineering gradient diagram, reconciled and corner registered | 53.43 m |
| Hockenheim | LGL DGM025 bare-earth lidar, 0.25 m; 2022 update | 4.21 m |
| Buddh | Team-described landmarks and sparse terrain controls | 14.00 m |

Broad terrain at Silverstone, Interlagos and Hockenheim uses the same regional
lidar as the road. The other eight venues use retained Copernicus GLO-30
2021 terrain: a surface model containing trees and roofs, based on 2011–2015
data. Filtering and resampling cannot recover finer measurements.
Centimetre storage precision is not accuracy.

Istanbul's [METU engineering thesis](https://etd.lib.metu.edu.tr/upload/12608091/index.pdf)
contains a full gradient diagram and interval table. The original diagram has
a station typo, identified by the author; even after that correction the table
integrates to a 5.8845 m lap-closure error. The retained reference records every
original interval and the explicit reconciliation, preserving the two height
changes described in the text. Extrema are registered to mapped corners, with
the [operator's 8.145% maximum grade](https://tosfedistanbulpark.com/en/the-circuit/)
enforced. This is an inferred engineering reconstruction, with 6 m vertical
and 40 m station uncertainty, not a measured road survey.

Buddh's [McLaren team preview](https://www.motorsport.com/f1/news/after-two-disappointing-races-mclaren-waits-a-smile-from-fortune-at-buddh/428104/)
documents the 14 m rise from T1 to T3. The [Renault team preview](https://www.motorsport.com/f1/news/renault-sport-f1-view-on-upcoming-indian-gp-race/442233/)
describes the T1 compression and the descent/ascent along the back straight.
These observations replace the old under-height opening climb and register
the crest to T3. Other heights retain sparse coarse-terrain controls and
4 m vertical uncertainty. A complete measured road/camber profile remains
unresolved; this asset must not be described as survey accurate.

The F1 graphical traces retain pixel/station observations, local interpolation
and stated uncertainty. They are not construction surveys. Shanghai's raw
graphic exceeded the independently documented +3% uphill limit; its retained
profile is the least-change fit within the published +3%/−8% limits, followed
by local smoothing. The maximum height adjustment is 0.647 m. The stated
1 m uncertainty includes that conflict; the smaller 0.36 m pixel-tracing
uncertainty alone would not cover it. See the per-circuit numeric reference.

Suzuka uses the [operator's course guide](https://www.suzukacircuit.jp/eng/course_s/pdf/suzuka_courseguide.pdf)
longitudinal vector profile. Its local grades and the separation of the
crossing branches are preserved; the retained GSI samples remain source
history rather than the current road profile.

Modified-data attribution: produced using Copernicus WorldDEM-30 © DLR e.V.
2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under
COPERNICUS by the European Union and ESA; all rights reserved.
See [Copernicus DEM data and terms](https://registry.opendata.aws/copernicus-dem/).
USGS government lidar data are public domain. SPW lidar provenance and terms:
[2021–2022 terrain model](https://geoportail.wallonie.be/catalogue/a004e570-99d6-4fe5-b83d-49b774409278.html).
GSI DEM processing follows the attributed GSI terms above.

Silverstone attribution: **© Environment Agency copyright and/or database right
2022. All rights reserved.** The [1 m DTM](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m)
is used under [OGL v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
The 2022 composite contains surveys from 2000–2022; the local flight epoch
remains unresolved. Heights use Ordnance Datum Newlyn.

Hockenheim attribution: **Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0;
LGL-BW (2026).** [DGM025](https://opengeodata.lgl-bw.de/) crops are used under
[Datenlizenz Deutschland Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0).
Per-tile CSV records give a 2016-01-29 acquisition, 2022-02-15 update,
0.15 m stated height accuracy and the DHHN2016 height datum.

Interlagos attribution: **Prefeitura Municipal de São Paulo (PMSP), GeoSampa
M3DC 2017; accessed 2026-09-07.** The retained EPT subset contains 5,487,560
class-2 ground points. Sampling uses the closest containing triangle among
the eight nearest observations, with bounded inverse-distance interpolation
outside their convex hull. This avoids the extreme extrapolation of nearly
collinear local plane fits. The maximum nearest-ground-point distance at the
sampled road is 1.79 m. The [data owner's licence notice](https://prefeitura.sp.gov.br/web/licenciamento/w/licen%C3%A7a-para-uso-de-dados-do-geosampa)
published 2025-04-03 specifies CC BY-SA 4.0. This is the licence used here;
the older [AWS registry](https://registry.opendata.aws/pmsp-lidar/) labels GPLv3.
The EPT delivery metadata does not specify its vertical datum; road and terrain
use the same source and relative height origin.

[Formula 1's published elevation comparison](https://www.formula1.com/en/latest/article/highs-and-lows-which-f1-track-has-the-most-elevation-changes-.7I9JEcBw3R2AqXbnJ6hyvc.7I9JEcBw3R2AqXbnJ6hyvc)
(2016-10-21) independently reports 30.9 m for COTA and 43 m for Interlagos,
consistent with these lidar profiles. Operator figures of 133 ft (40.54 m)
and approximately 56 m respectively differ from those road measurements;
no profile is rescaled to force agreement. Per-circuit provenance records the
published cross-checks without redistributing the article's figures.

Camber is estimated from lidar cross-sections at Spa, COTA, Silverstone,
Interlagos and Hockenheim; elsewhere it is neutral and unmeasured. Source
resolution, road registration, profile filtering and survey age still limit
precision. Suzuka's approximately 6.2 m road separation agrees with the
operator profile; deck thickness and guard foundations are modeled estimates.

## Layout accuracy

Routes follow OSM observations and published circuit lengths. Projection and
uniform normalization are recorded; smoothing uses four-metre controls and
1536 runtime stations. Widths combine operator dimensions and aerial estimates.
Runoff and walls use mapped features and individual image traces, not constant
road offsets. Registration residuals, historical changes and oblique image
perspective limit their accuracy to metres in many areas. Sepang and Istanbul
have oblique aerials; their distant perimeter details are especially uncertain.

Suzuka and Interlagos start anchors were projected from the previous catalogue
and checked visually against aerial pit-straight context. Their exact painted
line locations remain approximate. Operator/FIA documents linked in each
`provenance.json` support configuration and dimensions; copyrighted PDFs are
research references and are not redistributed here.

Buildings use mapped footprints and heights where tagged. Other heights, roof
forms, tree distribution, landmark details, paint motifs and braking-board
locations are authored approximations. Pit-entry and pit-exit gates are fictional
physical closures requested for this game, not represented as real track features.

## Rebuilding and source refresh

Follow the [authoring commands](../README.md) for an offline export and geometry
verification. To review an aerial overlay, run:

```sh
uv run --no-sync python tools/diagnostics/review_circuit_layout.py shanghai
```

Source acquisition tools are deliberate, networked operations. Do not blindly
rerun `prepare_reconstructed_layout.py`, source importers or registration against
new revisions: retained manual traces, source transforms and every downstream
geometry export must be reviewed together. QA reports belong under
`build/circuit-reconstruction/`; they are not runtime or rebuild dependencies.
