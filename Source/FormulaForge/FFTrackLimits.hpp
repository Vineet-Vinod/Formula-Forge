#pragma once

#include "core_math.hpp"
#include <array>
#include <cstdint>
#include <span>
#include <vector>

struct FFTrackTyre {
    Vec2 centreMetres;
    float halfWidthMetres;
};

extern const std::array<FFTrackTyre, 4> FFSilverstoneTyres;

bool FFTyreTouchesTrack(float LaneMetres, float RoadHalfWidthMetres,
    Vec2 TyreAcross, Vec2 TrackAcross, float TyreHalfWidthMetres);

struct FFTrackLimitTriangle {
    std::array<Vec2, 3> points;
    Vec2 minimum;
    Vec2 maximum;
};

class FFTrackLimits {
public:
    bool Load(std::span<const std::uint8_t> bytes);
    bool SetTriangles(std::span<const std::array<Vec2, 3>> points);
    bool Touches(Vec2 centreMetres, Vec2 tyreAcross, float halfWidthMetres) const;
    bool Empty() const;
    const std::vector<FFTrackLimitTriangle>& Triangles() const;
private:
    std::vector<FFTrackLimitTriangle> triangles;
};
