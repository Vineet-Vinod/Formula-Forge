#include "FFDriveSurface.hpp"
#ifndef FF_SURFACE_ONLY
#include "FFSimulation.hpp"
#endif

#include <algorithm>
#include <cmath>
#include <iostream>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>

namespace {
std::vector<std::uint8_t> SurfaceBytes(const std::vector<FFSurfaceTriangle>& triangles) {
    std::vector<std::uint8_t> bytes{'F', 'F', 'S', 'U', 'R', 'F', '1', 0};
    const auto count = static_cast<std::uint32_t>(triangles.size());
    bytes.resize(12 + triangles.size() * sizeof(FFSurfaceTriangle));
    std::memcpy(bytes.data() + 8, &count, 4);
    std::memcpy(bytes.data() + 12, triangles.data(), triangles.size() * sizeof(FFSurfaceTriangle));
    return bytes;
}

bool SurfaceAudit() {
    FFDriveSurface surface;
    const std::vector<FFSurfaceTriangle> triangles{
        {{{{-4.0f, -4.0f, 0.0f}, {4.0f, -4.0f, 0.0f}, {4.0f, 4.0f, 0.0f}}}},
        {{{{-4.0f, -4.0f, 0.0f}, {4.0f, 4.0f, 0.0f}, {-4.0f, 4.0f, 0.0f}}}},
        {{{{-0.02f, -2.0f, 0.083f}, {0.02f, -2.0f, 0.083f}, {0.02f, 2.0f, 0.083f}}}},
        {{{{-0.02f, -2.0f, 0.083f}, {0.02f, 2.0f, 0.083f}, {-0.02f, 2.0f, 0.083f}}}}};
    const auto bytes = SurfaceBytes(triangles);
    if (!surface.Load(bytes)) return false;
    const auto near = [](float actual, float expected) { return std::abs(actual - expected) < 0.0001f; };
    std::array<FFSurfacePoint, 4> footprint{{{-1.0f, -1.0f, 0.0f}, {1.0f, -1.0f, 0.0f}, {1.0f, 1.0f, 0.0f}, {-1.0f, 1.0f, 0.0f}}};
    if (!near(surface.Height(-0.01f, -0.01f).value_or(-1.0f), 0.083f) || surface.Height(10.0f, 10.0f)) return false;
    for (const auto& corner : footprint) if (!near(surface.Height(corner.positionX, corner.positionY).value_or(-1.0f), 0.0f)) return false;
    if (!near(surface.Penetration(footprint), 0.083f)) return false;
    std::reverse(footprint.begin(), footprint.end());
    if (!near(surface.Penetration(footprint), 0.083f)) return false;
    for (auto& point : footprint) point.positionZ = 0.083f;
    if (!near(surface.Penetration(footprint), 0.0f)) return false;
    for (auto& point : footprint) point.positionX += 2.0f;
    if (!near(surface.Penetration(footprint), 0.0f)) return false;
    footprint = {{{-0.02f, -2.0f, 0.0f}, {0.02f, -2.0f, 0.0f}, {0.02f, 2.0f, 0.0f}, {-0.02f, 2.0f, 0.0f}}};
    if (!near(surface.Penetration(footprint), 0.083f)) return false;
    footprint = {{{-1.0f, -1.0f, -0.1f}, {1.0f, -1.0f, 0.1f}, {1.0f, 1.0f, 0.1f}, {-1.0f, 1.0f, -0.1f}}};
    if (!near(surface.Penetration(footprint), 0.1f)) return false;
    const auto original = footprint;
    for (int angleIndex = 0; angleIndex < 720; ++angleIndex) {
        const float angle = angleIndex * 0.01f;
        for (std::size_t index = 0; index < footprint.size(); ++index) {
            footprint[index] = {original[index].positionX * std::cos(angle) - original[index].positionY * std::sin(angle),
                original[index].positionX * std::sin(angle) + original[index].positionY * std::cos(angle), 0.0f};
        }
        if (!near(surface.Penetration(footprint), 0.083f)) return false;
    }
    if (surface.Load(std::span<const std::uint8_t>(bytes.data(), bytes.size() - 1))) return false;
    auto invalid = bytes;
    invalid[0] = 0;
    if (surface.Load(invalid)) return false;
    auto degenerate = triangles;
    degenerate[0].points[1] = degenerate[0].points[0];
    if (surface.Load(SurfaceBytes(degenerate))) return false;
    std::vector<std::uint8_t> authored;
    for (int part = 0; part < 3; ++part) {
        std::ifstream file("Content/Generated/Data/drive_surface.bin." + std::to_string(part), std::ios::binary);
        if (!file) return false;
        authored.insert(authored.end(), std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
    }
    if (!surface.Load(authored)) {
        std::cerr << "Could not load the authored surface export\n";
        return false;
    }
    for (const auto& triangle : surface.Triangles()) {
        const auto& points = triangle.points;
        const double centreX = (static_cast<double>(points[0].positionX) + points[1].positionX + points[2].positionX) / 3.0;
        const double centreY = (static_cast<double>(points[0].positionY) + points[1].positionY + points[2].positionY) / 3.0;
        const float centreZ = (points[0].positionZ + points[1].positionZ + points[2].positionZ) / 3.0f;
        if (surface.Height(centreX, centreY).value_or(-1000.0f) < centreZ - 0.001f) {
            std::cerr << "Missing authored surface at " << centreX << ", " << centreY << ", " << centreZ << '\n';
            return false;
        }
    }
    std::cout << "Rendered road/kerb/apron/terrain triangles: " << surface.Triangles().size() << '\n';
    return true;
}
}

int main() {
    bool passed = SurfaceAudit();
    std::cout << "Rendered surface: narrow kerbs, sloped/rotated footprints, invalid files, authored triangle heights: "
              << (passed ? "PASS" : "FAIL") << '\n';
#ifndef FF_SURFACE_ONLY
    const bool simulationPassed = FFSimulation::Audit();
    std::cout << "Native simulation: road ground, swept barriers, lap gates, reverse, launch: "
              << (simulationPassed ? "PASS" : "FAIL") << '\n';
    passed = passed && simulationPassed;
#endif
    return passed ? 0 : 1;
}
