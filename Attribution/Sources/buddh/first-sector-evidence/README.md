# Buddh first-sector dimensions and surfaces

The legal-width reconstruction covers native 304 to 2680 m. It starts at the retained broad T16 apex, narrows through the pit straight and T1/T2, flares into T3, contracts on its exit and expands progressively into the retained broad T4 approach. Separate surface roles cover the complete T16 and T4 escapes over approximately 230 to 2820 m.

`first-sector.json` is the authored source profile. The legal widths are architectural estimates with stated manual allowances, not a surveyed white-line schedule. The generic construction range is retained as historical context, not reused as a legal-road minimum. Width, flat paving, raised curb, gravel and grass are separate quantities.

| Region | Native station / nominal full legal width, metres | Manual allowance |
| --- | --- | --- |
| T16 rollout | 304 / 20, 340 / 15 | 3 m at apex, 2 m on exit |
| Pit straight and T1 | 470 through 1110 / 15 | 2 m |
| T2 and uphill approach | 1165 / 14, 1250 / 13, 1320 / 14 | 2 m |
| T3 entry | 1380 / 21, 1400 / 23, 1415 / 23 | 2 m |
| T3 apex and exit | 1429 / 18.5, 1445 / 14, 1460 / 14, 1530 / 15 | 2 m |
| Back straight | 1800 through 2480 / 15 | 2 m |
| T4 flare | 2530 / 16, 2580 / 20, 2620 / 23, 2680 / 25 | 2.5 to 3 m |

Shape-preserving cubic interpolation keeps continuing flares smooth without a false zero-slope shelf at every control. Native compilation adds knots only inside the correction and retains every literal old outside control. No centerline, elevation, bank, car, camera or shared tuning change is part of this reconstruction.

## Primary images and registration

The two `imagery-*` folders retain original primary tile bytes, acquisition metadata and exact native-normal sample positions from 77 section records per epoch, including repeated controls. Their source indices preserve the original pre-correction native rows, literal WGS84 query positions, service requests and image hashes. Those old native width values are comparison inputs, not surveyed dimensions.

| Acquisition | Primary publication | Display spacing | Provider sampling | Reported absolute position accuracy |
| --- | --- | --- | --- | --- |
| 2018-10-12, WV02 | Esri Wayback 2020-01-08 | About 1.05 m at z17 | 0.5 m | 8.47 m |
| 2021-03-02, WV03 | Esri Wayback 2022-01-12 | About 0.526 m at z18 | 0.31 m | 5 m |

Publication dates are distinct from acquisition dates. Both acquisitions precede the 2023 MotoGP variant. The current MotoGP headline width is not used to resize the earlier Formula 1 layout. A 2014 publication was rejected because its underlying acquisition was 2010 construction imagery.

Nine distributed straight controls give approximate image comparison translations of east +0.44 m / north -0.37 m for 2018 and east +0.74 m / north -0.59 m for 2021. Midpoint residual RMS is about 1.10 m. Local cross-epoch feature ties differ: near T1 they are about 0 m east / +1 m north; at T3 about +3 m east / -4 m north. Public-ground, corner and exit features agree locally. These are diagnostic registrations, not surveyed control points. They do not justify moving the native centerline.

Relative image width is stronger evidence than an absolute edge displacement on a curved centerline. White paint is below the display-pixel spacing and merges with curb/apron paint in places. The 2 to 3 m manual full-width allowances include that reconstruction limit; they are not statistical error bars. T3 side placement retains local uncertainty even though its span and entry/exit shape are supported.

The primary construction account reports 18 to 25 m of paved circuit width, while ABB's venue summary reports 18 to 20 m. Neither is a station-resolved legal-white-line survey. They cannot establish 25 m of legal road at every hairpin. The retained broad T4 approach remains consistent with the historical image and supplied views.

- [Construction supplier account, RoadNews 24](https://www.consultanthart.com/www/pdf/RoadNews_24_en_India.pdf)
- [ABB Contact India 3/2011](https://library.e.abb.com/public/bade2cb5c7c3d0e94825797e0062298a/Contact_3_11_India.pdf)
- [FIA 2013 circuit plan](https://www.fia.com/sites/default/files/external_archive/node3786/16-india-circuit-print.pdf)
- [Tilke portfolio](https://tilke.de/wp-content/uploads/2024/12/2024-Portfolio.pdf)

## Supplied driving reference

`supplied-reference.json` identifies the existing `Saved/Refs/india.mp4` by hash and records the reviewed original times. The edited game's exact event/year is unverified. The original 1920 by 1080 frames establish appearance and edge roles, not metric survey accuracy.

The 112 to 128 second sequence establishes T16 rollout, the pit straight, T1 and T2. The 130 to 136 second sequence shows T3 entry, apex and exit. The 149 to 154 second sequence establishes the T4 approach. Original 200 to 204 seconds confirms the T16 sequence. The official native registration is T16 near 304 m, T1 right at 1041 m, T2 left at 1165 m, T3 right at 1429 m and T4 right at 2719 m.

No source-image or video pixels are copied into a game texture. Primary tiles are retained as reference evidence with their provider metadata and attribution, without claiming an open imagery licence. Generated scene geometry and paint patterns are original authoring.

## Surface interpretation

T1 has a flat green and white striped outside escape, separate from its inside raised curb. The complete corrected 1000 to 1080 m T1 curb path is retained. A left braking curb precedes the corner. T2 has a left curb and grass beyond a narrow drain.

T3 has a blue paved crescent adjoining the legal edge, farther tan gravel, a right raised curb, a narrow inner green strip and the grass island. The old gray block and narrow blue strip 15 m beyond the legal edge did not match the reference. The blue crescent's outer width is reconstructed to about 3 m; the gravel reach to about 4 m. Exact curb endpoints and the T3 exit treatment remain estimated.

The existing 1.2 m curb width and 55 mm height are retained reconstruction dimensions, not survey observations. Flat painted escape is not raised as a broad curb. The source producer's small downward road/curb faces are corrected by the separate shared up-facing ribbon fix.

New corrected T1 tops retain their plans and attached UVs, but use a continuous triangulated native-road grade below the existing 21 to 55 mm radial rise. This removes nearest-segment height jumps inside very narrow triangles. It changes neither native road elevation nor retained old faces. Remaining numerical top fragments may be omitted only when their projected area is at most 0.000005 square metres and their altitude at most 0.03 mm. Both limits are enforced; a meaningful near-vertical top raises an error. The underlying role reconstruction fills the omitted plan rather than leaving a ground hole. These are numerical geometry repairs, not additional survey measurements.

## Reproducible baseline and ground

`first-sector-baseline.json` contains literal old native width and shoulder controls and the active `kBuddhSceneRunoff` minima. The inactive `kBuddhRunoff` array is not the runtime source. Native float replay and the exporter's decimal boundary reproduce all 8,192 retained scalar rows exactly, with hash `77a1b73f9a6af5bd78ea65c5d11e30a8453b03f4f46f7e1eff69f8975cdb6e20`.

Rendering first uses that retained source frame, preserving original outside terrain traversal, architecture, pit surfaces, stands and planting in world position. One post-terrain operation clips actual emitted local rows, retains complete untouched bytes and interpolates original attributes along split edges. It then installs the actual compiled legal profile. It never reads a private packed cache in production or alters the global terrain union.

The pit profile remains in the retained rendering frame. Its inner/outer lane coordinates stay 11.21/33.5 m. Reapplying new-road-relative offsets to that old rendering phase would shift it twice. Old corrected-curb ground exclusions are recovered from the original bounded verge/field recipe, with explicit joins. Native terrain and all unrelated data remain unchanged.

Actual local paved, gravel and grass planes are separate from legal track limits. Native effective shoulders require compensation after runtime minima, not only in raw controls. Generic full-shoulder asphalt/gravel classification must not cover restored grass. Native driving-height support, true contact class and rendered paint are verified separately with unbuffered packed barycentric queries. Shared friction and query tolerances stay fixed.

The contact export retains the actual original floor-owner plane before final render and native float packing. A 0.3 mm bevel around each contact triangle closes numerical edge gaps; bevel corners avoid acute-angle spikes. Heights remain on that original plane. Both rendered vertex deviation and unbuffered native coverage are checked. Reference faces with projected area at most 0.00000001 square metres are numerical collapses, not measurable ground area. The exporter follows the existing native load-area requirement and reports omitted small triangles separately. This contact treatment does not move rendered rows, road elevation or the terrain field.

Compact paved and gravel classification is triangulated from the exact union of actual source/rendered footprints. It receives no height padding. Grass keeps the existing no-hit classification. Ground-height triangles are separate. Small encoding islands may receive height-only support within 1 mm of their actual footprint. One pinned grass island near native east 264.8793 m / north -107.0376 m needs 1.1 mm: 1.05 mm cannot produce a float triangle above the unchanged loader minimum, while 1.1 mm can. This bound is an encoding repair on the verified owner plane, not a new terrain observation or a change to visible paving. The source-frame and original-row guards remain required.

## Acceptance boundary

Luna accepted the frozen source proposal for integration review on 14 November 2026. Recipe hash `9d1718cb524f412151e6e180ee87bee33c99e5d076f37d637bf3879e90e70bb8`; private source proof hash `d4ad0e20110f649934a3af5bb9c9830cc13d0517a678ce0f6971823a931c3882`.

That decision does not establish compiled contact, frame rate or cooked visual acceptance. Production still requires effective-shoulder checks, unchanged outside rows/attributes/native fields, exact packed contact coverage and fresh original approach/apex/exit views plus a complete live lap. The rest of Buddh's dimensions and scenery retain their separate existing source limitations.
