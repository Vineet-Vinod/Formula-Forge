#include "FFDriveSurface.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace {
constexpr float CellSize = 4.0f;
constexpr float Tolerance = 0.00001f;

double Side(const FFSurfacePoint& first, const FFSurfacePoint& second, double positionX, double positionY) {
    const double edgeX = static_cast<double>(second.positionX) - first.positionX;
    const double edgeY = static_cast<double>(second.positionY) - first.positionY;
    return edgeX * (positionY - first.positionY) - edgeY * (positionX - first.positionX);
}

float TrianglePenetration(const FFSurfaceTriangle& triangle, const std::array<FFSurfacePoint, 4>& footprint) {
    const auto& origin = footprint[0];
    const FFSurfacePoint edgeFirst{footprint[1].positionX - origin.positionX, footprint[1].positionY - origin.positionY, footprint[1].positionZ - origin.positionZ};
    const FFSurfacePoint edgeSecond{footprint[3].positionX - origin.positionX, footprint[3].positionY - origin.positionY, footprint[3].positionZ - origin.positionZ};
    const float normalX = edgeFirst.positionY * edgeSecond.positionZ - edgeFirst.positionZ * edgeSecond.positionY;
    const float normalY = edgeFirst.positionZ * edgeSecond.positionX - edgeFirst.positionX * edgeSecond.positionZ;
    const float normalZ = edgeFirst.positionX * edgeSecond.positionY - edgeFirst.positionY * edgeSecond.positionX;
    if (std::abs(normalZ) < Tolerance) return 0.0f;
    const float orientation = normalZ > 0.0f ? 1.0f : -1.0f;
    std::array<FFSurfacePoint, 8> polygon{};
    std::copy(triangle.points.begin(), triangle.points.end(), polygon.begin());
    int count = 3;
    for (int edge = 0; edge < 4 && count > 0; ++edge) {
        std::array<FFSurfacePoint, 8> clipped{};
        int clippedCount = 0;
        const auto& first = footprint[edge];
        const auto& second = footprint[(edge + 1) % 4];
        for (int index = 0; index < count; ++index) {
            const auto& previous = polygon[(index + count - 1) % count];
            const auto& current = polygon[index];
            const float previousSide = Side(first, second, previous.positionX, previous.positionY) * orientation;
            const float currentSide = Side(first, second, current.positionX, current.positionY) * orientation;
            const bool previousInside = previousSide >= 0.0f;
            const bool currentInside = currentSide >= 0.0f;
            if (previousInside != currentInside && previousSide != 0.0f && currentSide != 0.0f) {
                const float blend = previousSide / (previousSide - currentSide);
                clipped[clippedCount++] = {previous.positionX + (current.positionX - previous.positionX) * blend,
                    previous.positionY + (current.positionY - previous.positionY) * blend, previous.positionZ + (current.positionZ - previous.positionZ) * blend};
            }
            if (currentInside) clipped[clippedCount++] = current;
        }
        polygon = clipped;
        count = clippedCount;
    }
    float penetration = 0.0f;
    for (int index = 0; index < count; ++index) {
        const auto& point = polygon[index];
        const float height = origin.positionZ - (normalX * (point.positionX - origin.positionX) + normalY * (point.positionY - origin.positionY)) / normalZ;
        penetration = std::max(penetration, point.positionZ - height);
    }
    return penetration;
}
}

std::uint64_t FFDriveSurface::CellKey(int column, int row) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(column)) << 32) | static_cast<std::uint32_t>(row);
}

bool FFDriveSurface::Load(std::span<const std::uint8_t> bytes) {
    constexpr std::array<std::uint8_t, 8> signature{'F', 'F', 'S', 'U', 'R', 'F', '1', 0};
    static_assert(sizeof(FFSurfaceTriangle) == 36);
    if (bytes.size() < 12 || !std::equal(signature.begin(), signature.end(), bytes.begin())) return false;
    std::uint32_t count = 0;
    std::memcpy(&count, bytes.data() + 8, 4);
    if (count == 0 || count > 4000000 || bytes.size() != 12 + static_cast<std::size_t>(count) * 36) return false;
    std::vector<FFSurfaceTriangle> loaded(count);
    std::memcpy(loaded.data(), bytes.data() + 12, static_cast<std::size_t>(count) * 36);
    for (const auto& triangle : loaded) {
        for (const auto& point : triangle.points) {
            if (!std::isfinite(point.positionX) || !std::isfinite(point.positionY) || !std::isfinite(point.positionZ) ||
                std::abs(point.positionX) > 10000.0f || std::abs(point.positionY) > 10000.0f || std::abs(point.positionZ) > 1000.0f) return false;
        }
        if (std::abs(Side(triangle.points[0], triangle.points[1], triangle.points[2].positionX, triangle.points[2].positionY)) < Tolerance) return false;
        for (int index = 1; index < 3; ++index) {
            if (std::abs(triangle.points[index].positionX - triangle.points[0].positionX) > 100.0f ||
                std::abs(triangle.points[index].positionY - triangle.points[0].positionY) > 100.0f) return false;
        }
    }
    triangles = std::move(loaded);
    cells.clear();
    for (std::uint32_t index = 0; index < count; ++index) {
        const auto& points = triangles[index].points;
        const int firstColumn = static_cast<int>(std::floor(std::min({points[0].positionX, points[1].positionX, points[2].positionX}) / CellSize));
        const int lastColumn = static_cast<int>(std::floor(std::max({points[0].positionX, points[1].positionX, points[2].positionX}) / CellSize));
        const int firstRow = static_cast<int>(std::floor(std::min({points[0].positionY, points[1].positionY, points[2].positionY}) / CellSize));
        const int lastRow = static_cast<int>(std::floor(std::max({points[0].positionY, points[1].positionY, points[2].positionY}) / CellSize));
        for (int row = firstRow; row <= lastRow; ++row) {
            for (int column = firstColumn; column <= lastColumn; ++column) cells[CellKey(column, row)].push_back(index);
        }
    }
    return true;
}

std::optional<float> FFDriveSurface::Height(double positionX, double positionY) const {
    const auto cell = cells.find(CellKey(static_cast<int>(std::floor(positionX / CellSize)), static_cast<int>(std::floor(positionY / CellSize))));
    if (cell == cells.end()) return std::nullopt;
    std::optional<float> height;
    for (const auto index : cell->second) {
        const auto& points = triangles[index].points;
        const double area = Side(points[0], points[1], points[2].positionX, points[2].positionY);
        const double first = Side(points[1], points[2], positionX, positionY) / area;
        const double second = Side(points[2], points[0], positionX, positionY) / area;
        const double third = 1.0 - first - second;
        if (std::min({first, second, third}) < -Tolerance) continue;
        const float candidate = static_cast<float>(first * points[0].positionZ + second * points[1].positionZ + third * points[2].positionZ);
        height = height ? std::max(*height, candidate) : candidate;
    }
    return height;
}

float FFDriveSurface::Penetration(const std::array<FFSurfacePoint, 4>& footprint) const {
    float minimumX = footprint[0].positionX, maximumX = minimumX;
    float minimumY = footprint[0].positionY, maximumY = minimumY;
    for (const auto& point : footprint) {
        minimumX = std::min(minimumX, point.positionX);
        maximumX = std::max(maximumX, point.positionX);
        minimumY = std::min(minimumY, point.positionY);
        maximumY = std::max(maximumY, point.positionY);
    }
    float penetration = 0.0f;
    for (int row = static_cast<int>(std::floor(minimumY / CellSize)); row <= static_cast<int>(std::floor(maximumY / CellSize)); ++row) {
        for (int column = static_cast<int>(std::floor(minimumX / CellSize)); column <= static_cast<int>(std::floor(maximumX / CellSize)); ++column) {
            const auto cell = cells.find(CellKey(column, row));
            if (cell == cells.end()) continue;
            for (const auto index : cell->second) penetration = std::max(penetration, TrianglePenetration(triangles[index], footprint));
        }
    }
    return penetration;
}

const std::vector<FFSurfaceTriangle>& FFDriveSurface::Triangles() const {
    return triangles;
}
