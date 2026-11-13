# Pending Sainte-Dévote hillside property evidence

Unapplied research checkpoint from 2026-11-13. These files are not consumed by the current scene generator and do not change package `219ac9a7`, any native road/profile, terrain or building asset.

The source is IGN BD TOPO building geometry, acquired through the official GeoPF WFS. The complete 34,369-byte response contains 27 features. The request file retains its exact public URL, Lambert 93 query bounds and uncompressed payload SHA-256. Attribution and licensing follow the existing [Monaco IGN provenance](../../hillside-architecture-provenance.json). Footprint registration uses the existing OpenStreetMap contributors data under ODbL1.0. Feature records state 2.5 m plan and 1.5 m vertical precision; decimal coordinates do not imply finer survey accuracy.

- `ign-local-buildings.json.gz` is the complete original response, gzip-compressed without changing its JSON payload.
- `ign-local-buildings-request.json` records the exact query and payload identity.
- `property-source-matches.json` records measured component overlaps with the existing named OSM properties, literal 3D roof-edge ranges and separate source height fields.

Casa Mia `94399990` currently uses an unverified 6.8 m default. Three measured components jointly cover 89.34% of its retained ground body and have boundary roof elevations 36.5–55.3 m absolute. Villa Marie Antoinette `94401978` currently uses 10.2 m from three tagged storeys; a 94.23% matched component has 17.9 m source height and roof 54.8–56.9 m absolute. These are concrete dimension discrepancies to resolve, not evidence for flattening the real hill.

Casa Mia's middle component has roof edges 44.1–52.7 m and must retain its complex envelope. Rose de France `94399519` has two partial matches totaling 81.67%; its separate maximum-roof fields disagree with some actual boundary heights. The small church component's 2.4 m height is not accepted as a complete church measurement. Do not apply a uniform maximum-height box or treat roof outlines automatically as ground walls.

A read-only raw-envelope test indicates that the Casa Mia and Villa Marie Antoinette components would occlude three of six tested gray hillside rays, but would leave the main lower 200 m gray face visible. Any repair needs matched forward reference and property exterior evidence for roof interpretation, facade articulation and materials. Keep the real IGN ground, upper streets and racing geometry unchanged. The local 226.179 m² mapped wood is already completely rendered as Grass; extending it across the gray hill is unsupported.

The historical visual hold for the opening view was superseded by Luna High's matched-image visual PASS. This newly acquired dimension evidence is an independent source-completion concern, pending Luna's final adjudication. It does not relabel earlier captures or imply that the pending property repair has been applied or reviewed.
