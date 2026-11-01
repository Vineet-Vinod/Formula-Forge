# Monza reconstruction references

## Regional 3D survey, 25 October 2026

`regional_3d/` retains paginated, unmodified feature records from Regione
Lombardia's Database Geo-Topografico. Its manifest records the requests, hashes,
acquisition date and CC BY 4.0 licence evidence. Building volumes retain both
extrusion type and height; roof elements, sports structures, breaklines and spot
heights retain their source Z coordinates. `DATA_INI` distinguishes the older
surveys from the date downloaded. Run `fetch_monza_3d.py` to refresh these inputs.

The spot-height domain distinguishes ground (`01`, `0101`), building feet
(`0301`) and eaves or roof observations (`0302`). Roof points must not be treated
as ground. For example, points 9803845–9803861 constrain the long pit building's
roof, while 9806306 and 9809607 constrain the side grandstand roofs. Different
roof levels and the pit's raised truss must be compared separately. These
observations supersede guessed heights where their locations and structure age
match; they do not establish current event signage or every facade detail.

This directory contains the inputs required by the authoring tools. `survey.json`
supplies the circuit geometry and mapped features; `layout.json` supplies the
reviewed barriers, runoff and braking zones. `monza.osm` is the offline input to
`survey_monza.py`. Keep this manifest for provenance and attribution. Reference
images, screenshots and generated QA reports belong under `build/`.

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

The subsequent layout revision records its sources in [layout.json](layout.json).
AGEA 2024 regional orthophotos supply the approximate barrier and runoff plan;
the FIA 2026 competition notes corroborate chicane escape connectivity. The
[FIA circuit and pit-lane pack](https://www.fia.com/system/files/decision-document/2026_italian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf)
was also consulted. These sources do not provide a measured elevation model.
The closed pit entry and exit are a recorded game-specific exception.

`monza.osm` is an unmodified OpenStreetMap API response for bounding box
`9.268,45.607,9.300,45.636`. It was retrieved from
`https://api.openstreetmap.org/api/0.6/map?bbox=9.268,45.607,9.300,45.636`.
Individual elements retain their version and edit timestamp.

Copyright OpenStreetMap contributors. Data available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OSM copyright and attribution](https://www.openstreetmap.org/copyright).
`survey.json` is the derived geographic database, distributed under ODbL 1.0.
The Blender scene is a produced work; preserve the OSM attribution when sharing it.
Generator code follows the repository license. The original reconstruction bundled
no external image textures; the rebuild below adds licensed CC0 surface maps.

Runoff clipping uses Shapely 2.1.2 and its
[constrained polygon triangulation](https://shapely.readthedocs.io/en/stable/reference/shapely.constrained_delaunay_triangles.html).
Mapped traps take precedence over inferred infill, and both exclude the racing
surface and kerb aprons. This prevents coplanar overlap and preserves openings.

## Measured versus inferred

The plan uses WGS84 local tangent-plane metres at the mapped control line.
The observed polyline is 5,798.188 m in that projection. Interpolation and resampling
produce 5,798.513 m before the uniform scale correction of 0.999049281.
All map features receive the same correction, retaining their relative placement.
The horizontal loop is normalized to 5,793.000 m. The measured terrain revision
adds the vertical component separately.

The preliminary 5,794.4 m figure used a rough constant latitude scale; the final
survey uses the WGS84 ellipsoid instead. Both measurements remain distinct from
the normalized result.

Road height now uses the regional ground observations described below. Local
width transitions, crossfall, unmeasured structure heights, construction details,
unmapped safety offsets and individual trees remain estimates.
The scene is based on the 2025 FIA map with the 2026 official circuit specification.
Temporary 2026 signage, exact resurfacing details and storm recovery cannot be
certified from these references. No centimetre-level accuracy is claimed.

## Reference rebuild, 22 October 2026

`rebuild_reference_index.json` records timestamped observations from the user's
`build/references/monza/reference.mp4`. This commercial game footage is a visual
reference, not survey data. Its frames and the AGEA consultation image remain
under `build/` and are excluded from shipping assets. The original pass misidentified the central grandstand's oval press room as a
22.25 m timing tower. The survey and ACI oblique photograph resolve that conflict;
the full-height cylinder has been removed. The separate north/south hospitality
towers shown in Monza's 2025 brochure are not represented by that aerial pick.

The rebuild retains the surveyed road, runoff and barrier meshes. It adds pit
balconies, glazing, railings, a curved timing tower, spectators, event panels,
Italian flags, two event screens and low woodland growth. The screen placements,
canopy details, sponsor spans, vegetation density and race-day occupancy are
estimates. The existing pit closure remains part of the retained layout.

Surface maps reuse the CC0 inputs and derivatives documented in Silverstone's
`rebuild_materials/manifest.json` and `architecture_materials/manifest.json`.
Monza's map hashes and recipes are in `rebuild_materials/manifest.json`. The sky
uses the existing CC0 Spa panorama with a recorded color adjustment. It depicts
illustrative daylight, not measured venue weather. Spectators and screen imagery
are original project artwork. Event panels use original DejaVu Sans Bold
lettering; no logo artwork or pixels were extracted from the reference video.

Run `make monza-assets` to apply the repeatable detail pass to the retained
surveyed BLEND and export it. The full `build_monza.py --phase finalize` path also
applies the pass after repairing the base scene. Run `make monza-preview` for the
Blender overview and `make monza-check` for asset validation, tests, lint and type
checks. These targets use the existing memory and filesystem guard. The GLB now
retains material-specific UVs, vertex colors, normal maps and roughness maps.
Visual exports no longer rewrite the driving survey or barrier contact include.


## Regional elevation and structure reconstruction, 25 October 2026

`prepare_monza_terrain.py` selects 3,439 DBGT ground observations from the retained
`regional_3d/spot_heights.json`. Classes `01` and `0101` exclude roof and building
foot observations. Duplicate positions use their median height. Delaunay
interpolation produces a 4 m terrain grid with the 183.16 m absolute datum
removed. The initial reconstruction used an 18 m Gaussian road filter and gave
approximately 13.08 m of relief, including the dip before Ascari. That replaced
the old analytic slope, whose relief was 4.84 m. The full-lap revision below
separates the road profile from this park terrain raster. These sparse map observations do not
establish centimetre road accuracy or measured banking.

`monza_elevation_scene.py` applies the terrain once to the retained scene and
updates the road elevation controls. The layout pass regenerates visible walls,
runoff and their native contact data together. Ground is cut away beneath road
and runoff surfaces to prevent the coarse terrain from covering them.

The main pit roof uses DBGT observations around 193.13 m absolute height. Its
single inclined glazed storey and open roof terrace follow the architect's
[project description](https://www.archilovers.com/projects/40161/autodromo-nazionale-di-monza.html).
The lateral stand roofs use 195.48 m and 198.24 m observations. The lower seating
foredecks, partial roof coverage, white fascias and access rails follow the
[FIA Formula 2 track photograph](https://www.fiaformula2.com/Latest/5twD1lKXlZh2E3zwriejt9/what-to-watch-for-the-key-storylines-to-look-out-for-in-monza-as-the-action)
and the supplied onboard reference. Bay spacing and structural member sections
remain photographic estimates. No photograph pixels enter the assets.

The same reference corrects the straight's inner low guardrail to approximately
3.3 m beyond the road edge and identifies the paved pit-side shoulder. These are
explicit geometry corrections; the vehicle coefficients and control behaviour
are unchanged. Road, barrier and surface includes are regenerated by
`make monza-assets`, then held fixed during the decorative pass.

`regional_3d/road_grade_overrides.json` records two access-underpass reaches where
bare-ground observations lie below the straight. The racing deck interpolates
between adjacent surface samples; the lower observations remain in the source.
The deck correction includes the shoulders through 20 m from the centreline,
blending into the observed ground by 32 m and over 24 m at each end. These
transition widths are reconstruction estimates. Applying only a centreline
height offset had left false banks and pits beside the protective barriers.
Wall, Armco, advertising and fence sections interpolate their endpoint heights;
fence shearing keeps posts upright. Contact height bounds enclose each section.
The applied terrain grid is retained in the Blender file so later revisions
apply height differences instead of stacking the original warp again.
The retained OSM ways corroborate those crossings: service tunnel 34404647
crosses the pit approach near local y = -290 m; service tunnel 38168647 crosses
the straight near y = 140 m. Both are tagged `tunnel=yes`, `cutting=yes`, and
`layer=-1`. The matching low DBGT observations therefore describe access roads
under the racing deck, rather than depressions in the racing surface.

The central stand's glazed ground-floor clubhouse, cantilevered wings and
projecting press room follow a
[dated 2024 spectator photograph](https://www.gazchap.com/blog/one-off-the-bucket-list-the-italian-grand-prix/).
DBGT roof observations give the wing envelope at 198.68 m and central high point
at 203.04 m. Exact facade divisions, roof thicknesses and press-room radii remain
photographic estimates. The pit upper glazing is one storey above the garages;
the terrace has its own occupied deck beneath the independently surveyed canopy.

The hospitality frontage follows its OSM footprint, with the south and north
roof envelope constrained by DBGT points 9803866 (194.49 m) and 9803877
(201.44 m). Interpolation between those observations, the rounded south corner,
floor slabs and glazing divisions are photographic estimates from the ACI 2024
oblique view. They are not an as-built architectural survey. The same photograph
supports the mature tree band behind the main stands; individual stem locations
and 18–23 m crown heights remain estimates.

Additional reference-only source: [Monza operator 2025 hospitality brochure](https://www.monzanet.it/wp-content/uploads/2025/07/Monza_Hospitality_GP_2025.pdf).

### Full-lap road and verge reconstruction

`regional_3d/road_profile.json` retains the station, offset, altitude and DBGT
OBJECTID of each near-road ground observation used for the revised profile.
It excludes observations inside the known pit-straight underpasses. A periodic
40 m Gaussian filter follows the broad grade without copying the terrain raster’s
cell steps or isolated park banks into the asphalt. Four explicitly estimated
deck anchors at stations 0, 400, 5500 and 5650 m retain the accepted straight’s
broad elevation; they replace the old blend back into the four-metre raster,
which left a false crest after Parabolica and small ripples across the start line.
Around Serraglio the filter grows to 60 m, with 150 m smooth transitions,
softening the depression and recovery without removing them. The whole road
corridor now follows this continuous profile, including the main straight.
The anchors and filter lengths are reconstruction choices, not road survey data.

The road surface samples this longitudinal profile directly. The park terrain
meets it out to 22 m from the centreline and blends into retained surrounding elevations
by 70 m; projection onto line segments avoids nearest-vertex steps. Runoff,
shoulders, visible barriers and contact surfaces are rebuilt from the same
revision. The surveyed Serraglio depression remains: the circuit operator
identifies the crossing beneath the historic north banking on its
[track description](https://www.monzanet.it/tracciato-pista-monza/).

The supplied video at 99–103, 112–126 and 185–190 seconds provides the visual
check for continuous verges at Rettifilo/Curva Grande, the Lesmos and the
Parabolica approach. It is reference-only, not a metric elevation source.
Roadside tree exports within 100 m of the circuit outside the approved straight
use the same four CC0 crown views as the accepted main-stand backdrop
(Poly Haven Tree Small 02, Rico Cilliers; retained Silverstone derivatives).
Positions, rotations and crown dimensions follow the existing authored trees;
their trunk cutouts remain beneath the replacement crowns. Horizontal aerial
cards, which appeared as flat shelves from the cockpit, are omitted there.
Unreal gives these nearby crowns a separate soft shading profile and per-tree
colour variation; the approved straight's distant backdrop keeps its existing shading.
The editable source trees are retained. Corner spectators use the
same atlas, colour variation and facing treatment as the approved main straight.

Reference-only structural checks, retrieved 2026-10-28:

- [Ponte staccata Ascari](https://commons.wikimedia.org/wiki/File:Ponte_staccata_Ascari.jpg),
  Marco Rocchi, 2015, CC BY-SA 4.0: oblique bridge and banking view.
- [Historic Monza Oval Banking](https://commons.wikimedia.org/wiki/File:Historic_Monza_Oval_Banking,_2019_Italian_Grand_Prix,_Monza,_September_6th.jpg),
  Interceptor73, 2019, CC BY 2.0: bank surface and upper guardrail.

These photographs confirm the substantial concrete structure but do not establish
the overpass's span, support spacing or thickness. Those existing dimensions
remain reconstruction estimates; photographs are not embedded in game assets.

Rebuild this pass with `make monza-lap-assets`, then export/import into Unreal
with `bash scripts/unreal.sh circuit-assets monza`. The full `monza-assets`
build also retains the revised grade and spectator treatment.

### Road-width cross-check, 28 October 2026

The [circuit operator](https://www.monzanet.it/tracciato-pista-monza/) still lists
10–12 m nominal width. The model uses that range; local transitions remain
estimates. Four new AGEA 2024 consultation sheets at stations 1350, 3400, 5250
and 5650 m did not establish systematic undersizing. Manual white-line picks
suggest approximately 10.0 m at 1350 and 11.9 m at both straight samples, with
about 0.5 m picking uncertainty. The shadowed Serraglio sample gave an anomalous
8.7 m; it is not adopted as a design constraint. These edge-line separations
must not be confused with pavement width, drainage strips, or the operator’s
nominal range. Initial picks including the pale outer shoulder were rejected
on enlarged-image review. The consultation images, pixel picks and review
remain in `build/monza-grade-width-review/`, outside packaged assets.

No width, plan alignment, car scale or shared cockpit-camera setting changed
in this grade repair. The supplied video uses a different car: more visible
front tyres and a thinner halo change its apparent scale and framing. Unmatched
video poses cannot establish a metre-width correction by themselves.
