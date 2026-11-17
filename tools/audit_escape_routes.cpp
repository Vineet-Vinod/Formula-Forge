#include "FFSimulation.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace {
constexpr float Units = 17.0f;
constexpr float KerbMetres = 0.85f;

struct Witness {
    std::string circuit;
    std::string escape;
    double x;
    double y;
    double z;
};

std::vector<std::uint8_t> Read(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

std::vector<Witness> ReadWitnesses(const std::filesystem::path& path) {
    std::ifstream stream(path);
    std::string line;
    std::getline(stream, line);
    if (line != "circuit,escape,x_m,y_m,z_m") return {};
    std::vector<Witness> result;
    while (std::getline(stream, line)) {
        std::replace(line.begin(), line.end(), ',', ' ');
        std::istringstream row(line);
        Witness point;
        if (!(row >> point.circuit >> point.escape >> point.x >> point.y >> point.z)) return {};
        result.push_back(point);
    }
    return result;
}

std::array<float, 10> Values(const ArcadeSurface& surface) {
    return {surface.grip, surface.acceleration, surface.rollingResistance, surface.steering,
        surface.maxSpeed, surface.driftCharge, surface.bumpiness, surface.groundElevation,
        surface.groundGrade, surface.launchVelocity};
}

template <typename T> void Append(std::vector<std::uint8_t>& bytes, const T& value) {
    const auto* first = reinterpret_cast<const std::uint8_t*>(&value);
    bytes.insert(bytes.end(), first, first + sizeof(value));
}

std::vector<std::uint8_t> SurfaceBytes(const FFSurfaceTriangle& triangle) {
    std::vector<std::uint8_t> bytes{'F', 'F', 'S', 'U', 'R', 'F', '1', 0};
    Append(bytes, std::uint32_t{1});
    Append(bytes, triangle);
    return bytes;
}

bool TinyTriangleAudit() {
    const FFSurfaceTriangle normal{{{{0, 0, 2}, {1, 0, 2}, {0, 1, 2}}}};
    const FFSurfaceTriangle tiny{{{{0, 0, 2}, {0.001f, 0, 2}, {0, 0.000001f, 2}}}};
    FFDriveSurface ordinary;
    if (!ordinary.Load(SurfaceBytes(normal)) || ordinary.Load(SurfaceBytes(tiny)) ||
        ordinary.Triangles().size() != 1 || ordinary.Triangles()[0].points[1].positionX != 1) return false;
    FFDriveSurface escape;
    if (!escape.Load(SurfaceBytes(tiny), 0.0) || !escape.Height(0.0003, 0.0000003)) return false;
    auto invalid = tiny;
    invalid.points[2].positionY = 0;
    if (escape.Load(SurfaceBytes(invalid), 0.0) || escape.Triangles().size() != 1) return false;
    invalid.points[2].positionY = std::numeric_limits<float>::quiet_NaN();
    return !escape.Load(SurfaceBytes(invalid), 0.0) && !escape.Load(SurfaceBytes(tiny), -1.0);
}

bool MainRoadAudit(FFSimulation& before, FFSimulation& after, int& probes) {
    for (float station = 0; station < before.lapLength; station += 2.0f) {
        const auto road = before.Sample(station);
        const Vec2 across{-road.tangent.y, road.tangent.x};
        for (const float side : {-1.0f, 0.0f, 1.0f}) {
            const Vec2 position = road.position + across * (side * (road.halfWidth + 0.40f) * Units);
            const auto projection = before.Project(position);
            if (std::abs(projection.lane) > (projection.halfWidth + KerbMetres) * Units) continue;
            before.vehicle.pos = after.vehicle.pos = position;
            before.vehicle.heading = after.vehicle.heading = std::atan2(road.tangent.y, road.tangent.x);
            before.vehicle.elevation = after.vehicle.elevation = before.Ground(position);
            const auto original = before.CurrentSurface();
            const auto candidate = after.CurrentSurface();
            if (before.Ground(position) != after.Ground(position) ||
                before.VisualGround(position) != after.VisualGround(position) ||
                Values(original) != Values(candidate) || original.allowsDrift != candidate.allowsDrift) {
                std::cerr << "Protected main-road change at " << station << ", side " << side << '\n';
                return false;
            }
            ++probes;
        }
    }
    return true;
}
}

int main(int argc, char* argv[]) {
    if (argc != 3 || !TinyTriangleAudit()) return 2;
    const auto witnesses = ReadWitnesses(argv[2]);
    if (witnesses.size() != 42) return 2;
    int failures = 0;
    int tested = 0;
    int totalWitnesses = 0;
    for (const auto& track : trackCatalog()) {
        const auto file = std::filesystem::path(argv[1]) / track.slug / "escape_surface.bin";
        if (!std::filesystem::exists(file)) continue;
        FFSimulation before(track.id);
        FFSimulation after(track.id);
        const auto surface = std::filesystem::path("Content/Generated") / track.contentDir / "drive_surface.bin";
        if (std::filesystem::exists(surface)) {
            const auto bytes = Read(surface);
            if (!before.driveSurface.Load(bytes) || !after.driveSurface.Load(bytes)) return 2;
        }
        if (!after.escapeSurface.Load(Read(file), 0.0)) return 2;
        int mainRoadProbes = 0;
        int sourceProbes = 0;
        int asphaltProbes = 0;
        int protectedWitnesses = 0;
        int misses = 0;
        int roleErrors = 0;
        float maximumSourceError = 0;
        bool passed = MainRoadAudit(before, after, mainRoadProbes);
        for (const auto& witness : witnesses) {
            if (witness.circuit != track.slug) continue;
            ++sourceProbes;
            const auto nativeHeight = after.escapeSurface.Height(witness.x, witness.y);
            if (!nativeHeight) { ++misses; continue; }
            maximumSourceError = std::max(maximumSourceError, std::abs(*nativeHeight - static_cast<float>(witness.z)));
            after.vehicle.pos = {static_cast<float>(witness.x * Units), static_cast<float>(-witness.y * Units)};
            const auto projection = after.Project(after.vehicle.pos);
            after.vehicle.heading = std::atan2(projection.tangent.y, projection.tangent.x);
            after.vehicle.elevation = static_cast<float>(witness.z * Units);
            if (std::abs(projection.lane) <= (projection.halfWidth + KerbMetres) * Units) {
                ++protectedWitnesses;
                continue;
            }
            for (const float height : {after.Ground(after.vehicle.pos) / Units,
                    after.VisualGround(after.vehicle.pos) / Units,
                    after.CurrentSurface().groundElevation / Units}) {
                maximumSourceError = std::max(maximumSourceError, std::abs(height - static_cast<float>(witness.z)));
            }
            if (std::abs(projection.lane) > (projection.halfWidth + KerbMetres + 1.02f) * Units) {
                ++asphaltProbes;
                const auto actual = after.CurrentSurface();
                const std::array<float, 6> values{actual.acceleration, actual.rollingResistance,
                    actual.steering, actual.maxSpeed, actual.driftCharge, actual.bumpiness};
                const std::array<float, 6> expected{0.82f, 2.0f, 0.88f, 0.86f, 0.20f, 0.14f};
                for (std::size_t index = 0; index < values.size(); ++index) {
                    if (std::abs(values[index] - expected[index]) > 0.000002f) ++roleErrors;
                }
                if (actual.allowsDrift) ++roleErrors;
            }
        }
        passed = passed && sourceProbes > 0 && asphaltProbes > 0 && misses == 0 && roleErrors == 0 && maximumSourceError < 0.001f;
        std::cout << "{\"circuit\":\"" << track.slug << "\",\"pass\":" << (passed ? "true" : "false")
            << ",\"main_road_exact_probes\":" << mainRoadProbes << ",\"source_witnesses\":" << sourceProbes
            << ",\"protected_witnesses\":" << protectedWitnesses << ",\"full_asphalt_witnesses\":" << asphaltProbes
            << ",\"height_misses\":" << misses << ",\"role_errors\":" << roleErrors
            << ",\"maximum_source_height_error_m\":" << maximumSourceError << "}\n";
        totalWitnesses += sourceProbes;
        ++tested;
        if (!passed) ++failures;
    }
    return tested == 4 && totalWitnesses == 42 && failures == 0 ? 0 : 1;
}
