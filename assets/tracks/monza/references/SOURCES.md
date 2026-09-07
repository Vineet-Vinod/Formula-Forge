# Monza reconstruction references

References consulted on 4 September 2026. This is an environment reconstruction,
not a laser survey or an FIA homologation drawing.

- [Formula 1, 2026 Italian Grand Prix](https://www.formula1.com/en/racing/2026/italy).
  Official lap length and corner count: 5.793 km, 11 numbered turns.
- [Autodromo Nazionale Monza, circuit guide](https://www.monzanet.it/en/circuit/).
  Road width range, direction, named sections and approximate corner radii.
  Lesmo 1 is about 75 m; Lesmo 2 is about 35 m. These are useful independent
  shape checks, not instructions to replace the observed curves with circles.
- [FIA, Monza 2025 circuit map, version 2](https://www.fia.com/system/files/decision-document/2025_monza_event_-_circuit_map_-_monza_2025_0.pdf).
  Corner numbering, section order, marshal-post locations and historic oval crossing.
  The map was viewed as a reference; its copyrighted artwork is not included.
- [FIA, Monza 2025 F2 event notes](https://www.fia.com/system/files/decision-document/2025_monza_event_-_f2_monza_event_notes_2025_v1.pdf).
  Pit-lane and paddock photographs, barrier openings and the bridge after Ascari.
  These are support-series notes, not evidence of 2026 F1 operating rules.
- [Monza, 2024 modernization](https://www.monzanet.it/en/the-future-of-f1-starts-from-monza/).
  Resurfacing and recent venue construction context.
- [FIA Formula 3, analysis of the 2024 changes](https://www.fiaformula3.com/en/latest/article/race-analysis-how-monzas-track-changes-brought-the-most-dramatic-f3-finale.6jYCdvd3yS0cwr5FM2Xfii).
  Lower Ascari kerbs and the drainage crown. Crown magnitude is estimated here.
- [FIA WEC, Monza venue aerial photograph](https://www.fiawec.com/en/news/6-hours-of-monza-sees-38-cars-on-the-first-entry-list/7056).
  Pit-building roof trusses, main-grandstand canopy and seating, garage proportions.
  Older imagery is used for permanent architecture, not temporary event layouts.
- [Regione Lombardia, Monza park reforestation](https://www.regione.lombardia.it/agricoltura/boschi-e-foreste/rimboschimento-aree-del-parco-di-monza).
  Woodland restoration context after the 2023 storm. Individual current trees are
  not surveyed; planting in this scene uses mapped woods and preserved clearings.
- [South-venue aerial used in FormulaPassion's park report](https://www.formulapassion.it/mondo/lautodromo-di-monza-piantera-nel-parco-3000-nuovi-alberi).
  Viewed to distinguish the open southern park fields from the narrow tree belts
  beside the back straight. The two modeled shelterbelt rows are explicitly
  image-inferred. This older photograph does not establish current tree positions.
- [OpenStreetMap, circuit relation 284565](https://www.openstreetmap.org/relation/284565).
  Geographic observations for the car-racing route, pit lane, service roads,
  buildings, grandstands, gravel traps, woodland and disused oval.

## Geographic data and licensing

`monza.osm` is an unmodified OpenStreetMap API response for bounding box
`9.268,45.607,9.300,45.636`. It was retrieved from
`https://api.openstreetmap.org/api/0.6/map?bbox=9.268,45.607,9.300,45.636`.
Individual elements retain their version and edit timestamp.

Copyright OpenStreetMap contributors. Data available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OSM copyright and attribution](https://www.openstreetmap.org/copyright).
`survey.json` is the derived geographic database, distributed under ODbL 1.0.
The Blender scene is a produced work; preserve the OSM attribution when sharing it.
Generator code follows the repository license. No external image textures are bundled.

Runoff clipping uses Shapely 2.1.2 and its
[constrained polygon triangulation](https://shapely.readthedocs.io/en/stable/reference/shapely.constrained_delaunay_triangles.html).
Mapped traps take precedence over inferred infill, and both exclude the racing
surface and kerb aprons. This prevents coplanar overlap and preserves openings.

## Measured versus inferred

The plan uses WGS84 local tangent-plane metres at the mapped control line.
The observed polyline is 5,798.188 m in that projection. Interpolation and resampling
produce 5,798.513 m before the uniform scale correction of 0.999049281.
All map features receive the same correction, retaining their relative placement.
The final horizontal loop is 5,793.000 m; its modeled 3D length is 5,793.010 m.

The preliminary 5,794.4 m figure used a rough constant latitude scale; the final
survey uses the WGS84 ellipsoid instead. Both measurements remain distinct from
the normalized result.

Road height, local width transitions, crossfall, structure heights, construction
details, unmapped safety offsets and individual trees are artist estimates.
The scene is based on the 2025 FIA map with the 2026 official circuit specification.
Temporary 2026 signage, exact resurfacing details and storm recovery cannot be
certified from these references. No centimetre-level accuracy is claimed.
