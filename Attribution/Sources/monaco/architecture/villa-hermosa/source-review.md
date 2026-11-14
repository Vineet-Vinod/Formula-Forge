# Villa Hermosa upper-context source adjudication

## Source-qualified identity and envelope

Villa Hermosa is OSM way 94399624, at 9 Boulevard de Suisse, tagged as a six-level apartment building with a hipped roof. Its plan ring projects to approximately x −60.46…−27.46 m, y 385.18…403.76 m in the retained Monaco scene frame. IGN BDTOPO component `BATIMENT0000000074074444` has a nearly matching footprint (about 1–2 m planimetric difference, within its stated 2.5 m precision). This links the roof evidence to the mapped building; it is not a separate building to extrude beside Villa Hermosa.

IGN reports ground elevations from 52.9 to 68.8 m absolute, a roof-boundary ring at 82.1–82.8 m, `hauteur` 29.9 m, and maximum roof altitude 89.2 m, with 1.5 m vertical precision. Do not subtract the lowest ground from the highest roof and extrude that result uniformly: the footprint spans a steep grade, and the reported roof maximum may be a ridge above the boundary ring. The retained scene uses a generic 20.4 m / six-floor body, while the OSM feature itself only supplies the six-floor count. The source evidence supports a property-specific, hillside-stepped body and hipped roof, but not a flat platform or a single uniform base elevation.

The 2019 government orthophoto shows a broad gray hipped roof with a visible ridge/hip outline. The OSM footprint corners register inside that roof image: on tile `orthophoto2019-l8-r796835-c680971.jpg`, the ring spans about x −45…257 px, y 215…375 px; the western roof edge continues into the adjacent tile. The current generic frontage builder instead emits a constant-height flat triangulated Roof at `base + height`, so the flat roof is a concrete mismatch with both `roof:shape=hipped` and the orthophoto. Its single base is chosen as the minimum current ground sample around the ring, despite the source ground range spanning 15.9 m; that makes the resulting common floor bands a poor fit to a steeply stepped building. The generic 20.4 m body height is six default 3.4 m storeys, not an OSM height tag.

The height discrepancy is measurable in the retained registrations. Current 12 m terrain values sampled at the four OSM ring corners range about 52.77–62.23 m in scene Z, and the generic body's lowest corner sets a flat cap at about 73.17 m (52.77 + 20.4). Applying the retained IGN/scene vertical offset of 1.5129 m puts the IGN roof-boundary range at about 80.59–81.29 m scene Z and its maximum roof at about 87.69 m. The generic cap is therefore about 7.4–8.1 m below the measured roof boundary and 14.5 m below the source maximum. The IGN ground range is 52.9–68.8 m absolute; its broad local variation explains why neither that maximum nor the current coarse terrain's ring samples should be turned into a single flat foundation. The source record's `hauteur=29.9 m` is consistent with the lower-ground-to-eave scale but does not define a uniform extrusion across the sloping footprint.

Immediately south of the footprint, the same orthophotos show a bounded courtyard/garden with a rectangular blue pool, lawn and hardscape. Keep these as separate local garden/pool surfaces and low terrace edges. Do not extend the garden into the larger ravine or turn its pool apron into a building-height podium.

The 2012 ravine-station and 2024 chapel-wide oblique photos corroborate the steep planted cliff, terraced residential blocks and pale/cream hillside architecture in this district. Neither view is a registered façade photograph of Villa Hermosa. They do not establish its exact window pattern, balcony rhythm, ridge direction, local floor datums or individual retaining-wall heights. Keep the six OSM levels as the floor-count anchor; do not invent property-specific façade modules from the surrounding buildings.

## Relationship to the frame-266 ray and ravine trial

The frame-266 upper ray at pixel (300,110) meets existing Runoff at native approximately (−46.47,384.63), z≈58.13 m relative; the point is about 1 m from the IGN roof footprint. The ray does not hit Villa Hermosa. This is consistent with an unresolved narrow strip immediately outside the building/terrace edge, not evidence that the roof should be expanded or that the whole upper slope is roof. Keep the 574 m² open-ravine patch bounded below this property and exclude the building, pool and terrace. Any join repair should follow the literal roof/building and visible path/pool edges, with an explicitly estimated local collar.

## Recommended bounded authoring direction

1. Replace the generic six-storey flat-top appearance only within way 94399624. Follow the existing hillside rather than flattening the footprint; use the IGN boundary roof levels as anchors and a separate hipped ridge reaching the source maximum only where the 2019 roof outline supports it.
2. Preserve six principal storeys from OSM. Step their exposed base/facade against locally supported ground; do not treat IGN min/max elevations as a uniform façade plane. No exact floor elevations are established.
3. Keep the visible south pool, garden and hardscape as a small separate courtyard/terrace system. Preserve the pool opening and the visible slope/retaining transition beyond it. The orthophoto provides role and outline evidence; local wall heights and hidden supports remain estimates.
4. Do not extend the held L-roof feature `BATIMENT0000000074074420` or merge its terrace with Villa Hermosa.

This is source qualification only. It does not prove the current runtime appearance, authorize production edits, or establish surveyed elevations.

## Evidence identities

- OSM buildings source: `Attribution/Sources/monaco/buildings.osm.json.gz`, SHA-256 `fc3964cd49b8cb3c37cca673c7614fd4d7b13dea8dbf17cc979d687bae0c8e65`.
- IGN local building response: `Attribution/Sources/monaco/architecture/pending-hill-properties/ign-local-buildings.json.gz`, SHA-256 `f4a45e3fc55d0831593e04049cb5fbc11bde44dc4e82f21ac5f25d872754506a`.
- Current scenery recipe: `Attribution/Sources/monaco/scenery.json`, SHA-256 `385e1eb80278c74f2e159d6835f037935800bbaa2e06d2057e919e5562c51817`.
- 2019 orthophotos: tile 835/971 SHA-256 `41ec82e39f245bde2991d94ab95343c11179ca66efdd510eb3a591069f985c9c`; tile 835/972 `3d97d3b4fe136829c8c0f87341815af566ce9efb9c9dda43d1f5444599a695d6`.
- Oblique context views: 2012 SHA-256 `a9693f6f3617f793059ba3f180ff75155299082b2b6f2301b25cfd015c1e69ec`; 2024 SHA-256 `2972a1bc88c213ad9b1374bbfc6802be420fe29a54de18fabf60619288649d82`.
- Frame-266 ray record: `453-west-remaining-rays.json`, SHA-256 `9140d90cbd8099834f2b1b15ff7403e0031ae60b70b29d0da1d5ee693323f406`.


Developer garden-front photograph

The developer's project page and its BERT-R6785-HR_vh photograph provide a direct
reference for the long garden-facing elevation. The reconstruction uses four
broad loggia bays and two narrower French-window bays, rose columns, pale bands,
openwork iron rails and a dormered attic with a central pediment. Bay proportions,
1.2m balcony depth, column dimensions, ornament and the front-only mansard break
(12% inset,2.2m rise) are architectural estimates. All IGN eaves, the ridge maximum,
the literal main body and existing Ground remain unchanged. Six visible principal
levels are retained; the developer's nine-floor project description may include
hidden/lower levels and does not establish nine exposed rows here. Unphotographed
sides remain simpler estimates. The image is reference-only and is not a game
texture. Source photography is retained in the ignored review packet.

- Project: https://www.groupemarzocco.mc/en/projects/
- Photograph: https://www.groupemarzocco.mc/wp-content/uploads/2025/07/BERT-R6785-HR_vh-792x1024.webp
- Photo SHA256: d15f3bc2495c900a866d4f4763df567f2aa46d08b742e3bf8e7fe254b1fa04af
