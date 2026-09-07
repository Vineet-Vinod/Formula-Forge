"""Separate shipped track assets, reproducible inputs and disposable build output."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "assets/tracks/monza"
SOURCE = Path(__file__).resolve().parent / "sources/monza"
QA = ROOT / "build/monza/qa"
CACHE = ROOT / "build/monza/cache"

for directory in (QA, CACHE):
    directory.mkdir(parents=True, exist_ok=True)
