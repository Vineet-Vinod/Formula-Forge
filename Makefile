BUILD_DIR := build
GAME_BUILD_DIR := $(BUILD_DIR)/game
TARGET := $(GAME_BUILD_DIR)/harbor_karts
LEGACY_TARGET := $(BUILD_DIR)/harbor_karts
SDL_LIB := $(BUILD_DIR)/deps/install/lib/libSDL3.a

.PHONY: all deps clean clean-all run self-test race-audit capture-playtest

all: $(TARGET) $(LEGACY_TARGET)

deps: $(SDL_LIB)

$(SDL_LIB): scripts/bootstrap_deps.sh third_party/_cache/SDL3-3.4.10.tar.gz third_party/_cache/libXext-1.3.6.tar.xz
	scripts/bootstrap_deps.sh

$(TARGET): CMakeLists.txt src/main.cpp src/harbor_karts.cpp src/core_math.hpp src/renderer.hpp src/track_layout.hpp $(SDL_LIB)
	cmake -S . -B $(GAME_BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(GAME_BUILD_DIR) --parallel

$(LEGACY_TARGET): $(TARGET)
	ln -sf game/harbor_karts $@

run: $(TARGET)
	$(TARGET)

self-test: $(TARGET)
	$(TARGET) --self-test

race-audit: $(TARGET)
	$(TARGET) --race-audit

capture-playtest: $(TARGET)
	$(TARGET) --capture-playtest build/playtest_frames

clean:
	rm -rf $(GAME_BUILD_DIR) $(LEGACY_TARGET)

clean-all:
	rm -rf $(BUILD_DIR)
