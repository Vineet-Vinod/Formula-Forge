#include "FFCircuitGeometry.hpp"

namespace {
#include "Native/track_data/interlagos_boundaries.inc"
#include "Native/track_data/interlagos_ground.inc"
}

const FFCircuitGeometry FFInterlagosGeometry{kInterlagosSurveyBarriers, kInterlagosSurveyRunoff, kInterlagosGround};
