#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <span>
#include "core_math.hpp"

// Source terrain is stored in Blender metre XY, with centimetre height samples.
// Each grid cell has the same a-b-c / a-c-d diagonal as the exported terrain.
struct AuthoredGroundGrid {
    float x0, y0, step;
    int columns, rows;
    std::span<const std::int16_t> heights;
};

inline float authoredGridElevationMeters(const AuthoredGroundGrid& grid, Vec2 simulationPosition) {
    const float x = std::clamp((simulationPosition.x / 17.0f - grid.x0) / grid.step,
                               0.0f, static_cast<float>(grid.columns - 1) - 0.0001f);
    const float y = std::clamp((-simulationPosition.y / 17.0f - grid.y0) / grid.step,
                               0.0f, static_cast<float>(grid.rows - 1) - 0.0001f);
    const int column = static_cast<int>(x), row = static_cast<int>(y);
    const float u = x - column, v = y - row;
    const int i = row * grid.columns + column;
    const float a = grid.heights[i] * 0.01f, b = grid.heights[i + 1] * 0.01f;
    const float d = grid.heights[i + grid.columns] * 0.01f;
    const float c = grid.heights[i + grid.columns + 1] * 0.01f;
    return u >= v ? a + (b - a) * u + (c - b) * v
                  : a + (c - d) * u + (d - a) * v;
}
