"""Compile and run controlled game-library captures without changing the game."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / "build/forensics/monza")
    ap.add_argument(
        "--asset",
        type=Path,
        default=ROOT / "assets/tracks/monza/monza.glb",
    )
    ap.add_argument("--prefix", default="")
    ap.add_argument("--unlit", action="store_true")
    args = ap.parse_args()
    r = args.output.resolve()
    r.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O2",
            str(ROOT / "tools/diagnostics/monza_renderer_probe.cpp"),
            "-I" + str(ROOT / "build/deps/raylib-install/include"),
            "-I" + str(ROOT / "build/deps/install/include"),
            str(ROOT / "build/deps/raylib-install/lib/libraylib.a"),
            str(ROOT / "build/deps/install/lib/libSDL3.a"),
            "-ldl",
            "-lm",
            "-o",
            str(r / "renderer_probe"),
        ],
        check=True,
    )
    source = (ROOT / "src/arcade_render.cpp").read_text()
    for name, ext in [("Vertex", "vs"), ("Fragment", "fs")]:
        (r / f"game.{ext}").write_text(
            re.search(
                r"kLighting" + name + r'Shader = R"GLSL\((.*?)\)GLSL"',
                source,
                re.DOTALL,
            )[1]
        )
    fragment_path = r / "game.fs"
    if args.unlit:
        fragment_path = r / "game_unlit.fs"
        fragment_path.write_text(
            (r / "game.fs")
            .read_text()
            .replace("gl_FragColor = vec4(finalColor, base.a);", "gl_FragColor = base;")
        )
    sys.path.insert(0, str(ROOT / "tools/blender/tracks"))
    import build_monza as B

    poses = {}
    for name, s, off, look in [
        ("start", -15, 0, 30),
        ("pit", 150, -3, 40),
        ("grandstand", 170, 0, 35),
        ("kerb", 645, -2, 20),
        ("kerb_entry", 603, 0, 16),
        ("stand_side", 65, 0, 30),
        ("stand_av", 360, 0, 30),
    ]:
        eye = B.station_point(s, off, 1.2)[0]
        target = B.station_point(
            s + look, -25 if name in ["stand_side", "stand_av"] else off, 1.2
        )[0]
        poses[name] = [
            v for p in [eye, target] for v in (p.x * 1.445, p.z * 1.445, -p.y * 1.445)
        ]
    (r / "poses.json").write_text(json.dumps(poses, indent=2) + "\n")
    for name, pose in poses.items():
        for near, reverse in [("0.05", "0"), ("0.5", "0"), ("0.05", "1")]:
            label = f"{args.prefix}{name}_near{near}_reverse{reverse}"
            cmd = [
                str(r / "renderer_probe"),
                str(args.asset.resolve()),
                str(r / "game.vs"),
                str(fragment_path),
                str(r / f"{label}.png"),
                near,
                *map(str, pose),
                reverse,
                str(int(args.unlit)),
            ]
            with (r / f"{label}.log").open("w") as out:
                subprocess.run(
                    cmd,
                    env={**os.environ, "SDL_VIDEODRIVER": "offscreen"},
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            assert (r / f"{label}.png").is_file(), label
            print(label, flush=True)


if __name__ == "__main__":
    main()
