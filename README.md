# Formula Forge

A single-player formula racing game built entirely in Unreal Engine. Drive a Ferrari
at Silverstone, Monza or Interlagos in Time Trial. Choose Unlimited, 1, 3, 5 or 10
timed laps. Unlimited is the default; the out-lap is excluded. Invalid timed laps
count toward the session limit but cannot set a best time.

Selection, loading, driving, pause and results run inside one game process.
Keyboard and controller input are supported. No Blender, raylib, Python setup,
Git LFS, paid asset downloads or separate menu application is needed to play.

## Requirements

**Install Unreal Engine 5.8.3 or a newer 5.8 patch, plus the C++ toolchain for your OS.**
Unreal Engine is required to build from this repository and is not included in Git.
Older engine versions cannot reliably read these assets. Other major/minor versions
are not supported by the build scripts. The tested engine version is 5.8.3.

| Platform | Install before building |
| --- | --- |
| Windows x64 | [Unreal through the Epic Games Launcher](https://dev.epicgames.com/documentation/en-us/unreal-engine/install-unreal-engine), Git, and [Visual Studio's C++ game-development toolchain](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine). UE 5.8 supports VS 2022 17.14+ or VS 2026 18.0+. Include MSVC and Windows SDK 10.0.22621.0 or newer. |
| macOS, Apple Silicon | Unreal through the Epic Games Launcher, Git, full Xcode and its command-line tools. [Epic's UE 5.8 requirements](https://dev.epicgames.com/documentation/en-us/unreal-engine/macos-development-requirements-for-unreal-engine) specify macOS 14.5+, Xcode 26.0 minimum and 26.1.1 recommended. Xcode 26.4 is incompatible. |
| Linux x86_64 | [Epic's Linux installed engine](https://www.unrealengine.com/en-US/linux), its bundled native toolchain, a Vulkan-capable GPU/driver, Git, GNU Make, a C++20 compiler, Bubblewrap and a functioning systemd user session. See [Epic's Linux requirements](https://dev.epicgames.com/documentation/en-us/unreal-engine/linux-development-requirements-for-unreal-engine). |

Use a machine that meets Epic's engine requirements; 32 GB RAM is recommended for
development. Allow at least 35 GB free for project build output, in addition to the
engine installation. A first build can take tens of minutes while compiling code,
shaders and mesh data; subsequent builds reuse generated caches. The scripts
limit C++ compilation to one action at a time.

Linux packaging and gameplay have been tested. Windows and macOS have native build
scripts and platform configuration, but have not yet been built or play-tested on
those operating systems. They should be treated as unverified until those checks
are completed.

## Clone

```sh
git clone --depth 1 https://github.com/Vineet-Vinod/Formula-Forge.git
cd Formula-Forge
```

The shallow clone downloads the current game without the earlier project's history.
All required game assets are ordinary Git files. The measured shallow-clone Git
transfer is about 580 MiB; the checkout is approximately 0.85 GiB before building.
Keep the checkout in a writable location, outside the
engine installation. On Windows, a short path such as `C:\Games\Formula-Forge`
also avoids toolchain path-length limits.

## Windows: build and play

Open PowerShell in the cloned repository. Set `UE_ROOT` to the directory that
contains `Engine`, not to the `Engine` directory itself:

```powershell
$env:UE_ROOT = "C:\Program Files\Epic Games\UE_5.8"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\unreal.ps1 package
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\unreal.ps1 run
```

The execution-policy option applies only to that PowerShell process. Later launches
only need the `run` command. To play in a window, add `-GameArgs "-windowed"`.
The package is written to `build/unreal/package/Windows/`.

## macOS: build and play

After installing full Xcode, select it and complete its first-launch setup:

```sh
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -runFirstLaunch
```

From the cloned repository:

```sh
export UE_ROOT="/Users/Shared/Epic Games/UE_5.8"
make package
make run
```

Adjust `UE_ROOT` if Epic installed the engine elsewhere. For example, some
installations use `/Users/Shared/UnrealEngine/UE_5.8`. The package is written to
`build/unreal/package/Mac/`. Later launches only need `make run`.

## Linux: build and play

For Ubuntu/Debian, install the project command-line dependencies:

```sh
sudo apt install git build-essential bubblewrap
```

Extract Epic's Linux installed engine, then set its location and build:

```sh
export UE_ROOT="$HOME/Unreal/UE_5.8"
make package
make run
```

Adjust the path to your installation. The engine's native SDK must be installed;
use Epic's setup instructions if UnrealBuildTool reports a missing Linux SDK.
Run from a normal desktop login with a working `systemd --user` session and
Bubblewrap user namespaces available. The guarded Linux scripts do not support
containers or systems without those facilities.

The package is written to `build/unreal/package/Linux/`. Later launches only need
`make run`. On Linux and macOS, `make run ARGS="-windowed"` starts a windowed game.
`UE_ROOT` can be set in your shell profile so it persists across terminals.

## Updates and troubleshooting

After `git pull`, run the package command again before playing. Packaged games
contain cooked assets; changing source files alone does not update the executable.
Close the game and editor before rebuilding.

- **Engine not found / wrong version:** check `UE_ROOT/Engine/Build/Build.version`.
  The scripts require the 5.8 series, patch 3 or later.
- **Missing compiler or SDK:** install the C++ toolchain listed above. Installing
  the engine alone is not enough to compile a C++ project.
- **Game executable not found:** finish `package` successfully before `run`.
- **Build failure:** inspect `build/unreal/logs/` and the terminal output. On Windows,
  packaging output is also saved in `build/unreal/logs/package.log`.
- **Linux memory guard stops:** close memory-heavy applications and retry. These
  developer scripts cap the job at 4 GB with no swap and stop at 10 GB measured
  machine use. This guard and the read-only engine sandbox are Linux-specific;
  Windows/macOS scripts limit build concurrency but do not enforce a RAM ceiling.

The native `.uproject` can also be opened in Unreal Editor after building the editor
module with `make build` or `tools/unreal.ps1 build`. Use **Play > Standalone Game**
to inspect the game. The packaged `run` commands are the normal play path.

## Controls

On the landing page, A/D or Left/Right selects the circuit; W/S or Up/Down
changes the lap limit. Enter or Space starts the displayed session. On a
controller, use the D-pad or left stick and press A to drive. Mouse selection
is also supported. Escape or controller B quits from the landing page.

In pause/results menus, arrows or WASD navigate and Enter/Space or controller A
activates the highlighted action. Escape or P pauses driving; Escape resumes from pause. The pause menu supports
resume, restart, circuit selection and quit. Finite sessions show a results screen
with drive-again, change-circuit and quit actions.

Driving retains the original controls and tuning: W/A/S/D, Space for braking,
Q/E for shifts, M for automatic/manual shifting, C for camera and R for reset.
Gamepad triggers accelerate/brake, the left stick steers, shoulders shift,
X toggles automatic shifting, Back changes camera, Y resets and Start pauses.
Best valid laps are saved separately for each circuit.

## Development checks

`make script-check` checks the platform scripts with fake engine executables,
including argument quoting, engine-version checks and failure propagation. On
Linux, set `PWSH` to a PowerShell executable to include the Windows command tests.
These checks do not replace building and playing on Windows or macOS.

On Linux, `make check` runs native surface, simulation, circuit and camera audits.
After packaging, `make session-check` runs Unreal's lap-limit automation and
`make flow-check` exercises keyboard/controller input, all three maps, pause/resume,
a timed Interlagos lap, results, restart and return to selection.

`make run ARGS="-windowed -RenderOffscreen -FFMenuReview"` captures the garage menu
and exits. Review captures and gameplay test results go under
`build/unreal/home/Saved/FlowAudit/`. Best laps and game settings are stored under
`build/unreal/home/`. Build output and local saves are ignored by Git.

## Repository contents and licences

`Source/`, `Config/` and `Content/` are the game's source. Native Unreal assets are
versioned directly; no asset generator needs to run before building. The optional
`tools/prepare_project.py` uses Unreal Editor's own Python integration to rebuild
the garage scene, not the circuits.

Silverstone's drive-surface data is split into `drive_surface.bin.0` through `.2`
under `Content/Generated/Data/`. The game joins the consecutive 48 MiB pieces, with
a shorter final piece, before parsing them. This preserves the original data while
keeping every new Git blob below 50 MiB. Do not omit or rename these files.

Compiled executables, cooked packages, engine files, caches and downloaded
references are not committed. The three accepted circuits retain their geometry,
materials, camera and vehicle handling. Code is covered by [LICENSE](LICENSE);
asset credits and their separate licences are retained under
[Attribution](Attribution/README.md). Unreal Engine is installed and licensed
separately through Epic.
