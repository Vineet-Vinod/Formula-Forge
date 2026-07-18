BUILD_DIR := build
GAME_BUILD_DIR := $(BUILD_DIR)/game
TARGET := $(GAME_BUILD_DIR)/harbor_karts
TARGET_3D := $(GAME_BUILD_DIR)/harbor_karts_3d
LEGACY_TARGET := $(BUILD_DIR)/harbor_karts
LEGACY_TARGET_3D := $(BUILD_DIR)/harbor_karts_3d
SDL_LIB := $(BUILD_DIR)/deps/install/lib/libSDL3.a
RAYLIB_LIB := $(BUILD_DIR)/deps/raylib-install/lib/libraylib.a
GAME_SOURCES := $(wildcard src/*.cpp src/*.hpp) CMakeLists.txt

.PHONY: all deps assets assets-validate assets-preview clean clean-all run run-2d run-3d self-test input-audit-3d audio-audit-3d vehicle-audit-3d race-flow-audit-3d race-audit race-audit-3d capture-playtest capture-playtest-3d capture-lap-3d capture-section-tour-3d capture-spa-tour-3d capture-map-gallery-3d capture-time-trial-3d spa-audit-3d track-catalog-audit-3d asset-audit-3d time-trial-audit-3d perf-audit perf-audit-3d spa-perf-audit-3d smoke-3d handling-audit-3d collision-audit-3d terrain-audit-3d ai-pace-audit-3d

all: $(TARGET) $(TARGET_3D) $(LEGACY_TARGET) $(LEGACY_TARGET_3D)

deps: $(SDL_LIB) $(RAYLIB_LIB)

assets:
	uv sync --frozen
	uv run --no-sync python tools/build_assets.py build all
	uv run --no-sync python tools/blender/generators/generate_vehicles.py --asset all
	uv run --no-sync python tools/blender/generators/generate_drivers.py --asset all
	uv run --no-sync python tools/blender/tracks/generate_tracks.py --track all

assets-validate:
	uv sync --frozen
	uv run --no-sync python tools/build_assets.py validate all
	uv run --no-sync python tools/blender/generators/verify_assets.py
	uv run --no-sync python tools/blender/tracks/verify_tracks.py --track all

assets-preview:
	uv sync --frozen
	uv run --no-sync python tools/build_assets.py preview all

$(SDL_LIB): scripts/bootstrap_deps.sh third_party/_cache/SDL3-3.4.10.tar.gz third_party/_cache/libXext-1.3.6.tar.xz
	scripts/bootstrap_deps.sh

$(RAYLIB_LIB): scripts/bootstrap_raylib.sh third_party/_cache/raylib-6.0.tar.gz $(SDL_LIB)
	scripts/bootstrap_raylib.sh

$(TARGET) $(TARGET_3D) &: $(GAME_SOURCES) $(SDL_LIB) $(RAYLIB_LIB)
	cmake -S . -B $(GAME_BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(GAME_BUILD_DIR) --parallel

$(LEGACY_TARGET): $(TARGET)
	ln -sf game/harbor_karts $@

$(LEGACY_TARGET_3D): $(TARGET_3D)
	ln -sf game/harbor_karts_3d $@

run: run-3d

run-2d: $(TARGET)
	$(TARGET)

run-3d: $(TARGET_3D)
	$(TARGET_3D)

self-test: $(TARGET)
	$(TARGET) --self-test

race-audit: $(TARGET)
	$(TARGET) --race-audit

race-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --race-audit

capture-playtest: $(TARGET)
	$(TARGET) --capture-playtest build/playtest_frames

capture-playtest-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-playtest

capture-lap-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-lap

capture-section-tour-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-section-tour

capture-spa-tour-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-spa-tour

capture-map-gallery-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-map-gallery

capture-time-trial-3d: $(TARGET_3D)
	$(TARGET_3D) --capture-time-trial

spa-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --spa-audit

track-catalog-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --track-catalog-audit

asset-audit-3d: $(TARGET_3D)
	SDL_VIDEODRIVER=offscreen $(TARGET_3D) --asset-audit

time-trial-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --time-trial-audit --windowed

perf-audit: $(TARGET)
	$(TARGET) --perf-audit

perf-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --perf-audit

spa-perf-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --spa-perf-audit

smoke-3d: $(TARGET_3D)
	$(TARGET_3D) --smoke-render

handling-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --handling-audit

vehicle-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --vehicle-audit

audio-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --audio-audit

input-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --input-audit

race-flow-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --race-flow-audit

collision-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --collision-audit

terrain-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --terrain-audit

ai-pace-audit-3d: $(TARGET_3D)
	$(TARGET_3D) --ai-pace-audit

clean:
	rm -rf $(GAME_BUILD_DIR) $(LEGACY_TARGET) $(LEGACY_TARGET_3D)

clean-all:
	rm -rf $(BUILD_DIR)
