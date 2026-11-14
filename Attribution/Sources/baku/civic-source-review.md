# Baku Court and north-frontage source review

**Decision: SOURCE RECONSTRUCTION ACCEPTABLE FOR COOKED REVIEW; visual/native acceptance remains pending.**

## Reviewed evidence identity

- Canonical source: `tools/venues/baku_civic.py` SHA-256 `1c48416db03f7bfb7b7406cfbc6fcdf69e24c8231cf510442d741a1c2582f4c5` and `tools/venues/baku_civic_dataclasses.py` SHA-256 `b3578b96d7285c4fdf32bbca6a8b8692fd04c622a4e64621d52087fec05690d7`.
- Current source recipes: `Attribution/Sources/baku/court-frontage.json` SHA-256 `d13afb891d6543e96e425a68a4d2dbaae2458df01a67db3b97a4be96c63ecee2`, `north-frontage.json` SHA-256 `43cb7e38739aa0e264d4ec6d1ed385173933bf80a32673feddc3c652d58d2fc5`, and `court-photo-height.json` SHA-256 `d4beaba289b52e813066d64912463ae5aa174adc878aaef2744dbf52efc96791`.
- Source/contact evidence: `actual-base-course-proof.json` SHA-256 `922add357b01b22fa619b5c7a9d4de7fd7d6b035d90d88b8c7612dd589d66c28`; canonical counter receipt `canonical-counter-run.log` reports equal reviewed/canonical counters, no changed/added façade triangles, and identical native road rows/stations.
- Primary visual references: original 2015 Constitutional Court front photo `court-front-original-2015.jpg` SHA-256 `69ad2eabc1da6c02ad08acd6bdbfb1654cfa0a4b45c64438f3460568e6aa7cf3`; street/gate registration `court-other-photo-03.jpg` SHA-256 `227653a1d84dae8ec1418fd1d393198f2bcdebbd38c09354c47852f1df33bfc6`; Court entrance count `court-other-photo-02.jpg` SHA-256 `4824998140f16ceb487a0cb648ef5dc844cc3ed8485528baec507da81394776d`.

## Constitutional Court, OSM way 133641457

The edge-11 entrance registration is supported. The full street photo shows the Court frontage on the left, the service street continuing beside it, and the Shamakhi Gate ahead; the mapped service way runs beside the edge-11 side. The original 2015 frontal photograph directly supports the seven large upper arches, narrow first-floor window rhythm, small attic openings, three central entrance doors, and four broad ground-floor windows. The older edge-9 placement/count is superseded and should not be used.

The proposed 22.4 m body height is a reasonable architectural estimate, not a survey. The source photo was taken before later image retouching; the listed camera EXIF and mapped edge length of 32.822 m yield 22.44 m with a 0.0097 orthogonality residual. Sensitivity to the documented image-corner, width, and focal-length perturbations is 21.49–23.59 m, consistent with the chosen ±2 m uncertainty. The facade has a ground level, balcony/window level, tall arched level, and small upper window level under a parapet; the proposed 5.4/11.5/17.8/22.4 m bands are plausible divisions of that observed form. No floor elevations are surveyed.

The estimated entrance datum and three shallow steps are correctly kept separate from the unqualified southern public-stair corridor. Do not treat the retained renderer minimum as a measured entrance/foundation height. The rear elevation, side openings, canopy positions, and true below-grade foundation remain estimates.

## Adjacent north block, OSM way 133641456

The west-front registration has a good relative basis: its mapped edge 8 shares the Court edge-11 endpoint and continues along the same service-street corridor. The continuous street photo shows an uninterrupted sidewalk/curb and no large plinth at the junction. The north recipe therefore avoids transferring the Court's arches onto this separate block and does not use the roof-biased DSM base as bare-earth ground.

The local street controls vary from 5.016 to 7.052 m; along the observed west frontage, samples are approximately 6.10–6.95 m. A 7.15 m main threshold with ±2 m uncertainty is a bounded architectural datum, not a surveyed floor level. The night and press photos support a taller ground arcade/mezzanine, three broad rows of rectangular upper openings, and a small attic rhythm. A 24 m body estimate with ±3 m uncertainty is coherent with those proportions and the neighboring Court estimate; the resulting 31.15 m absolute roof is not an independently measured crown. The rear upper articulation and rear ground remain explicitly unresolved.

Current code creates the Court and north masses on their separate mapped footprints, grades the street-facing bases from the retained service profile, and keeps the rear/base uncertainties bounded. The actual base-course proof reports no missing public-ground samples, a closed base-support edge set, no roadway-byte or station changes, and 1,891 public footing samples. These are useful geometry/contact checks; they do not establish absolute building elevations, validate the old terrain surface, or demonstrate that a full cooked scene looks grounded.

## Remaining gates

- Keep 22.4 m, 24±3 m, 7.15±2 m, and the floor bands labeled as architectural estimates.
- Do not extend the west street datum across the north block's unqualified rear ground or flatten the wider historic district.
- Inspect a fresh cooked driving view before visual acceptance. The current evidence is source geometry and contact proof only; no runtime/native visual approval is implied.
- Preserve a distinct source-coverage hold for the unregistered north crown/rear articulation if later views or stronger site documentation contradict the present estimate.
