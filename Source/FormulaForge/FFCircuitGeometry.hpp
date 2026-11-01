#pragma once

#include "authored_circuit_ground.hpp"
#include "authored_track_collision.hpp"
#include <span>

struct FFCircuitGeometry {
    std::span<const AuthoredBarrierSegment> barriers;
    std::span<const AuthoredSurfaceTriangle> runoff;
    const AuthoredGroundGrid& ground;
};

extern const FFCircuitGeometry FFMonzaGeometry;
extern const FFCircuitGeometry FFInterlagosGeometry;
