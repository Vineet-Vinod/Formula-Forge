# Monza reconstruction QA

The saved scene passes the geometric checks in `qa/final_validation.json`.
All 1,932 lap frames were reviewed, and the crossings corrected during that
review were rendered and checked again.

## Geometry

The plan is projected from the WGS84 ellipsoid and normalized by a single scale
factor of 0.999049281. Horizontal length is 5,793.000 m; spatial length is
5,793.010 m. The clockwise centerline has no nonadjacent segment crossings.
The road has 69,516 vertices and 61,792 quads, with two boundary loops and no
nonmanifold shared edges. Its modeled width stays between 10 and 12 m.

The circle fits are 335.2 m for the mapped Biassono segment, 73.8 m for Lesmo 1
and 34.0 m for Lesmo 2. The guide gives approximate values of 300, 75 and 35 m.
Biassono includes radius transitions; it was not forced into a perfect circle.
Local minimum curvature radii are recorded separately in `geometry_qa.json`.

Section boundaries divide the environment work and include braking approaches.
They are not FIA corner start/end definitions. Negative heading changes are
clockwise, viewed from above.

| Section | Start m | End m | Length m | Heading change | Width m |
|---|---:|---:|---:|---:|---:|
| Start finish | 0.0 | 482.0 | 482.0 | 1.1° | 11.7–12.0 |
| Rettifilo | 482.0 | 731.5 | 249.5 | 20.1° | 11.0–11.7 |
| Curva Grande | 731.5 | 1670.0 | 938.5 | -100.9° | 11.0–11.0 |
| Roggia | 1670.0 | 2088.5 | 418.5 | 14.0° | 10.6–11.0 |
| Lesmo 1 | 2088.5 | 2443.0 | 354.5 | -102.9° | 10.1–10.6 |
| Lesmo 2 | 2443.0 | 2669.5 | 226.5 | -66.2° | 10.0–10.1 |
| Serraglio | 2669.5 | 3480.7 | 811.3 | 12.0° | 10.0–10.9 |
| Ascari | 3480.7 | 3936.2 | 455.5 | 41.7° | 10.9–11.0 |
| Back straight | 3936.2 | 4626.7 | 690.5 | 1.4° | 11.0–11.0 |
| Alboreto | 4626.7 | 5793.0 | 1166.3 | -180.2° | 11.0–12.0 |

The guide's 1,194.4 m start straight includes part of the mapped Alboreto exit.
An OSM way name is not a survey definition of a tangent point. The back-straight
way measures approximately 940.5 m between its mapped endpoints.

## Section review

Each section was built in lap order and rendered from 1.2 m above the road and
from an elevated camera. The cameras cover the pit straight, Rettifilo,
Biassono, Roggia, both Lesmos, Serraglio, Ascari, the back straight and Alboreto.
The section JSON files record the staged checkpoints. The final validation JSON
is authoritative for the complete saved scene.

Corrections made during those reviews:

- Reduced overexposure before evaluating surface materials.
- Moved the pit-straight camera to show the garages and main grandstands.
- Replaced opaque canopy masses with overlapping leaf geometry.
- Increased planting density within mapped woodland and preserved inner clearings.
- Resampled Armco along the barrier path so beams meet through bends.
- Kept the inside barrier open only where an offset would fold through a tight chicane.
- Blended runoff back to the park grade rather than extending road camber across it.
- Partitioned overlapping runoff polygons and excluded the road and kerb aprons.
- Trimmed legacy oval surfaces where they share the active Grand Prix straight.
- Refit the painted lines and kerbs after refining the road cross-section.
- Removed grass tufts from mapped gravel traps.
- Added the aerial-inferred back-straight tree belts and marked their lower confidence.
- Clipped seven mapped park-path meshes away from the racing road after the lap
  review exposed dirt strips at crossings. The added mesh audit reports zero
  path area over the road.

Saved-mesh checks find no runoff area over the active road. The summed runoff
polygon overlap after Blender's coordinate quantization is 0.00145 m² across
approximately 66,370 m², below the 0.1 m² numerical tolerance. There are no
visible overlapping slabs in the corrected Alboreto elevated render.

The minimum generated Armco clearance from the road edge is 4.68 m. The pit wall
is checked separately by its authored placement. Measured overhead clearance at
the bridges is at least 5.74 m above the road. Driver cameras are 1.2 m above the
surface. All tree instance origins meet the common terrain height function.

## Continuous pass

All 1,932 frames were inspected in 21 consecutive-frame sheets. The corrected
park-path crossings were rendered again over their approach and departure
intervals and checked at 1,728, 3,291, 4,131, 4,423.5 and 5,398.5 m. The final
video and frame sheets contain those corrected frames. The crossing strips are
gone, and the asphalt remains continuous through each location.

The pass also covered the legacy-bank bridge, both chicanes, the Lesmo turns,
Ascari, Alboreto and the return through the pit straight. No further road
occlusions or abrupt changes at the ten environment boundaries were observed
at the inspection resolution. Repeated asset families remain identifiable on
close inspection; tree rotation, scale, age and density vary within the mapped
woodland. No claim is made that every small detail is unique.

The inspection camera is keyed at every frame over one closed lap. There are
1,932 frames at 24 fps, spanning 80.5 seconds. The low-resolution 320 × 180
inspection is intended to reveal geometry and scenery discontinuities. Use the
larger section renders to assess materials and small object details. The camera
uses the centerline and constant station increments; it is not a physical car
simulation or an optimized racing line.

## Accuracy limits

No measured terrain raster, camber survey or current orthophoto was provided.
The vertical grade, 35 mm crown and crossfall up to 0.4 percent are restrained
artist estimates. They must not be interpreted as measured Monza elevations.
Mapped footprints anchor the buildings and grandstands, but facade details,
canopies, heights and seat layouts remain generalized. Individual trees and the
legacy bank profile are also estimates.

Materials are procedural and use metre-based coordinates. This avoids external
texture dependencies but does not reproduce unique photographic stains or every
repair at the real circuit. Exact 2026 temporary infrastructure, sponsor boards,
crowds, hospitality trucks and the current state of woodland recovery have not
been certified from the reference set.

The artifact is a reference-grounded Blender reconstruction, not a
photogrammetric digital twin. Runtime game assets and driving behavior are
unchanged.
