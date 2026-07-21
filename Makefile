BUILD_DIR := build
GAME_BUILD_DIR := $(BUILD_DIR)/game
TARGET := $(GAME_BUILD_DIR)/formula_forge
SDL_LIB := $(BUILD_DIR)/deps/install/lib/libSDL3.a
RAYLIB_LIB := $(BUILD_DIR)/deps/raylib-install/lib/libraylib.a
GAME_SOURCES := $(wildcard src/*.cpp src/*.hpp) CMakeLists.txt

.PHONY: all deps test assets assets-validate clean clean-all run \
	agent-play agent-play-audit input-audit audio-audit vehicle-audit \
	race-flow-audit race-audit handling-audit collision-audit terrain-audit \
	spa-audit track-catalog-audit asset-audit time-trial-audit perf-audit \
	spa-perf-audit smoke ai-pace-audit ai-pace-audit-spa \
	ai-pace-audit-suzuka ai-pace-audit-silverstone ai-pace-audit-interlagos \
	capture-playtest capture-lap capture-section-tour capture-spa-tour \
	capture-suzuka-tour capture-map-gallery capture-time-trial

all: $(TARGET)

deps: $(SDL_LIB) $(RAYLIB_LIB)

test: $(TARGET)
	ctest --test-dir $(GAME_BUILD_DIR) --output-on-failure

assets:
	uv sync --frozen
	uv run --no-sync python tools/blender/generators/generate_vehicles.py --asset all
	uv run --no-sync python tools/blender/generators/generate_drivers.py --asset all
	uv run --no-sync python tools/blender/generators/generate_loading_screen.py
	uv run --no-sync python tools/blender/generators/generate_formula_garage.py
	uv run --no-sync python tools/blender/tracks/generate_tracks.py --track all

assets-validate:
	uv sync --frozen
	uv run --no-sync python tools/blender/generators/verify_assets.py
	uv run --no-sync python tools/blender/tracks/verify_tracks.py --track all

$(SDL_LIB): scripts/bootstrap_deps.sh third_party/_cache/SDL3-3.4.10.tar.gz third_party/_cache/libXext-1.3.6.tar.xz
	scripts/bootstrap_deps.sh

$(RAYLIB_LIB): scripts/bootstrap_raylib.sh third_party/_cache/raylib-6.0.tar.gz $(SDL_LIB)
	scripts/bootstrap_raylib.sh

$(TARGET): $(GAME_SOURCES) $(SDL_LIB) $(RAYLIB_LIB)
	cmake -S . -B $(GAME_BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(GAME_BUILD_DIR) --parallel

run: $(TARGET)
	$(TARGET)

agent-play: $(TARGET)
	$(TARGET) --agent-play

agent-play-audit: $(TARGET)
	$(TARGET) --agent-play-audit

input-audit: $(TARGET)
	$(TARGET) --input-audit

audio-audit: $(TARGET)
	$(TARGET) --audio-audit

vehicle-audit: $(TARGET)
	$(TARGET) --vehicle-audit

race-flow-audit: $(TARGET)
	$(TARGET) --race-flow-audit

race-audit: $(TARGET)
	$(TARGET) --race-audit

handling-audit: $(TARGET)
	$(TARGET) --handling-audit

collision-audit: $(TARGET)
	$(TARGET) --collision-audit

terrain-audit: $(TARGET)
	$(TARGET) --terrain-audit

spa-audit: $(TARGET)
	$(TARGET) --spa-audit

track-catalog-audit: $(TARGET)
	$(TARGET) --track-catalog-audit

asset-audit: $(TARGET)
	SDL_VIDEODRIVER=offscreen $(TARGET) --asset-audit

time-trial-audit: $(TARGET)
	$(TARGET) --time-trial-audit --windowed

perf-audit: $(TARGET)
	$(TARGET) --perf-audit

spa-perf-audit: $(TARGET)
	$(TARGET) --spa-perf-audit

smoke: $(TARGET)
	$(TARGET) --smoke-render

ai-pace-audit: $(TARGET)
	$(TARGET) --ai-pace-audit

ai-pace-audit-spa: $(TARGET)
	$(TARGET) --ai-pace-audit-spa

ai-pace-audit-suzuka: $(TARGET)
	$(TARGET) --ai-pace-audit-suzuka

ai-pace-audit-silverstone: $(TARGET)
	$(TARGET) --ai-pace-audit-silverstone

ai-pace-audit-interlagos: $(TARGET)
	$(TARGET) --ai-pace-audit-interlagos

capture-playtest: $(TARGET)
	$(TARGET) --capture-playtest

capture-lap: $(TARGET)
	$(TARGET) --capture-lap

capture-section-tour: $(TARGET)
	$(TARGET) --capture-section-tour

capture-spa-tour: $(TARGET)
	$(TARGET) --capture-spa-tour

capture-suzuka-tour: $(TARGET)
	$(TARGET) --capture-suzuka-tour

capture-map-gallery: $(TARGET)
	$(TARGET) --capture-map-gallery

capture-time-trial: $(TARGET)
	$(TARGET) --capture-time-trial

clean:
	rm -rf $(GAME_BUILD_DIR)

clean-all:
	rm -rf $(BUILD_DIR)
