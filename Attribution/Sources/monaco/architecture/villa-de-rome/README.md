# Villa de Rome reconstruction

The typed `reconstruction.json` reproduces frozen private V3 exactly. `source-review.md` grants progression to production/native validation; native/cooked appearance is pending.

Source roles:

- `marzocco-rome-primary.webp`: developer south façade, nine-storey identity, marble/stucco/loggias/balconies/mouldings. Source: https://www.groupemarzocco.mc/en/projects/
- `primary-2015-roof-detail.jpg` and `primary-2019-roof-detail.jpg`: retained government ArcGIS primary roof mosaics. Service URLs and the exact tile transform are in `source-qualification.json`.
- `north-trace-controls.json` and `north-trace-two-epoch-comparison.json`: independent shoulder/eave traces and cross-epoch residuals. No image fit or presumed parallax correction.
- `original-ign-controls.json`: unchanged IGN feature and four XYZ observations. North plan/Z associations conflict with the image trace; reported precision does not act as a hard clipping boundary.
- `native-diagnostic-camera.json`: fixed whole-roof review pose in the retained frame. Source Z is relative metres; world Z is centimetres. It is a constructed diagnostic camera, not a gameplay edit.
- `native-material-proposal.json`: architectural material estimates with explicit sRGB-reference-to-linear conversion and roughness values for root's existing palette factory.

The body/south façade, provisional 56.305 m base and existing Ground remain unchanged. The separate Rome garden and pool/terrace roles are not approved by this architecture recipe. The thin roof/soffit join adds no occupied floor; its support arrangement remains estimated. Cornice 82.7 m, shoulder 86.6 m and apex 88.0 m absolute are estimated; the unlocated IGN maximum 89.1 m is unused. The model surface at the original northern IGN XY is 3.230/1.847 m below the respective observations, so exact northern heights remain held.
