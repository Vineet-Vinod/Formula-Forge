#pragma once

#include "authored_circuit_ground.hpp"
#include "authored_track_collision.hpp"
#include "track_catalog.hpp"

#include <cstdint>
#include <vector>

// One station of the same plan the simulation drives. sim is the simulation
// frame; elevation and halfWidth are metres.
struct CircuitSample {
    Vec2 sim;
    Vec2 tangent;
    float station = 0.0f;
    float elevation = 0.0f;
    float halfWidth = 6.0f;
    float bankSlope = 0.0f;
    float bankQuadratic = 0.0f;
};

struct GeneratedSupport {
    std::vector<AuthoredBarrierSegment> barriers;
    std::vector<AuthoredSurfaceTriangle> runoff;
    std::vector<std::int16_t> heights;
    AuthoredGroundGrid ground;
};

float circuitShoulderMeters(const TrackCatalogEntry& track, float station, bool left);
float circuitSurfaceHeight(const CircuitSample& sample, float lane) noexcept;
bool circuitBankedPaving(const TrackCatalogEntry& track, float station, bool positiveSide) noexcept;
float circuitPavedBankReach(const TrackCatalogEntry& track, const CircuitSample& sample, bool positiveSide) noexcept;
std::vector<CircuitSample> sampleCircuit(const TrackCatalogEntry& track, int sampleCount = 0);
void buildGeneratedSupport(const TrackCatalogEntry& track, const std::vector<CircuitSample>& samples, GeneratedSupport& support);
bool writeGeneratedContact(const TrackCatalogEntry& track, const std::vector<CircuitSample>& samples, const std::string& directory);
