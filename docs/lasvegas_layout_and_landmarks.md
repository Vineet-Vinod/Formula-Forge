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
requires a short audit window to distinguish its reversing turns; the previous
111.6 m window combined them into one left turn. A regression checks those
reversals and limits heading changes along the Sands approach. The later curve
revision filters the angular street controls before interpolation, uses 12,288
native samples and local geometric normals, and gives widths independent quintic
transitions. The regression checks consecutive centre and painted-edge chords;
adding samples alone had preserved the original corner kinks.

[Escape areas](../Attribution/Sources/lasvegas/escape-areas.json) extend the
incoming streets at T1, T5, T12 and T14. A localized blue apron follows the outside
of the Sphere chicane. These are bounded reconstructions from the onboard and
operator descriptions, not measured barrier footprints. Their union with the
narrow road deck supplies the visible pavement, native contact and closed outer
protection. Entrances stay open; far ends use tire stacks. The terrain is clipped
to that same union so it cannot cover the escape-road floor. White-line timing
limits exclude the extra paving.

[Landmark profiles](../Attribution/Sources/lasvegas/landmark-architecture.json)
retain the OSM feature IDs, individual facade choices, roof styles and height
estimates. Palazzo, Venetian, Bellagio, Paris, Wynn, Encore, Cosmopolitan,
Planet Hollywood, Flamingo, Treasure Island, Caesars, LINQ, Horseshoe and Elara
have separate profiles.
Classical towers have projecting bays and cornices, Paris has a mansard roof,
Cosmopolitan has balcony slabs and glass rails, and Wynn/Encore retain their
curved mapped footprints with bronze curtain glazing, dipped roof lines and
horizontal illuminated bands. Curved facade lettering follows the building skin.
Bellagio also has a rounded central dome. Entrance arcades and road-facing
names add detail at cockpit height. The Paris balloon has a rounded body and gold
ribs; the casino podiums have shop glazing and arcades. The Veer pair has
opposing 5 degree inclines, staggered yellow/clear glazing and horizontal louvers.
Crystals has a low glazed retail body under reconstructed folded metal roof
shards; its 30 m peak is not used as a uniform wall height. The adjacent museum
frontage also uses large retail glazing. The broad Horseshoe
footprint stays a low podium rather than becoming a solid tower. These are
original simplified models in the game's existing style, not scanned buildings.
The reference clip and hotel photographs supply observations; their pixels are
not shipped as artwork.

The roadside hotel name boards have been removed. Marshal booths, palms,
gantries and braking boards sit outside the physical paved areas. Braking boards
follow the revised corner positions.
Facade-only illumination keeps stone walls readable below the window and crown
brightness. New original race-week panels vary by sector, and covered pedestrian
bridges have visible frame bracing. The car, camera and driving controls are retained.
A fixed light-field coordinate frame keeps the Las Vegas material copies aligned
when fixture locations change.

Install `tools/requirements-lasvegas.txt` in the authoring Python environment.
`make lasvegas-assets LASVEGAS_PYTHON=<authoring-python>` rebuilds the native
assets. The importer runs four serial mesh batches to stay within the guarded
memory budget, then reopens every saved mesh in a fresh editor process.
`make lasvegas-check` checks the generated geometry, types and lint. Use the
same Python environment for both commands. Packaged cockpit views and a full
live lap are required for visual acceptance; native checks alone do not establish
that result. Current evidence is in
[the curve revision validation](lasvegas_curves_validation.json).

The barrier follow-up bakes both endpoint heights into
`Attribution/Sources/lasvegas/barrier_heights.bin`. Boundary interpolation uses a
small positional tolerance when selecting the escape deck. This prevents an
edge point from alternating between the street height and the higher escape
plane. Visible walls and fences follow those endpoint heights, with shared
mitered corners joining the concrete, sign faces and fence overhangs. Native
collision encloses the full sloped wall rather than its lower endpoint alone.

[Trackside placement](../Attribution/Sources/lasvegas/trackside-layout.json)
records the video-based curb extensions and shallow beveled curb profile.
Red/white transitions split at exact metre boundaries. The Sphere approach uses
blue left-side and black right-side protection before the blue apron. The Strip
has closer palm spacing, with placements excluded from mapped building
footprints. The mapped Wynn employee parking building uses open decks and
concrete piers. Oversized freestanding road-name/Sphere labels were removed;
track-spanning race gantries remain. These changes preserve the road alignment
and widths accepted in the smoothness review.
