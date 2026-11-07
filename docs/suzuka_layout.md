# Suzuka layout

The drivable circuit is the current 5.807 km Grand Prix loop, clockwise, with
the 18 named corners from the pit straight through the S curves, Dunlop,
Degner, 110R, the hairpin, 200R, Spoon, 130R and the final chicane. Station 0
is the mapped point nearest the published start at 34.8433 N, 136.5409 E.

The plan is OpenStreetMap relation 284570, scaled from 5,809.6 m to 5,807 m.
The road heights are the Geospatial Information Authority of Japan 5 m mesh,
retrieved 2026-11-07, with two smoothing passes. Relief on the racing line is
40.6 m. The steepest climb on a 64 m window is 7.6% at about 1,508 m, on the
way up to Dunlop. The low point is between Turn 1 and Turn 2, and the high
ground is through Spoon.

The back straight is the bridge, at about 4,651 m, over the Degner curves at
about 2,272 m. The ground mesh drops into the underpass, so that notch is
filled and the deck is held 6.2 m above the lower road. Two other narrow holes,
on the Dunlop crest and before the final chicane, are raised to the surrounding
road because they are culverts in the ground model rather than the racing
surface. The lower road is not lifted.

Widths are estimates: 15 m on the two straights and 12–14 m in the corners.
Gravel is on the outside of Turn 2, Degner, the hairpin, Spoon and the final
chicane. Named grandstands, the pit building and the west control tower use
OpenStreetMap footprints with estimated heights. The Circuit Wheel is an
original 48 m wheel at 34.845979 N, 136.538821 E. Its top is about 51 m above
the ground, from the published note that the ride looks down from about 50 m,
not from a measured diameter.

`Saved/Refs/japan.mp4` is a commercial game replay of the Japanese Grand Prix.
It was used to check the order of the scenery. Its pictures and meshes are not
in the game. The cockpit scene is native tiles in `Content/Generated/Japan/Track`,
built with the Interlagos and Monza materials. Regenerate with
`python3 tools/suzuka_scene.py`, then `bash tools/unreal.sh python tools/build_suzuka.py`.

Widths, stand heights and the wheel size are estimates. There is no orthophoto
registration and no packaged cockpit lap in this revision.
