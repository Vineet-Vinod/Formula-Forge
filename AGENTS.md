# Formula Forge

This project is an open-source formula racing game. The following parts
of the game are not to be altered without an explicit request:
- Drivability
- Car handling
- Speed
- Gear shifts
- Core gameplay behavior

The main things to focus on are related to game design.

## Guidelines

- Commit regularly
- Use the Blender Python API using `uv` to make the 3D graphics
- For circuit sources, authoring, validation and game integration, follow [map.md](map.md).

## Track distance boards

For new or revised maps, follow [the braking-marker policy](docs/track_braking_markers.md).
Use centreline distance to corner entry, choose the sequence from the usable approach
length, group linked corners, and verify visibility in the game renderer.
