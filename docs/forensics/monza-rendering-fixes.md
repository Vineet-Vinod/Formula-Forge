# Monza rendering repairs

The rebuilt game requests a 24-bit depth buffer and retains the original camera clip planes. The game confirmed 24 bits in its actual Monza capture run. Cutout fragments now become opaque after the alpha test, so foliage and fence transparency no longer depend on fractional blending while writing depth.

The Blender repair corrects the affected upward-facing sheets, conforms pit-edge and start/finish paint to the asphalt with a nominal 8 mm clearance, partitions the self-overlapping Rettifilo apron, recesses coincident gantry end caps by 5 mm, and extends stand foundations below the terrain while removing overlapping bottom faces. The strip and kerb generators now account for mirrored winding. Finalizing a regenerated Monza scene applies the same repairs.

All 42 stand meshes were traced to their mapped grandstand footprints. The largest extension beyond the mapped bounding rectangle is 1.442 m, consistent with the authored row layout. No stand-sized geometry stretched from another part of the map was found. The suspect seen in the reconstructed side-view object-ID capture belongs to `Tribuna Alta Velocità concrete terraces`. Stand bases were repaired without changing their horizontal placement, seating or roofs. The user's exact cropped camera view still needs their in-game confirmation.

Validation:

- 46 relevant surface sheets face upward.
- Both pit-edge markings and the start/finish stripe remain at least 5 mm above overlapping asphalt triangles after Blender's float conversion.
- The repaired apron has zero measured positive-area self-overlap.
- All 42 stand foundations terminate below the terrain and have no bottom faces.
- A second repair pass makes no further changes.
- Asphalt vertex positions and `src/track_data/monza_survey.inc` are unchanged.
- Runtime index, source hash and native route alignment checks pass.
- Asset loading, grid alignment, vehicle, collision and track-catalog tests pass, 5/5.
- The actual game produced 72 Monza tour captures. The inspected pit-straight and chicane captures show the restored right-hand edge line and red/white kerb shading.

Detailed local measurements are under `build/forensics/monza-fix/`, including `verification.json`, `stand_footprints.json`, the original scene backup and the after-repair scene audit. The full gameplay suite was not rerun; the previously documented AI/handling benchmark failures are not claimed to be resolved by these visual changes.

To repair a freshly authored scene, export and rebuild:

```sh
uv run --no-sync python tools/blender/tracks/repair_monza_rendering.py
uv run --no-sync python tools/blender/tracks/export_monza_runtime.py
make
uv run --no-sync python tools/blender/tracks/verify_monza_rendering.py
uv run --no-sync python tools/blender/tracks/verify_monza_runtime.py
```

Start the rebuilt game with `make run` and select Monza.
