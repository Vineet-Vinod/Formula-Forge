BUILD_DIR := build
GAME_BUILD_DIR := $(BUILD_DIR)/game
TARGET := $(GAME_BUILD_DIR)/formula_forge
SDL_LIB := $(BUILD_DIR)/deps/install/lib/libSDL3.a
RAYLIB_LIB := $(BUILD_DIR)/deps/raylib-install/lib/libraylib.a
GAME_SOURCES := $(wildcard src/*.cpp src/*.hpp src/track_data/*.inc) CMakeLists.txt
UV_PYTHON := uv run --no-sync python

.PHONY: all run test assets assets-validate clean

all: $(TARGET)

run: $(TARGET)
	$(TARGET) $(ARGS)

test: $(TARGET)
	ctest --test-dir $(GAME_BUILD_DIR) --output-on-failure

assets:
	uv sync --frozen
	$(UV_PYTHON) tools/blender/generators/generate_vehicles.py --asset all
	$(UV_PYTHON) tools/blender/generators/generate_drivers.py --asset all
	$(UV_PYTHON) tools/blender/generators/generate_loading_screen.py
	$(UV_PYTHON) tools/blender/generators/generate_formula_garage.py
	$(UV_PYTHON) tools/blender/tracks/generate_tracks.py --track all

assets-validate:
	uv sync --frozen
	$(UV_PYTHON) tools/blender/generators/verify_assets.py
	$(UV_PYTHON) tools/blender/tracks/verify_tracks.py --track all

$(SDL_LIB): scripts/bootstrap_deps.sh third_party/_cache/SDL3-3.4.10.tar.gz third_party/_cache/libXext-1.3.6.tar.xz
	scripts/bootstrap_deps.sh

$(RAYLIB_LIB): scripts/bootstrap_raylib.sh third_party/_cache/raylib-6.0.tar.gz $(SDL_LIB)
	scripts/bootstrap_raylib.sh

$(TARGET): $(GAME_SOURCES) $(SDL_LIB) $(RAYLIB_LIB)
	cmake -S . -B $(GAME_BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(GAME_BUILD_DIR) --parallel

clean:
	cmake -E remove_directory "$(BUILD_DIR)"
