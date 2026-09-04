# Monza rendering diagnosis

Diagnosis only, 4 September 2026. The supplied gameplay screenshots are accepted as bug evidence. No production scene, exported asset, exporter, renderer, route, or gameplay code was changed. Debug materials exist only in a separate Blender copy and diagnostic GLB under `build/forensics/monza`.

The evidence identifies both source geometry defects and renderer compatibility problems. Increasing separation everywhere would miss the reversed normals and buried markings. A Blender beauty render cannot validate any remedy here.

| Symptom | Established evidence | Attribution and limits |
| --- | --- | --- |
| Canopy stripes and missing/striped board details | The game-library probe receives a 16-bit depth buffer. Changing only depth precision to 24 bits or increasing the near plane changes the artifacts on the unchanged GLB. No duplicate canopy objects or coplanar overlapping canopy roof faces were found. | Renderer depth precision contributes. Some remaining white lines are actual canopy supports. Do not remove them on appearance alone. |
| Spotty or missing white lines | Pit-edge paint is 11 mm above the pit-lane ribbon but intersects the main crowned asphalt. The start/finish stripe also cuts through the crown. The right continuous edge line faces downward. | Confirmed source height and winding problems, with additional distance-dependent depth conflict in the renderer. |
| Dark near kerb versus brighter far kerb | `Rettifilo kerb 609` has 264 downward-facing triangles; `Rettifilo kerb 644` has 336 upward-facing triangles. GLB positions and material assignments match the source exactly. Disabling lighting in the probe restores bright white/red on the first kerb. | Confirmed source winding problem exposed by the game's treatment of backfaces. Depth precision does not correct its shading. |
| Hovering plane near grandstand | Several terrace bases float above the actual ground mesh at one end and penetrate it at the other. Their row boxes also retain coincident internal bottom faces. Object-ID captures and a 185-object suspect manifest are available. | Real source defects found. The exact object responsible for the user's cropped plane remains unconfirmed because its camera pose and track station are unavailable. |
| Green strip mistaken for a kerb | Both kerb colors survive export; separate grass and green-apron sheets have downward normals on one side. First-chicane kerbs remain above the sampled grass and terrain. | There is no evidence of a kerb material being remapped to green. The exact green pixels in the screenshot still need object identification. |

All coordinates below are Blender world metres. The game uses `(x, z, -y) * 1.445`. An object origin of zero is not a duplicate-placement test: much of this scene stores world coordinates directly in mesh vertices.

The full [suspect manifest](../../build/forensics/monza/suspects_before_debug.json) was written before assigning any debug materials. It lists dimensions, bounding boxes, connected components and large-face measurements. The [debug material manifest](../../build/forensics/monza/debug_materials.json) adds the unique material name and RGB identifier.

| Object | Bounding box minimum | Bounding box maximum | Dimensions |
| --- | --- | --- | --- |
| `Tribuna Laterale Sinistra canopy` | `(-39.350, 49.362, 12.562)` | `(-7.698, 126.534, 12.822)` | `(31.652, 77.173, 0.260)` |
| `MONZA start bridge` | `(-9.634, 10.006, 5.951)` | `(12.351, 13.839, 7.251)` | `(21.985, 3.833, 1.300)` |
| `Pit edge -1` | `(-31.857, -555.446, -1.160)` | `(24.222, 183.043, 0.457)` | `(56.079, 738.489, 1.617)` |
| `Pit edge 1` | `(-39.215, -554.660, -1.155)` | `(16.822, 182.831, 0.456)` | `(56.037, 737.491, 1.611)` |
| `Rettifilo kerb 609` | `(61.412, 605.777, 1.384)` | `(76.195, 616.335, 1.486)` | `(14.782, 10.558, 0.102)` |
| `Rettifilo kerb 644` | `(81.432, 622.202, 1.412)` | `(95.653, 641.458, 1.525)` | `(14.221, 19.256, 0.113)` |
| `tribune concrete terraces` | `(25.873, 53.854, 0.201)` | `(44.164, 126.306, 5.211)` | `(18.291, 72.452, 5.010)` |
| `Tribuna Alta Velocità concrete terraces` | `(52.210, 342.609, 0.874)` | `(73.033, 434.463, 5.884)` | `(20.823, 91.854, 5.010)` |

The geometry diagnostics compare triangle footprints and their actual plane heights across each intersection polygon. This catches a line that is above the road at one end and below it at the other, rather than trusting the nominal lift parameter.

| Surface pair | Measured vertical separation, first minus second | Finding |
| --- | --- | --- |
| `L continuous 150 mm edge line` / main asphalt | `+7.022 to +7.704 mm` | Already separated; no road crossings detected. |
| `R continuous 150 mm edge line` / main asphalt | `+7.019 to +7.721 mm` | Already separated, but all 15,448 triangles face down. |
| `Pit edge -1` / pit-lane asphalt | approximately `+11 mm` | The pit ribbon's own offset works. |
| `Pit edge 1` / main asphalt | `-24.000 to +9.820 mm` | Paint crosses and disappears beneath the main road. |
| `Pit edge -1` / main asphalt | `-14.439 to +11.068 mm` | Same problem on the other pit edge. |
| `Start finish line` / main asphalt | `-22.000 to +17.023 mm` | A two-triangle stripe spans the crown without following its interior profile. |
| `Rettifilo kerb 609` / park ground | `+24.287 to +109.016 mm` | No intersection with this ground sheet. |
| `Rettifilo kerb 644` / park ground | `+12.850 to +82.363 mm` | Above ground, but with less clearance. |
| `Rettifilo green apron 609` / itself | `-1.386 to +0.502 mm` | Seven crossing triangle pairs; a separate source conflict. |

Pit-line intersections occur at the joins with the main track; the combined bounds and gap ranges cover both entry and exit. They do not prove that every missing pixel in the supplied pit-exit screenshot comes from buried paint. Example intersection coordinates and triangle indices are in `scene_audit.json`.

The road lines come from `foundation()` and `refit_surface_details()` in [build_monza.py](../../tools/blender/tracks/build_monza.py). Pit lines use the mapped pit spline and terrain height. The main asphalt uses a crown and camber. Those are different height constructions. Kerbs come from `surface()` in [monza_environment.py](../../tools/blender/tracks/monza_environment.py): red and white are alternating material slots on one profiled mesh, with no separate color overlay or underlying kerb-base sheet.

The two compared kerbs share identity transforms, the `Track` collection, no parent, no modifiers, two valid material slots, no source UV layer, no duplicate triangles and no degenerate triangles. They differ in winding, dimensions and surrounding clearance. Each longitudinal segment is a disconnected eight-vertex component: 44 components for kerb 609 and 56 for kerb 644. Their boundaries are intentional open sheets, not a closed solid. Both export into `Red_paint 0 5 0` and `White_paint 0 5 0`; all 600 triangles match source positions and material slots. Kerb 700 also faces downward, with 252 matching exported triangles.

The exporter retains those normals. The authored-track draw disables face culling, and the lighting shader uses the supplied normal without a `gl_FrontFacing` correction. Consequently a downward-facing white kerb receives different illumination from an upward-facing one. The [lit entry capture](../../build/forensics/monza/depth24_kerb_entry_near0.05_reverse0.png) and [unlit entry capture](../../build/forensics/monza/unlit_kerb_entry_near0.05_reverse0.png) isolate this using unchanged geometry, materials, UVs and alpha discard. This is a diagnostic lighting toggle, not a proposed aesthetic change.

The duplicate scan found no coincident whole exported objects. Four duplicate-triangle groups occur in `Alboreto woodland understory` and `Lesmo_2 woodland understory`, outside the reported areas. Structural testing found coplanar intersections between the ends of `Timing gantry` and `MONZA start bridge`, within about 2 micrometres, around the bridge end faces near `(12.255, 10.403, 6.818)` and `(-9.538, 13.442, 6.818)`. These are local contacts, not an explanation for every broad board band. The front/back faces of the extruded lettering are 8 mm apart; these are thin solid geometry, not duplicate letters.

Roof faces can be large: the Sinistra canopy has evaluated triangles up to 885.12 m². Its top and bottom are 260 mm apart. The 20 mm close-parallel scan finds no overlapping canopy roof-face pairs. Its separate support rods are real geometry below and entering the canopy. [16-bit](../../build/forensics/monza/start_near0.05_reverse0.png) and [24-bit](../../build/forensics/monza/depth24_start_near0.05_reverse0.png) captures show which stripes and missing details respond to depth precision. Persistent lines are not automatically bugs.

For the floating-geometry search, the audit tested 42 terrace bases against the saved `Park ground` triangles, rather than just an analytic terrain formula. The Alta Velocità base reaches 102.840 mm above that mesh at `(52.210, 343.800, 0.874)`. Its 13 row boxes create 36 coplanar bottom-triangle overlaps. Prima Variante Esterna reaches 163.572 mm above ground at `(12.398, 630.911, 1.556)`. The smaller opposite-pit `tribune` reaches 80.683 mm above ground. The construction places each entire stand at a single centre-ground height. These gaps and internal faces exist in the source. A disconnected component count alone does not identify the screenshot plane. The [stand object-ID capture](../../build/forensics/monza/ids_stand_av_near0.05_reverse0.png) identifies a candidate in a reconstructed camera view, not the user's exact view.

The exporter audit also checked the following:

- All 2,188 GLB meshes, containing 1,295,635 triangles, have valid index bounds and finite positions, normals and UVs. All 57 selected affected objects match source triangle positions and material assignments exactly.
- No negative-determinant transform or hidden-but-exported ordinary source object was found. The exporter ignores visibility flags in general and filters by collection name, so this remains a compatibility hazard for future changes. Geometry-node placement containers have identity matrices in this scene; the exporter would ignore a nonidentity container transform.
- No evaluated non-manifold edges other than open boundaries, or inconsistent adjacent winding edges, were found in exported ordinary meshes. Entire sheets can still face the wrong direction while being internally consistent.
- Source UVs and procedural material nodes are not preserved. `emit()` derives world-coordinate projected UVs; `Writer.material()` converts viewport diffuse color and applies a generic detail texture. This is an intentional export conversion, but Blender and game shading are not equivalent.
- Road, paint, roof and grass textures are fully opaque. Only foliage and fence textures have transparency, exported as `MASK`. Source Principled alpha values are all 1.0; Blender's `DITHERED` material setting alone does not indicate actual transparency.
- The game discards alpha below 0.35, but returns the surviving fractional alpha while ordinary alpha blending remains enabled. Together with near-to-far drawing and depth writes, this is a separate cutout compatibility concern. Residual draw-order differences in foliage are not proof that every remaining pixel is z-fighting.
- Seats and tyres undergo exporter decimation; trees become three intersecting cards; fences become textured sheets; grass instances are subsampled. There are no glTF LOD extensions. A horizontal tree card is another possible source of an apparent floating plane; it is not identified as the cause of the submitted crop.
- Source coordinates span kilometres and exported nodes have no additional transforms. No nonfinite or anomalous affected-object scale was found. The shader uses `mediump` fragment precision. That is recorded as a portability concern, not established as the cause here.
- `game.cpp` skips the procedural road and props when the authored track loads. The screenshots are not explained by simultaneously drawing the fallback procedural road.

The renderer experiment uses the same installed raylib/SDL libraries, the extracted game shader, the game lighting constants, the 1.445 model scale, the same four-sample MSAA window request, the authored-track culling calculation and the same sort order. The local context is Mesa Intel Iris Xe, OpenGL ES 3.2, with a measured default 16-bit depth buffer. Raylib defaults to near `0.05`, far `4000` and `LEQUAL`; the SDL setup does not explicitly request a depth size. The probe varies only the requested depth buffer, near plane, draw order or lighting output for each controlled comparison. Camera positions are reconstructed from the survey. Its flat sky, missing car/HUD and lack of gameplay simulation mean these are renderer reproductions, not pixel-identical reruns of the user's screenshots. The user's device was not queried.

At the start-straight probe camera, reversing mesh draw order changes 37,866 pixels by more than eight RGB levels with 16-bit depth, versus 2,332 with 24-bit depth. These whole-frame counts include foliage and are sensitivity measurements, not counts of defective pixels. The corresponding fractions are 4.109% and 0.253%.

The [recorded measurements](monza-evidence.json) retain the source hashes, affected geometry, export comparisons and draw-order counts. Full raw outputs stay in `build/forensics/monza`. No Blender render was used to claim that an in-game problem was corrected.

Reproduce from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 uv run --no-sync python tools/diagnostics/monza_scene_audit.py
uv run --no-sync python tools/diagnostics/monza_export_audit.py
uv run --no-sync python tools/diagnostics/monza_terrace_audit.py
uv run --no-sync python tools/diagnostics/monza_debug_copy.py
uv run --no-sync python tools/diagnostics/run_monza_probe.py
FORENSICS_DEPTH_BITS=24 uv run --no-sync python tools/diagnostics/run_monza_probe.py --prefix depth24_
FORENSICS_DEPTH_BITS=24 uv run --no-sync python tools/diagnostics/run_monza_probe.py --prefix unlit_ --unlit
FORENSICS_DEPTH_BITS=24 uv run --no-sync python tools/diagnostics/run_monza_probe.py --asset build/forensics/monza/debug_export/monza.glb --prefix ids_ --unlit
uv run --no-sync python tools/diagnostics/monza_evidence.py
```

The debug `.blend` contains the complete source scene with suspect material replacements. Its diagnostic GLB contains only the suspects and deliberately omits non-suspects and instances; it must not replace the runtime asset. The global duplicate comparison does not expand geometry-node instances. Arbitrary enclosed faces in every solid are not exhaustively classified; terrace bottoms and affected roofs receive targeted tests. No screenshot-precise identification of the floating plane or green strip is claimed.

The next decision can separate renderer depth handling, source winding, paint/road intersections and terrace grounding. None of those remedies has been applied. Exact identification of the remaining screenshot pixels needs a game camera position or an object-ID capture at that location.

Validation completed: the full source scan, GLB comparison, terrace/ground measurements and 84 renderer captures ran successfully. Synthetic duplicate, coplanar, separated-plane and crossing-plane checks passed. Python lint/compilation and C++ syntax checks passed. SHA-256 checks confirm the source Blender scene, runtime GLB, runtime metadata and generated driving route are unchanged.
