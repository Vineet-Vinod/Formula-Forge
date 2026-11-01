# Shared foliage

`foliage.png` and `cards.json` are the three orthographic projections of each
of the twelve `LIB_Tree_*` meshes in the project's completed Monza scene.
They contain project-authored geometry rendered to transparent cards, with
no satellite or third-party tree photography. They use the repository's
MIT licence, copyright © 2026 Vineet-V; see the root `LICENSE`.

The non-Monza Blender scenes retain the editable leaf meshes. Their GLBs use
the matching cards to keep the runtime memory cost small. The signature is
SHA-256 of the twelve tree prototypes' mesh, transform and material data,
plus the Monza world shader and fixed atlas bake settings. It is checked
before generating a circuit. A changed tree or bake input requires a fresh
bake and visual comparison; editing unrelated Monza geometry does not.
`repair_monza_grid.py` checks the old signature, compares source and appended
tree inputs, then migrates the retained signature after its grid-only save.

To regenerate, use a single memory-capped process as described in the map
skill. Run this Python through the repository's pinned `uv` environment:

```python
import sys
from pathlib import Path
import shutil

sys.path.insert(0, "tools/blender/tracks")
import bpy
import export_monza_runtime as exporter

output = Path("build/circuit-fidelity/foliage-rebake").resolve()
output.mkdir(parents=True, exist_ok=True)
exporter.CACHE = output
bpy.ops.wm.open_mainfile(filepath=str(exporter.B.BLEND))

def two_threads(scene):
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2

bpy.app.handlers.render_pre.append(two_threads)
exporter.foliage_atlas()
target = Path("tools/blender/tracks/sources/shared/monza_foliage")
shutil.copyfile(output / "foliage.png", target / "foliage.png")
shutil.copyfile(output / "foliage_cards.json", target / "cards.json")
```

This calls only the foliage baker. It does not save the Monza scene, export
its track, or regenerate its route. Inspect all twelve silhouettes and
their alpha edges in the game before accepting a replacement atlas.
