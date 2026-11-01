#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include <unordered_map>
#include <vector>

struct FFSurfacePoint {
    float positionX;
    float positionY;
    float positionZ;
};

struct FFSurfaceTriangle {
    std::array<FFSurfacePoint, 3> points;
};

class FFDriveSurface {
public:
    bool Load(std::span<const std::uint8_t> bytes);
    std::optional<float> Height(double positionX, double positionY) const;
    float Penetration(const std::array<FFSurfacePoint, 4>& footprint) const;
    const std::vector<FFSurfaceTriangle>& Triangles() const;
private:
    static std::uint64_t CellKey(int column, int row);
    std::vector<FFSurfaceTriangle> triangles;
    std::unordered_map<std::uint64_t, std::vector<std::uint32_t>> cells;
};
