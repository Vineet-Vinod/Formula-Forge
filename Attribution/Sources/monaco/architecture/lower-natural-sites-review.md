The 2019 Monaco Government orthophoto supports two small planted sites south of
the previously qualified ravine. These are manual land-use interpretations with
about 1–2 m boundary uncertainty. They supply no tree species, substrate height
or terrain survey. The source registration and explicit OSM/IGN exclusions are
retained in `lower-natural-sites.json`; its source-proposal hash pins the finite
Luna High review. No reference-image pixels are used in a material.

The permitted polygons cover 11.7902 and 38.1541 m² after the actual source-frame
registration and exclusions. Buildings and IGN roofs have a 1.5 m margin;
walkways, actual racing/protection geometry and extra corridors have a 2 m
margin. The ambiguous Casa Mia eave hit remains excluded. The first site's
existing surface role remains intact. Only 38.1541 m² of exposed Runoff in the
second canopy parcel changes to `MonacoNaturalGround`. Existing precise ivy,
rock and paved roles are preserved.

Full generation changes only `Tile_Street_m1_01`; all other scene payloads and
native physical data remain exact. Four original Runoff faces become 53
fragments on their original planes. An independent owner comparison measures
5.245 µm maximum packed height error, 4.779e-7 normal error and 2.521e-6 outside
UV error. Plan coverage is exact after F32 encoding. One outside numerical ear
encodes two identical vertices and has zero area; it cannot render or create a
finite hole. Other material rows remain byte-exact. The full scope and attribute
receipts are `monaco/lower-sites-source-scope-proof.json` and
`monaco/lower-sites-attribute-proof.json` in the 2026-11-14 review archive.

These source checks permit native integration. Fresh cooked driving views must
still establish material tone and whole-route appearance. This change does not
close the separate uncertain upper pale apron or any unresolved property role.

The 15 November follow-up adds a third finite site: a photographed eastern
rock/vegetation spur above the curved path. Its 27.4495 m² interpreted outline
has about 1 m edge uncertainty. Existing exclusions reduce it to 21.5405 m²;
only 13.4245 m² still using Runoff changes appearance. The private replay splits
14 old faces and preserves all 16,658 other-material rows exactly. Original
height planes and interpolated normals remain; fragment UVs retain the existing
8 m world mapping within float32 precision. The exact current 240 m camera ray
at pixel (350,159) identifies this spur. The adjacent unresolved (405,154) ray
is excluded. See `east-spur-source.json` for registration, source pixels and the
Luna High source decision. Native import and fresh cooked review remain required.
