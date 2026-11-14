"""Rebuild native contact after exporting the current COTA road profile."""

from pathlib import Path

from circuit_scene import CircuitScene
from venues.cota import circuit_edges
from venues.cota_paving import write_backstraight_paving


def main() -> None:
    scene = CircuitScene('cota')
    scene.road_surfaces()
    circuit_edges(scene)
    root = Path(__file__).resolve().parents[1]
    write_backstraight_paving(scene, root / 'Source/FormulaForge/Native/track_data/cota_backstraight_paving.inc')


if __name__ == '__main__':
    main()
