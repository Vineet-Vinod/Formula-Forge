#pragma once

#include "core_math.hpp"

#include <cstdint>
#include <span>
#include <unordered_map>
#include <vector>

struct FFPitSection {
    Vec2 position;
    float height;
    float halfWidth;
    float trackStation;
    float distance;
    Vec2 normal;
    float crossSlope;
};

struct FFPitProjection {
    bool inside = false;
    bool controlled = false;
    float height = 0.0f;
    float grade = 0.0f;
    float trackStation = 0.0f;
    float distance = 0.0f;
    float lane = 0.0f;
    float halfWidth = 0.0f;
    Vec2 position;
    Vec2 tangent{1.0f, 0.0f};
};

class FFPitLane {
public:
    static constexpr float GroundBlendMetres = 3.0f;

    bool Load(std::span<const std::uint8_t> bytes);
    FFPitProjection Project(Vec2 positionMetres, float lateralMarginMetres = 0.0f) const;
    FFPitProjection Sample(float distanceMetres) const;
    const std::vector<FFPitSection>& Sections() const;
private:
    static std::uint64_t CellKey(int column, int row);
    std::vector<FFPitSection> sections;
    std::unordered_map<std::uint64_t, std::vector<std::uint32_t>> cells;
    float limitEntry = 0.0f;
    float limitExit = 0.0f;
};
