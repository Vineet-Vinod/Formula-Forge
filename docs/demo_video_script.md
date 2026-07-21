# Formula Forge — Build Week Demo Video

**Target length:** 2:45–2:55

**Format:** Continuous game flow with separately recorded voiceover
**Visual flow:** Loading screen → Race selection → Car selection → Monza, 2 laps → Race → Results

## Recording and editing directions

- Record clean 1080p gameplay with game audio audible beneath the narration.
- Begin recording before launch so the Formula Forge loading screen appears naturally.
- Select **Race**, choose a car, select **Monza**, and set the race to **2 laps**.
- Keep the countdown, launch, first chicane, lap transition, finish, and results screen at normal speed.
- Use smooth 1.5×–2× speed ramps on Monza's long straights and make short invisible cuts between braking zones if needed. Both completed laps and the changing lap counter must remain clear.
- Favor clean driving over winning. Show braking, manual gear changes, close AI racing, one overtake if available, and at least one strong high-speed corner.
- Record the voiceover separately and fit the gameplay ramps to it. Do not rush the narration to fit an unedited race.
- Display the title **Formula Forge** at the beginning and the repository URL at the end. Avoid additional text overlays unless a feature is otherwise difficult to recognize.

## Timed script

### 0:00–0:10 — Loading screen

**Visual:** Launch the game. Hold briefly on the Formula Forge loading artwork as the cars appear.

**Voiceover:**

> This is Formula Forge, an open-source, Linux-native formula racing game built with Codex and GPT-5.6.

### 0:10–0:27 — Entering single player

**Visual:** Arrive at the main flow and select **Race**. Move deliberately so every selection is readable.

**Voiceover:**

> I started it because I loved Beach Buggy Racing, but could not play it natively on Linux. I also love F1, so I challenged myself to see how far an AI coding agent could help me build a complete 3D racing game.

### 0:27–0:43 — Car selection

**Visual:** Cycle through several rotating car previews, then choose one. Let the garage and original liveries remain visible for a moment.

**Voiceover:**

> The result is an original C++20 game with five logo-free car liveries, a six-car racing grid, controller and steering-wheel input, and both AI races and solo time trials.

### 0:43–0:57 — Monza and race-distance selection

**Visual:** Cycle through the circuit map previews, stop on **Monza**, select **2 laps**, and start the race.

**Voiceover:**

> Five circuits are currently playable. For this demo, I am choosing Monza and a two-lap race against AI. The entire selection, race, pause and results flow is implemented in-game.

### 0:57–1:20 — Grid, countdown and launch

**Visual:** Show the full grid, countdown and launch at normal speed. Enter the first chicane, shifting and braking cleanly.

**Voiceover:**

> The driving model is more than a car following a line. It combines tire grip, aerodynamic downforce and drag, load transfer, trail braking, engine braking, surface changes and an eight-speed manual sequential gearbox. The AI scans upcoming curvature, brakes before turn-in, and commits to the corner exit.

### 1:20–1:48 — First lap

**Visual:** Continue lap one. Show an AI battle or overtake, then speed-ramp a long straight. Return to normal speed for braking and corner entry.

**Voiceover:**

> GPT-5.6 and Codex were active engineering partners throughout the project, not just autocomplete. They helped implement the physics, AI, race rules, rendering, interface, controller support, audio and development tools. I would play a build, describe what felt wrong, and ask Codex to diagnose the underlying behavior.

### 1:48–2:18 — Lap transition and second lap

**Visual:** Show the lap counter changing to lap two at normal speed. Continue racing, with smooth ramps on straights and normal-speed corner sequences.

**Voiceover:**

> The hardest part was communicating subjective feedback such as, “the car feels slow,” or, “the AI enters this corner badly.” I solved that by giving Codex programmatic feedback. Deterministic audits measure acceleration, braking, grip, shifting, collisions, AI pace and lap validity. A JSONL agent-play protocol lets a model drive the game, inspect telemetry and request screenshots before making another change.

### 2:18–2:39 — Final sector

**Visual:** Show the strongest final-lap sequence. Include a high-speed corner, braking zone and the approach to the finish.

**Voiceover:**

> Codex also uses Blender through Python to generate cars, drivers, tracks, garage scenes and runtime assets. Separate validation tools check dimensions, animations, circuit geometry and clearances. Giving the agent ways to build, observe, measure and verify is what pushed the project beyond a basic prototype.

### 2:39–2:55 — Finish and results

**Visual:** Cross the line at normal speed. Show the final position and results screen, then end on a clean Formula Forge title card with the repository URL.

**Voiceover:**

> Formula Forge is now a complete, playable Linux racing game with realistic-feeling handling and reproducible tests behind it. Next, I want to add more tracks, improve the artwork and sound, expand racecraft, and eventually bring it to more platforms. This is Formula Forge—built with Codex and GPT-5.6.

## Full voiceover copy

This is Formula Forge, an open-source, Linux-native formula racing game built with Codex and GPT-5.6.

I started it because I loved Beach Buggy Racing, but could not play it natively on Linux. I also love F1, so I challenged myself to see how far an AI coding agent could help me build a complete 3D racing game.

The result is an original C++20 game with five logo-free car liveries, a six-car racing grid, controller and steering-wheel input, and both AI races and solo time trials.

Five circuits are currently playable. For this demo, I am choosing Monza and a two-lap race against AI. The entire selection, race, pause and results flow is implemented in-game.

The driving model is more than a car following a line. It combines tire grip, aerodynamic downforce and drag, load transfer, trail braking, engine braking, surface changes and an eight-speed manual sequential gearbox. The AI scans upcoming curvature, brakes before turn-in, and commits to the corner exit.

GPT-5.6 and Codex were active engineering partners throughout the project, not just autocomplete. They helped implement the physics, AI, race rules, rendering, interface, controller support, audio and development tools. I would play a build, describe what felt wrong, and ask Codex to diagnose the underlying behavior.

The hardest part was communicating subjective feedback such as, “the car feels slow,” or, “the AI enters this corner badly.” We solved that by giving Codex programmatic feedback. Deterministic audits measure acceleration, braking, grip, shifting, collisions, AI pace and lap validity. A JSONL agent-play protocol lets a model drive the game, inspect telemetry and request screenshots before making another change.

Codex also uses Blender through Python to generate cars, drivers, tracks, garage scenes and runtime assets. Separate validation tools check dimensions, animations, circuit geometry and clearances. Giving the agent ways to build, observe, measure and verify is what pushed the project beyond a basic prototype.

Formula Forge is now a complete, playable Linux racing game with realistic-feeling handling and reproducible tests behind it. Next, I want to add more tracks, improve the artwork and sound, expand racecraft, and eventually bring it to more platforms. This is Formula Forge—built with Codex and GPT-5.6.
