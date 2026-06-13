cmake_minimum_required(VERSION 3.20)

project(HarborKarts LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(SDL3_ROOT "${CMAKE_SOURCE_DIR}/build/deps/install" CACHE PATH "Vendored SDL3 install root")
set(SDL3_INCLUDE_DIR "${SDL3_ROOT}/include")
set(SDL3_LIBRARY "${SDL3_ROOT}/lib/libSDL3.a")

if(NOT EXISTS "${SDL3_LIBRARY}" OR NOT EXISTS "${SDL3_INCLUDE_DIR}/SDL3/SDL.h")
    message(FATAL_ERROR "Vendored SDL3 is missing. Run scripts/bootstrap_deps.sh first.")
endif()

find_package(Threads REQUIRED)

add_executable(harbor_karts src/main.cpp)

target_compile_definitions(harbor_karts PRIVATE SDL_MAIN_HANDLED)
target_compile_options(harbor_karts PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(harbor_karts PRIVATE "${SDL3_INCLUDE_DIR}")
target_link_libraries(harbor_karts PRIVATE "${SDL3_LIBRARY}" Threads::Threads dl m)

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    target_compile_options(harbor_karts PRIVATE -O3)
endif()
