cmake_minimum_required(VERSION 3.20)

project(FormulaBuggy LANGUAGES CXX)

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

add_executable(harbor_karts
    src/main.cpp
    src/harbor_karts.cpp
)

target_compile_definitions(harbor_karts PRIVATE SDL_MAIN_HANDLED)
target_compile_options(harbor_karts PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(harbor_karts PRIVATE "${SDL3_INCLUDE_DIR}")
target_link_libraries(harbor_karts PRIVATE "${SDL3_LIBRARY}" Threads::Threads dl m)

add_executable(harbor_karts_3d
    src/main3d.cpp
    src/arcade_audio.cpp
    src/arcade_hud.cpp
    src/arcade_race.cpp
    src/arcade_render.cpp
    src/arcade_vehicle.cpp
    src/harbor_karts_3d.cpp
    src/track_renderer.cpp
)

target_compile_definitions(harbor_karts_3d PRIVATE SDL_MAIN_HANDLED)
target_compile_options(harbor_karts_3d PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(harbor_karts_3d PRIVATE "${RAYLIB_INCLUDE_DIR}" "${SDL3_INCLUDE_DIR}")
target_link_libraries(harbor_karts_3d PRIVATE "${RAYLIB_LIBRARY}" "${SDL3_LIBRARY}" Threads::Threads dl m)

if(BUILD_TESTING)
    add_test(NAME controller_input_audit COMMAND harbor_karts_3d --input-audit)
    add_test(NAME arcade_audio_audit COMMAND harbor_karts_3d --audio-audit)
    add_test(NAME arcade_vehicle_audit COMMAND harbor_karts_3d --vehicle-audit)
    add_test(NAME arcade_race_flow_audit COMMAND harbor_karts_3d --race-flow-audit)
    add_test(NAME track_gradient_audit COMMAND harbor_karts_3d --terrain-audit)
    add_test(NAME ai_attacking_pace_audit COMMAND harbor_karts_3d --ai-pace-audit)
    add_test(NAME spa_geometry_audit COMMAND harbor_karts_3d --spa-audit)
endif()

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    target_compile_options(harbor_karts PRIVATE -O3)
    target_compile_options(harbor_karts_3d PRIVATE -O3)
endif()
