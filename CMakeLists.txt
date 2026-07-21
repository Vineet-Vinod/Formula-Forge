cmake_minimum_required(VERSION 3.20)

project(FormulaForge LANGUAGES CXX)

include(CTest)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(SDL3_ROOT "${CMAKE_SOURCE_DIR}/build/deps/install" CACHE PATH "Vendored SDL3 install root")
set(SDL3_INCLUDE_DIR "${SDL3_ROOT}/include")
set(SDL3_LIBRARY "${SDL3_ROOT}/lib/libSDL3.a")
set(RAYLIB_ROOT "${CMAKE_SOURCE_DIR}/build/deps/raylib-install" CACHE PATH "Vendored raylib install root")
set(RAYLIB_INCLUDE_DIR "${RAYLIB_ROOT}/include")
set(RAYLIB_LIBRARY "${RAYLIB_ROOT}/lib/libraylib.a")

if(NOT EXISTS "${SDL3_LIBRARY}" OR NOT EXISTS "${SDL3_INCLUDE_DIR}/SDL3/SDL.h")
    message(FATAL_ERROR "Vendored SDL3 is missing. Run scripts/bootstrap_deps.sh first.")
endif()
if(NOT EXISTS "${RAYLIB_LIBRARY}" OR NOT EXISTS "${RAYLIB_INCLUDE_DIR}/raylib.h")
    message(FATAL_ERROR "Vendored raylib is missing. Run scripts/bootstrap_raylib.sh first.")
endif()

find_package(Threads REQUIRED)

add_executable(formula_forge
    src/agent_play_protocol.cpp
    src/main.cpp
    src/arcade_audio.cpp
    src/arcade_hud.cpp
    src/arcade_race.cpp
    src/arcade_render.cpp
    src/arcade_vehicle.cpp
    src/glb_asset.cpp
    src/game.cpp
    src/track_catalog.cpp
    src/track_renderer.cpp
)

target_compile_definitions(formula_forge PRIVATE SDL_MAIN_HANDLED)
target_compile_options(formula_forge PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(formula_forge PRIVATE "${RAYLIB_INCLUDE_DIR}" "${SDL3_INCLUDE_DIR}")
target_link_libraries(formula_forge PRIVATE "${RAYLIB_LIBRARY}" "${SDL3_LIBRARY}" Threads::Threads dl m)

if(BUILD_TESTING)
    add_test(NAME agent_play_protocol_audit COMMAND formula_forge --agent-play-audit)
    add_test(NAME controller_input_audit COMMAND formula_forge --input-audit)
    add_test(NAME race_grid_alignment_audit COMMAND formula_forge --grid-audit)
    add_test(NAME arcade_audio_audit COMMAND formula_forge --audio-audit)
    add_test(NAME arcade_vehicle_audit COMMAND formula_forge --vehicle-audit)
    add_test(NAME arcade_race_flow_audit COMMAND formula_forge --race-flow-audit)
    add_test(NAME track_gradient_audit COMMAND formula_forge --terrain-audit)
    add_test(NAME ai_monza_pace_audit COMMAND formula_forge --ai-pace-audit)
    add_test(NAME ai_spa_pace_audit COMMAND formula_forge --ai-pace-audit-spa)
    add_test(NAME ai_suzuka_pace_audit COMMAND formula_forge --ai-pace-audit-suzuka)
    add_test(NAME ai_silverstone_pace_audit COMMAND formula_forge --ai-pace-audit-silverstone)
    add_test(NAME ai_interlagos_pace_audit COMMAND formula_forge --ai-pace-audit-interlagos)
    add_test(NAME handling_dynamics_audit COMMAND formula_forge --handling-audit)
    add_test(NAME collision_dynamics_audit COMMAND formula_forge --collision-audit)
    add_test(NAME spa_control_audit COMMAND formula_forge --spa-control-audit)
    add_test(NAME spa_geometry_audit COMMAND formula_forge --spa-audit)
    add_test(NAME track_catalog_audit COMMAND formula_forge --track-catalog-audit)
    add_test(NAME time_trial_session_audit COMMAND formula_forge --time-trial-audit --windowed)
    add_test(NAME authored_asset_audit COMMAND formula_forge --asset-audit)
    set_tests_properties(authored_asset_audit PROPERTIES
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
        ENVIRONMENT "SDL_VIDEODRIVER=offscreen"
    )
endif()

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    target_compile_options(formula_forge PRIVATE -O3)
endif()
