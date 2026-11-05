# Las Vegas layout and landmarks

The November 2026 revision follows the FIA 2025 circuit map V2, issued on
19 November 2025. The retained OSM circuit relation supplies street registration.
The FIA map supplies corner order and the shape of the temporary Harmon section;
it is not treated as a metric engineering survey.

The old source loop included a 20 m lateral jog on Sands before the broad
T10/T11 bends. It also replaced T14–16 after the Strip with one diagonal turn.
[The correction recipe](../Attribution/Sources/lasvegas/layout-corrections.json)
removes that Sands jog and authors rounded T14 left, T15 right and T16 left
transitions onto the mapped Harmon Avenue axis. The Sphere chicane and the broad
Sands bends remain. The plan is resampled before road heights, widths, contact
triangles, barriers and scenery are generated. Its final lap length remains
6,201 m. The explicit turn table now registers all 17 official corner names.

The road controls are estimates registered to the existing street data. Source
origin, units, smoothing, normalization and the elevation datum are recorded in
[provenance](../Attribution/Sources/lasvegas/provenance.json). The short chicane
requires an 18.6 m audit window to distinguish its reversing turns; the previous
111.6 m window combined them into one left turn. A regression checks those
reversals and limits heading changes along the Sands approach.

[Landmark profiles](../Attribution/Sources/lasvegas/landmark-architecture.json)
retain the OSM feature IDs, individual facade choices, roof styles and height
estimates. Palazzo, Venetian, Bellagio, Paris, Wynn, Encore, Cosmopolitan,
Planet Hollywood, Flamingo, Treasure Island, Caesars, LINQ, Horseshoe and Elara
have separate profiles.
Classical towers have projecting bays and cornices, Paris has a mansard roof,
Cosmopolitan has balcony slabs and glass rails, and Wynn/Encore retain their
curved mapped footprints with bronze glazing and narrow horizontal bands.
Bellagio also has a rounded central dome. Entrance arcades and road-facing
names add detail at cockpit height. These are
original simplified models in the game's existing style, not scanned buildings.
The reference clip and hotel photographs supply observations; their pixels are
not shipped as artwork.

Hotel entrance signs, planters, marshal booths and sector signs sit outside the
physical track barriers. Gantry supports account for each side's paved shoulder.
Braking boards and widened apron stations follow the revised corner positions.
Facade-only illumination keeps stone walls readable below the window and crown
brightness. New original race-week panels vary by sector, and covered pedestrian
bridges have visible frame bracing. The car, camera and driving controls are retained.
A fixed light-field coordinate frame keeps the Las Vegas material copies aligned
when fixture locations change.

`make lasvegas-assets LASVEGAS_PYTHON=<python-with-Pillow>` rebuilds the native
assets. The importer runs four serial mesh batches to stay within the guarded
memory budget, then reopens every saved mesh in a fresh editor process.
`make lasvegas-check` checks the generated geometry, types and lint. Use the
same Python environment for both commands. Packaged cockpit views and a full
live lap are required for visual acceptance; native checks alone do not establish
that result.
