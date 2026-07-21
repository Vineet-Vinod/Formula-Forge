This is Formula Forge — a Linux-native, open-wheel, formula-style racing game built during OpenAI Build Week.

Formula Forge is an original, open-source 3D racing game written in C++20 with SDL3 and raylib. Choose one of five logo-free car liveries and one of five circuits, then compete in a solo time trial or a full race against AI. The game features a six-car grid, manual sequential shifting, lap timing, collisions, track limits, controller input, and steering-wheel support.

Its handling model combines tire grip, aerodynamic downforce and drag, load transfer, trail braking, engine braking, surface changes, and speed-sensitive steering. AI drivers read the circuit ahead, brake before turn-in, commit to corner exits, race for position, and adapt modestly to the player's pace.

Formula Forge was developed with Codex and GPT-5.6 as active engineering partners. Codex helped build the physics, AI, race flow, rendering, interface, controls, assets, tests, and development tools. When subjective feedback such as “the car feels slow” was difficult to communicate, I gave the agent better ways to observe the game: deterministic handling and race audits, repeatable frame captures, telemetry, and a JSONL protocol that allows a model to drive the game itself.

The 3D cars, drivers, tracks, garage, and loading artwork were produced through a reproducible Blender Python pipeline. Automated validation checks asset dimensions, animations, circuit geometry, clearances, lap progression, AI pace, and vehicle behavior.

Formula Forge is currently developed and tested on Linux. Windows and macOS support are future goals.

Source code and build instructions:
https://github.com/Vineet-Vinod/Formula-Forge

Formula Forge is an unofficial original project and is not affiliated with or endorsed by Formula 1, the FIA, any racing team, or any commercial racing game.

#OpenAIBuildWeek #Codex #GPT56 #OpenSource #LinuxGaming #FormulaRacing #GameDevelopment
