# Formula Forge

This repository is the canonical Unreal-only game. Keep project files and build
artifacts in this folder. Do not create worktrees unless requested. Preserve the
separately installed Unreal Engine folder.

Support Silverstone, Monza and Interlagos, with Ferrari and Time Trial fixed.
Unlimited laps is the default. Menus, loading and driving run in one Unreal process.
Preserve accepted circuit assets, physics, handling, speed, shifting and camera
unless the user explicitly requests changes.

On Linux, use the guarded Make targets for building, packaging, testing and playing. Stay
below 11 GB total used memory and run one heavy job at a time. Keep native Unreal
assets versioned. Do not add Blender, raylib or an external menu process.

Keep implementation simple. Declare C++ types and functions in headers and put
implementations in .cpp files. Use focused checks for input, session flow, physics
and asset regressions. Commit with type: concise description. Do not push or merge
without an explicit request.
