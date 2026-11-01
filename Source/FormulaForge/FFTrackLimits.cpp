#include "FFTrackLimits.hpp"

#include <cmath>
#include <cstring>
#include <algorithm>

const std::array<FFTrackTyre, 4> FFSilverstoneTyres{{
    {{1.60f, 0.815f}, 0.156f},
    {{1.60f, -0.815f}, 0.156f},
    {{-1.57f, 0.775f}, 0.1976f},
    {{-1.57f, -0.775f}, 0.1976f},
}};

bool FFTyreTouchesTrack(float laneMetres, float roadHalfWidthMetres,
    Vec2 tyreAcross, Vec2 trackAcross, float tyreHalfWidthMetres) {
    const float lateralReach = std::abs(dot(tyreAcross, trackAcross)) * tyreHalfWidthMetres;
    return std::abs(laneMetres) <= roadHalfWidthMetres + lateralReach + 0.001f;
}

bool FFTrackLimits::Load(std::span<const std::uint8_t> bytes) {
    if (bytes.size() < 8 || std::memcmp(bytes.data(), "FFTL", 4) != 0) return false;
    std::uint32_t count;
    std::memcpy(&count, bytes.data() + 4, sizeof(count));
    if (count == 0 || count > 100000 || bytes.size() != 8 + count * 6 * sizeof(float)) return false;
    std::vector<std::array<Vec2, 3>> points(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        std::array<float, 6> coordinates;
        std::memcpy(coordinates.data(), bytes.data() + 8 + index * sizeof(coordinates), sizeof(coordinates));
        for (std::size_t point = 0; point < 3; ++point) {
            points[index][point] = {coordinates[point * 2], coordinates[point * 2 + 1]};
        }
    }
    return SetTriangles(points);
}

bool FFTrackLimits::SetTriangles(std::span<const std::array<Vec2, 3>> points) {
    if (points.empty() || points.size() > 100000) return false;
    std::vector<FFTrackLimitTriangle> loaded;
    loaded.reserve(points.size());
    for (const auto& vertices : points) {
        FFTrackLimitTriangle triangle;
        triangle.points = vertices;
        for (Vec2 point : vertices) {
            if (!std::isfinite(point.x) || !std::isfinite(point.y) ||
                std::abs(point.x) > 10000.0f || std::abs(point.y) > 10000.0f) return false;
        }
        if (std::abs(cross(triangle.points[1] - triangle.points[0], triangle.points[2] - triangle.points[0])) < 0.000001f) return false;
        triangle.minimum = triangle.maximum = triangle.points[0];
        for (const Vec2 point : triangle.points) {
            triangle.minimum.x = std::min(triangle.minimum.x, point.x);
            triangle.minimum.y = std::min(triangle.minimum.y, point.y);
            triangle.maximum.x = std::max(triangle.maximum.x, point.x);
            triangle.maximum.y = std::max(triangle.maximum.y, point.y);
        }
        loaded.push_back(triangle);
    }
    triangles = std::move(loaded);
    return true;
}

bool FFTrackLimits::Touches(Vec2 centreMetres, Vec2 tyreAcross, float halfWidthMetres) const {
    const Vec2 first = centreMetres - tyreAcross * halfWidthMetres;
    const Vec2 last = centreMetres + tyreAcross * halfWidthMetres;
    const Vec2 minimum{std::min(first.x, last.x) - 0.001f, std::min(first.y, last.y) - 0.001f};
    const Vec2 maximum{std::max(first.x, last.x) + 0.001f, std::max(first.y, last.y) + 0.001f};
    for (const auto& triangle : triangles) {
        if (minimum.x > triangle.maximum.x || minimum.y > triangle.maximum.y ||
            maximum.x < triangle.minimum.x || maximum.y < triangle.minimum.y) continue;
        const float orientation = cross(triangle.points[1] - triangle.points[0], triangle.points[2] - triangle.points[0]) > 0.0f ? 1.0f : -1.0f;
        float begin = 0.0f;
        float end = 1.0f;
        for (std::size_t edge = 0; edge < 3; ++edge) {
            const Vec2 origin = triangle.points[edge];
            const Vec2 direction = triangle.points[(edge + 1) % 3] - origin;
            const float tolerance = length(direction) * 0.001f;
            const float firstSide = orientation * cross(direction, first - origin) + tolerance;
            const float lastSide = orientation * cross(direction, last - origin) + tolerance;
            if (firstSide < 0.0f && lastSide < 0.0f) {
                begin = 2.0f;
                break;
            }
            if (firstSide < 0.0f) begin = std::max(begin, firstSide / (firstSide - lastSide));
            if (lastSide < 0.0f) end = std::min(end, firstSide / (firstSide - lastSide));
        }
        if (begin <= end) return true;
    }
    return false;
}

bool FFTrackLimits::Empty() const { return triangles.empty(); }

const std::vector<FFTrackLimitTriangle>& FFTrackLimits::Triangles() const { return triangles; }
