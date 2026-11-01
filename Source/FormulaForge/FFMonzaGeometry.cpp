#include "FFCircuitGeometry.hpp"

namespace {
#include "Native/track_data/monza_boundaries.inc"
#include "Native/track_data/monza_ground.inc"
}

const FFCircuitGeometry FFMonzaGeometry{kMonzaBarriers, kMonzaRunoffTriangles, kMonzaGround};
